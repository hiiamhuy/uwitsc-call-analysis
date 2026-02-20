#!/bin/bash
# OnDemand wrapper for the call-analysis pipeline.
# Called by my_job.sh — submits GPU jobs via submit_slurm.py.

set -euo pipefail

# ── Paths (absolute — this script runs from the OnDemand job directory) ──────
REPO_ROOT="/mmfs1/gscratch/fellows/transcribeit/uwitsc-call-analysis"
DATA_DIR="${REPO_ROOT}/audio_data"

# ── Configuration ────────────────────────────────────────────────────────────
# These can be overridden by setting environment variables in OnDemand or
# editing the values below directly.
THRESHOLD="${THRESHOLD:-75}"
OLLAMA_MODEL="${OLLAMA_MODEL:-deepseek-r1:32b}"
PARTITION="${PARTITION:-gpu-rtx6k}"
GPUS="${GPUS:-1}"
MEM="${MEM:-32}"
TIME_LIMIT="${TIME_LIMIT:-02:00:00}"

# ── Project environment ──────────────────────────────────────────────────────
# Non-interactive shells (like SBATCH jobs) skip ~/.bashrc early, so we set
# the required variables here directly. Update these values as needed.
export UWNETID="transcribeit"
export GSCRATCH_BASE="/mmfs1/gscratch/fellows/${UWNETID}"

export HF_TOKEN="${HF_TOKEN:-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}"
export WHISPERX_IMAGE="${WHISPERX_IMAGE:-${REPO_ROOT}/whisperx_python.sif}"
export OLLAMA_IMAGE="${OLLAMA_IMAGE:-${REPO_ROOT}/ollama_python.sif}"
export SLURM_ACCOUNT="${SLURM_ACCOUNT:-uwit}"

# PyTorch fix for 2.6+ pickle loading security changes (needed by WhisperX)
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=true

# Redirect caches to gscratch (keeps 10GB home partition clean)
export APPTAINER_CACHEDIR="${GSCRATCH_BASE}/apptainer-cache"
export APPTAINER_TMPDIR="${GSCRATCH_BASE}/apptainer-tmp"
export OLLAMA_MODELS="${GSCRATCH_BASE}/ollama"
export XDG_CACHE_HOME="${GSCRATCH_BASE}/xdg-cache"
export PIP_CACHE_DIR="${XDG_CACHE_HOME}/pip"
export HF_HOME="${XDG_CACHE_HOME}/huggingface"
export TRANSFORMERS_CACHE="${HF_HOME}/transformers"

# Ensure cache directories exist
mkdir -p "${APPTAINER_CACHEDIR}" "${APPTAINER_TMPDIR}" "${OLLAMA_MODELS}" "${XDG_CACHE_HOME}"

# Bind ~/.ollama to the relocated model store if the symlink is missing
if [ ! -L "$HOME/.ollama" ]; then
    if [ -d "$HOME/.ollama" ]; then
        mv "$HOME/.ollama" "$HOME/.ollama.bak.$(date +%Y%m%d%H%M%S)"
    fi
    ln -s "${OLLAMA_MODELS}" "$HOME/.ollama"
fi

# ── Validate required vars ───────────────────────────────────────────────────
if [[ -z "${HF_TOKEN:-}" ]]; then
    echo "ERROR: HF_TOKEN is not set" >&2
    exit 1
fi
if [[ -z "${WHISPERX_IMAGE:-}" || ! -f "${WHISPERX_IMAGE}" ]]; then
    echo "ERROR: WHISPERX_IMAGE is not set or file does not exist" >&2
    exit 1
fi
if [[ -z "${OLLAMA_IMAGE:-}" || ! -f "${OLLAMA_IMAGE}" ]]; then
    echo "ERROR: OLLAMA_IMAGE is not set or file does not exist" >&2
    exit 1
fi

# ── Load modules ─────────────────────────────────────────────────────────────
if command -v module >/dev/null 2>&1; then
    module load apptainer/1.2.5 2>/dev/null || true
    module load coenv/python/3.11.9 2>/dev/null || true
fi

# ── Run the orchestrator ─────────────────────────────────────────────────────
echo "=== Call Analysis Pipeline ==="
echo "  Repo root:    ${REPO_ROOT}"
echo "  Data dir:     ${DATA_DIR}"
echo "  Threshold:    ${THRESHOLD}"
echo "  WhisperX SIF: ${WHISPERX_IMAGE}"
echo "  Ollama SIF:   ${OLLAMA_IMAGE}"
echo "  Ollama model: ${OLLAMA_MODEL}"
echo "  Partition:    ${PARTITION}"
echo "  GPUs:         ${GPUS}"
echo "  Memory:       ${MEM}G"
echo "  Time limit:   ${TIME_LIMIT}"
echo ""

python3 "${REPO_ROOT}/submit_slurm.py" \
    "${DATA_DIR}" \
    --hf-token "${HF_TOKEN}" \
    --threshold "${THRESHOLD}" \
    --repo-root "${REPO_ROOT}" \
    --whisperx-image "${WHISPERX_IMAGE}" \
    --ollama-image "${OLLAMA_IMAGE}" \
    --ollama-model "${OLLAMA_MODEL}" \
    --partition "${PARTITION}" \
    --gpus "${GPUS}" \
    --mem "${MEM}" \
    --time-limit "${TIME_LIMIT}" \
    ${SLURM_ACCOUNT:+--account "${SLURM_ACCOUNT}"}

echo ""
echo "Orchestrator finished. Monitor GPU jobs with: squeue -u ${USER}"

