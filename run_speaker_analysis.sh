#!/bin/bash
# Wrapper for submitting the transcription + analysis pipeline to SLURM.

set -euo pipefail

# Load Python 3.11 for the orchestrator script (submit_slurm.py)
# This does NOT affect WhisperX, which runs in its own container
if command -v module >/dev/null 2>&1; then
    module load coenv/python/3.11.9 2>/dev/null || true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")"

usage() {
    cat <<USAGE
Usage: $0 [options] <folder_name> [threshold]

Positional arguments:
  folder_name            Relative path (from repo root) or absolute path containing agent folders
  threshold              Optional score threshold (default: 75)

Options:
  --whisperx-image PATH  Path to whisperx Apptainer image (.sif). Overrides WHISPERX_IMAGE env.
  --ollama-image PATH    Path to ollama Apptainer image (.sif). Overrides OLLAMA_IMAGE env.
  --ollama-model NAME    Ollama model to use (default: deepseek-r1:32b or OLLAMA_MODEL env).
  --partition NAME       SLURM partition (default: gpu-rtx6k).
  --gpus N               GPUs per job (default: 1).
  --mem GB               Memory per job in GB (default: 81).
  --time HH:MM:SS        Time limit per job (default: 02:00:00).
  --account NAME         SLURM account name (default: SLURM_ACCOUNT env).
  -h, --help             Show this help message.

Environment:
  HF_TOKEN must be exported with a valid Hugging Face token.
USAGE
}

WHISPERX_IMAGE="${WHISPERX_IMAGE:-}"
OLLAMA_IMAGE="${OLLAMA_IMAGE:-}"
OLLAMA_MODEL="${OLLAMA_MODEL:-deepseek-r1:32b}"
PARTITION="gpu-rtx6k"
GPUS=1
MEM=32
TIME_LIMIT="02:00:00"
ACCOUNT="${SLURM_ACCOUNT:-}"

POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --whisperx-image)
            WHISPERX_IMAGE="$2"; shift 2 ;;
        --ollama-image)
            OLLAMA_IMAGE="$2"; shift 2 ;;
        --ollama-model)
            OLLAMA_MODEL="$2"; shift 2 ;;
        --partition)
            PARTITION="$2"; shift 2 ;;
        --gpus)
            GPUS="$2"; shift 2 ;;
        --mem)
            MEM="$2"; shift 2 ;;
        --time)
            TIME_LIMIT="$2"; shift 2 ;;
        --account)
            ACCOUNT="$2"; shift 2 ;;
        -h|--help)
            usage; exit 0 ;;
        --)
            shift; break ;;
        -*)
            echo "Unknown option: $1" >&2
            usage
            exit 1 ;;
        *)
            POSITIONAL+=("$1"); shift ;;
    esac
done

set -- "${POSITIONAL[@]}" "$@"

if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

FOLDER_ARG="$1"
THRESHOLD="${2:-75}"

if [[ -z "${HF_TOKEN:-}" ]]; then
    echo "HF_TOKEN environment variable must be set" >&2
    exit 1
fi

if [[ "$FOLDER_ARG" = /* ]]; then
    BASE_DIR="$(realpath "$FOLDER_ARG")"
else
    BASE_DIR="$(realpath "$REPO_ROOT/$FOLDER_ARG")"
fi

if [[ ! -d "$BASE_DIR" ]]; then
    echo "Base directory not found: $BASE_DIR" >&2
    exit 1
fi

if [[ -z "$WHISPERX_IMAGE" || ! -f "$WHISPERX_IMAGE" ]]; then
    echo "WhisperX image not provided or does not exist" >&2
    exit 1
fi

if [[ -z "$OLLAMA_IMAGE" || ! -f "$OLLAMA_IMAGE" ]]; then
    echo "Ollama image not provided or does not exist" >&2
    exit 1
fi

echo "Running pipeline"
echo "  Repo root:     $REPO_ROOT"
echo "  Base dir:      $BASE_DIR"
echo "  Threshold:     $THRESHOLD"
echo "  WhisperX SIF:  $WHISPERX_IMAGE"
echo "  Ollama SIF:    $OLLAMA_IMAGE"
echo "  Ollama model:  $OLLAMA_MODEL"
echo "  Partition:     $PARTITION"
echo "  GPUs per job:  $GPUS"
echo "  Mem per job:   $MEM GB"
echo "  Time limit:    $TIME_LIMIT"

python3 "$REPO_ROOT/submit_slurm.py" \
    "$BASE_DIR" \
    --hf-token "$HF_TOKEN" \
    --threshold "$THRESHOLD" \
    --repo-root "$REPO_ROOT" \
    --whisperx-image "$WHISPERX_IMAGE" \
    --ollama-image "$OLLAMA_IMAGE" \
    --ollama-model "$OLLAMA_MODEL" \
    --partition "$PARTITION" \
    --gpus "$GPUS" \
    --mem "$MEM" \
    --time-limit "$TIME_LIMIT" \
    ${ACCOUNT:+--account "$ACCOUNT"}

echo "Submission complete. Monitor progress with: squeue -u $USER"
