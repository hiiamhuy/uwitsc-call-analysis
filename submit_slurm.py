#!/usr/bin/env python3
"""SLURM orchestration for the call-analysis pipeline.

IMPORTANT: This script requires Python 3.7 or later.
If you get a SyntaxError about 'annotations', run:
  module load coenv/python/3.11.9
Or use the wrapper script:
  ./run_speaker_analysis.sh <folder_name>
"""
from __future__ import annotations

import sys

# Verify Python version (runtime check for dataclasses support)
if sys.version_info < (3, 7):
    sys.stderr.write("ERROR: This script requires Python 3.7 or later.\n")
    sys.stderr.write("Current Python version: {}.{}.{}\n".format(*sys.version_info[:3]))
    sys.stderr.write("\nPlease load Python 3.11 module:\n")
    sys.stderr.write("  module load coenv/python/3.11.9\n")
    sys.stderr.write("\nOr use the wrapper script:\n")
    sys.stderr.write("  ./run_speaker_analysis.sh <folder_name>\n")
    sys.exit(1)

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wmv", ".avi", ".mp4")
DEFAULT_SCORE_THRESHOLD = 75
DEFAULT_GPU_PARTITION = "gpu-rtx6k"
DEFAULT_JOB_TIME = "02:00:00"


@dataclass
class ContainerConfig:
    repo_root: Path
    whisperx_image: Path
    ollama_image: Path
    ollama_model: str
    partition: str = DEFAULT_GPU_PARTITION
    gpus_per_job: int = 1
    mem_gb: int = 81
    time_limit: str = DEFAULT_JOB_TIME
    account: Optional[str] = None
    qos: Optional[str] = None


class SpeakerAnalysisOrchestrator:
    def __init__(self, base_dir: Path, hf_token: str, score_threshold: int, config: ContainerConfig):
        self.base_dir = base_dir
        self.hf_token = hf_token
        self.score_threshold = score_threshold
        self.config = config
        self.job_ids: List[str] = []
        self.speaker_folders: List[Path] = []

    # --- Discovery -----------------------------------------------------------------

    def discover_speaker_folders(self) -> List[Path]:
        print("Discovering speaker folders...")
        folders: List[Path] = []
        for entry in sorted(self.base_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            audio_files = [f for f in entry.rglob("*") if f.suffix.lower() in AUDIO_EXTENSIONS]
            if audio_files:
                folders.append(entry)
                print(f"  {entry.name}: {len(audio_files)} audio files")
        self.speaker_folders = folders
        print(f"Total speaker folders: {len(self.speaker_folders)}")
        return folders

    # --- Job script generation ------------------------------------------------------

    def create_slurm_job_script(self, speaker_folder: Path) -> Path:
        job_name = f"{speaker_folder.name}_pipeline"
        script_path = self.base_dir / f"{job_name}.slurm"
        repo_root = self.config.repo_root
        whisperx_image = self.config.whisperx_image
        ollama_image = self.config.ollama_image
        model_name = self.config.ollama_model

        account_line = f"#SBATCH --account={self.config.account}" if self.config.account else ""

        # Auto-determine QoS if not explicitly set
        if self.config.qos:
            qos_line = f"#SBATCH --qos={self.config.qos}"
        elif self.config.account and self.config.partition.startswith("gpu-"):
            # Format: {account}-gpu-{gpu_type}
            gpu_type = self.config.partition.replace("gpu-", "")
            auto_qos = f"{self.config.account}-gpu-{gpu_type}"
            qos_line = f"#SBATCH --qos={auto_qos}"
        else:
            qos_line = ""

        script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition={self.config.partition}
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --gpus={self.config.gpus_per_job}
#SBATCH --mem={self.config.mem_gb}G
#SBATCH --time={self.config.time_limit}
#SBATCH --output={self.base_dir}/logs/{job_name}_%j.out
#SBATCH --error={self.base_dir}/logs/{job_name}_%j.err
#SBATCH --mail-type=END,FAIL
{account_line}
{qos_line}

set -euo pipefail

module load apptainer

export HF_TOKEN="{self.hf_token}"
export PYTHONUNBUFFERED=1

REPO_ROOT="{repo_root}"
BASE_DIR="{self.base_dir}"
SPEAKER_DIR="{speaker_folder}"
WHISPERX_IMAGE="{whisperx_image}"
OLLAMA_IMAGE="{ollama_image}"
OLLAMA_MODEL="{model_name}"

mkdir -p "$BASE_DIR/logs"

# Run WhisperX transcription
apptainer exec --nv \
  --env LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib \
  --bind "$REPO_ROOT:$REPO_ROOT" \
  --bind "$BASE_DIR:$BASE_DIR" \
  "$WHISPERX_IMAGE" \
  python3 "$REPO_ROOT/transcribe_calls.py" "$SPEAKER_DIR" --device cuda

# Launch Ollama-backed analysis
apptainer exec --nv \
  --bind "$REPO_ROOT:$REPO_ROOT" \
  --bind "$BASE_DIR:$BASE_DIR" \
  --bind "$HOME/.ollama:$HOME/.ollama" \
  "$OLLAMA_IMAGE" \
  bash <<ANALYZE
set -eo pipefail
export OLLAMA_HOST="127.0.0.1:11434"
export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY

# Start Ollama server with proper error handling
ollama serve >/tmp/ollama.log 2>&1 &
OLLAMA_PID=\\$!
set -u

# Check if Ollama started successfully
if [[ -n "\\$OLLAMA_PID" ]] && kill -0 "\\$OLLAMA_PID" 2>/dev/null; then
    echo "Ollama server started with PID: \\$OLLAMA_PID"
    trap 'kill \\$OLLAMA_PID 2>/dev/null || true' EXIT

    # Wait for Ollama to be ready (up to 60 seconds)
    echo "Waiting for Ollama server to be ready..."
    for i in {{1..12}}; do
        if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            echo "Ollama server is ready"
            break
        fi
        echo "  Attempt \\$i/12: waiting..."
        sleep 5
    done

    # Check if model exists, pull only if necessary
    echo "Checking for model: $OLLAMA_MODEL"
    if ! ollama list | grep -q "$OLLAMA_MODEL"; then
        echo "Model not found, pulling: $OLLAMA_MODEL"
        ollama pull "$OLLAMA_MODEL"
    else
        echo "Model already available: $OLLAMA_MODEL"
    fi

    # Verify model is in the list
    ollama list

    # Warm up the model with a test request to load it into GPU memory
    echo "Warming up model..."
    echo '{{"model": "$OLLAMA_MODEL", "prompt": "Hello", "stream": false}}' | \
        curl -s -X POST http://127.0.0.1:11434/api/generate -d @- > /dev/null
    echo "Model warmed up and ready"

    # Run the analysis
    python3 "$REPO_ROOT/analyze_with_ollama.py" "$SPEAKER_DIR" --model "$OLLAMA_MODEL"
else
    echo "Failed to start Ollama server, skipping analysis" >&2
    exit 1
fi
ANALYZE

echo "Pipeline completed for {speaker_folder.name}"
"""
        script_path.write_text(script, encoding="utf-8")
        script_path.chmod(0o755)
        return script_path

    # --- Job submission -------------------------------------------------------------

    def submit_slurm_job(self, script_path: Path) -> Optional[str]:
        env = os.environ.copy()
        env["HF_TOKEN"] = self.hf_token
        try:
            result = subprocess.run(
                ["sbatch", str(script_path)],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            print(f"Failed to submit {script_path.name}: {exc.stderr.strip()}")
            return None
        job_id = result.stdout.strip().split()[-1]
        print(f"  Submitted job {job_id} for {script_path.stem}")
        return job_id

    # --- Job monitoring -------------------------------------------------------------

    def monitor_jobs(self) -> None:
        if not self.job_ids:
            print("No jobs submitted; skipping monitoring")
            return

        user = os.environ.get("USER", "")
        print(f"Monitoring jobs: {', '.join(self.job_ids)}")
        while True:
            remaining = []
            for job in self.job_ids:
                probe = subprocess.run(
                    ["squeue", "-j", job, "--noheader"],
                    capture_output=True,
                    text=True,
                )
                if probe.returncode == 0 and probe.stdout.strip():
                    remaining.append(job)
            if not remaining:
                print("All jobs have completed")
                return
            print(f"  Still running: {', '.join(remaining)}")
            if user:
                subprocess.run(["squeue", "-u", user])
            time.sleep(180)

    # --- Result organisation --------------------------------------------------------

    def organise_results(self, speaker_folder: Path) -> None:
        results_path = speaker_folder / "analysis_results.json"
        if not results_path.exists():
            print(f"No analysis results for {speaker_folder.name}; skipping organisation")
            return
        with results_path.open("r", encoding="utf-8") as handle:
            results = json.load(handle)

        needs_attention = speaker_folder / "needs_further_attention"
        reviewed = speaker_folder / "reviewed"
        needs_attention.mkdir(exist_ok=True)
        reviewed.mkdir(exist_ok=True)

        for transcription_file, payload in results.items():
            score = int(payload.get("score", 0))
            audio_name = payload.get("audio_file", transcription_file)
            audio_path = speaker_folder / audio_name
            call_id = Path(audio_name).stem
            destination_root = needs_attention if score < self.score_threshold else reviewed
            target_dir = destination_root / call_id
            target_dir.mkdir(parents=True, exist_ok=True)

            self._copy_if_exists(audio_path, target_dir / audio_path.name)
            for suffix in (".vtt", ".srt", ".txt", ".json"):
                candidate = speaker_folder / f"{call_id}{suffix}"
                self._copy_if_exists(candidate, target_dir / candidate.name)

            per_call_results = target_dir / "analysis_results.json"
            with per_call_results.open("w", encoding="utf-8") as handle:
                json.dump({transcription_file: payload}, handle, indent=2)

        print(f"Organised results for {speaker_folder.name}")

    @staticmethod
    def _copy_if_exists(src: Path, dst: Path) -> None:
        if src.exists() and src.is_file():
            shutil.copy2(src, dst)

    # --- High level orchestration ---------------------------------------------------

    def run(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "logs").mkdir(exist_ok=True)
        self.discover_speaker_folders()
        if not self.speaker_folders:
            print("No speaker folders discovered; exiting")
            return

        for speaker_folder in self.speaker_folders:
            script = self.create_slurm_job_script(speaker_folder)
            job_id = self.submit_slurm_job(script)
            if job_id:
                self.job_ids.append(job_id)

        self.monitor_jobs()

        for folder in self.speaker_folders:
            self.organise_results(folder)


# ------------------------------------------------------------------------------------


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit WhisperX + Ollama jobs to SLURM")
    parser.add_argument("base_dir", type=Path, help="Directory containing per-agent subfolders")
    parser.add_argument("--hf-token", required=True, help="Hugging Face token for WhisperX")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_SCORE_THRESHOLD,
        help="Score threshold separating reviewed vs needs attention",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Repository root path mounted into containers",
    )
    parser.add_argument(
        "--whisperx-image",
        type=Path,
        default=os.environ.get("WHISPERX_IMAGE"),
        help="Path to the WhisperX Apptainer image (.sif)",
    )
    parser.add_argument(
        "--ollama-image",
        type=Path,
        default=os.environ.get("OLLAMA_IMAGE"),
        help="Path to the Ollama Apptainer image (.sif)",
    )
    parser.add_argument(
        "--ollama-model",
        default=os.environ.get("OLLAMA_MODEL", "deepseek-r1:32b"),
        help="Model name expected to exist inside the Ollama image",
    )
    parser.add_argument(
        "--partition",
        default=DEFAULT_GPU_PARTITION,
        help="SLURM partition to target",
    )
    parser.add_argument(
        "--mem",
        type=int,
        default=81,
        help="Memory per job (GB)",
    )
    parser.add_argument(
        "--gpus",
        type=int,
        default=1,
        help="GPUs per job",
    )
    parser.add_argument(
        "--time-limit",
        default=DEFAULT_JOB_TIME,
        help="Wall clock limit per job (HH:MM:SS)",
    )
    parser.add_argument(
        "--account",
        default=os.environ.get("SLURM_ACCOUNT"),
        help="Optional SLURM account override",
    )
    parser.add_argument(
        "--qos",
        default=None,
        help="SLURM QoS (Quality of Service) - omit if your cluster doesn't use QoS",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    base_dir = args.base_dir.expanduser().resolve()
    repo_root = args.repo_root.expanduser().resolve()

    whisperx_image = Path(args.whisperx_image).expanduser().resolve() if args.whisperx_image else None
    ollama_image = Path(args.ollama_image).expanduser().resolve() if args.ollama_image else None
    if not whisperx_image or not whisperx_image.exists():
        raise SystemExit("WhisperX image path must be provided (via --whisperx-image or WHISPERX_IMAGE)")
    if not ollama_image or not ollama_image.exists():
        raise SystemExit("Ollama image path must be provided (via --ollama-image or OLLAMA_IMAGE)")

    config = ContainerConfig(
        repo_root=repo_root,
        whisperx_image=whisperx_image,
        ollama_image=ollama_image,
        ollama_model=args.ollama_model,
        partition=args.partition,
        gpus_per_job=args.gpus,
        mem_gb=args.mem,
        time_limit=args.time_limit,
        account=args.account,
        qos=args.qos,
    )

    orchestrator = SpeakerAnalysisOrchestrator(base_dir, args.hf_token, args.threshold, config)
    orchestrator.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
