#!/usr/bin/env python3
"""Batch transcription helper for WhisperX."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wmv", ".avi", ".mp4")

SCRIPT_ROOT = Path(__file__).resolve().parent
WHISPERX_SCRIPT = SCRIPT_ROOT / "whisperx_script.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe every audio file in a folder")
    parser.add_argument("speaker_folder", type=Path, help="Directory containing an agent's audio files")
    parser.add_argument(
        "--device",
        default="cuda",
        help="Execution device for WhisperX (default: cuda)",
    )
    parser.add_argument(
        "--output-format",
        choices=["vtt"],
        default="vtt",
        help="Output format (currently only vtt is supported)",
    )
    parser.add_argument(
        "--whisperx-script",
        type=Path,
        default=WHISPERX_SCRIPT,
        help="Path to the single-file transcription script",
    )
    parser.add_argument(
        "--extra-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Additional arguments forwarded to whisperx_script.py",
    )
    return parser.parse_args()


def discover_audio_files(folder: Path) -> list[Path]:
    files: list[Path] = []
    for extension in AUDIO_EXTENSIONS:
        files.extend(folder.glob(f"*{extension}"))
    return sorted({file.resolve() for file in files})


def run_transcription(audio_files: Iterable[Path], script_path: Path, device: str, extra_args: list[str]) -> None:
    python_exec = Path(sys.executable)
    for audio_file in audio_files:
        print(f"Transcribing {audio_file.name} ...")
        cmd = [
            str(python_exec),
            str(script_path),
            str(audio_file),
            "--device",
            device,
        ] + extra_args
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"  Transcription failed for {audio_file.name}")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
        else:
            print(f"  Completed {audio_file.name}")


def main() -> None:
    args = parse_args()

    speaker_folder = args.speaker_folder.expanduser().resolve()
    script_path = args.whisperx_script.expanduser().resolve()

    if not script_path.exists():
        raise SystemExit(f"whisperx_script.py not found at {script_path}")
    if not speaker_folder.exists() or not speaker_folder.is_dir():
        raise SystemExit(f"Speaker folder not found: {speaker_folder}")

    audio_files = discover_audio_files(speaker_folder)
    if not audio_files:
        raise SystemExit(f"No audio files discovered in {speaker_folder}")

    run_transcription(audio_files, script_path, args.device, args.extra_args)

    vtt_files = sorted(speaker_folder.glob("*.vtt"))
    print(f"Generated {len(vtt_files)} VTT files in {speaker_folder}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
