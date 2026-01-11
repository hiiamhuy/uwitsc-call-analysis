#!/bin/bash
#SBATCH --job-name=call_analysis
#SBATCH --partition=compute
#SBATCH --account=uwit
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=12:00:00
#SBATCH --output=audio_data/logs/analysis_%j.out
#SBATCH --error=audio_data/logs/analysis_%j.err

# UW ITSC Call Analysis Pipeline
# Submit via OOD: https://hyak.uw.edu/docs/ood/schedule-job
# Or via command line: sbatch submit_analysis.slurm

set -euo pipefail

# Load required modules
module load apptainer
module load coenv/python/3.11.9

# Project paths - uses $USER automatically
PROJECT_ROOT="/mmfs1/gscratch/fellows/${USER}/uwitsc-call-analysis"

# Container paths
export WHISPERX_IMAGE="${WHISPERX_IMAGE:-${PROJECT_ROOT}/whisperx_python.sif}"
export OLLAMA_IMAGE="${OLLAMA_IMAGE:-${PROJECT_ROOT}/ollama_python.sif}"

# Cache directories (avoid filling home directory)
export APPTAINER_CACHEDIR="/mmfs1/gscratch/fellows/${USER}/apptainer-cache"
export APPTAINER_TMPDIR="/mmfs1/gscratch/fellows/${USER}/apptainer-tmp"
export OLLAMA_MODELS="/mmfs1/gscratch/fellows/${USER}/ollama"
export XDG_CACHE_HOME="/mmfs1/gscratch/fellows/${USER}/xgd-cache"

# Hugging Face token (should be set in ~/.bashrc or here)
# export HF_TOKEN="your_token_here"  # Uncomment and set if not in ~/.bashrc

# Ensure log directory exists
mkdir -p "${PROJECT_ROOT}/audio_data/logs"

cd "${PROJECT_ROOT}"

echo "============================================"
echo "Starting Call Analysis Pipeline"
echo "Time: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "============================================"

# Run the analysis pipeline
./run_speaker_analysis.sh \
    --ollama-model deepseek-r1:32b \
    --mem 32 \
    audio_data/ \
    75

echo "============================================"
echo "Pipeline completed at $(date)"
echo "============================================"
