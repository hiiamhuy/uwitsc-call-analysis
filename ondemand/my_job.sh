#!/bin/bash
#SBATCH --job-name=call-analysis-orchestrator
#SBATCH --account=uwit
#SBATCH --partition=compute
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --output=orchestrator_%j.out
#SBATCH --error=orchestrator_%j.err

# This is a lightweight orchestrator job. It runs submit_slurm.py which
# then submits the actual GPU jobs for transcription and analysis.
# The GPU resources are requested by the child jobs, not this one.

set -euo pipefail

# Non-interactive SLURM shells skip ~/.bashrc, so load modules here
if command -v module >/dev/null 2>&1; then
    module load apptainer/1.2.5 2>/dev/null || true
    module load coenv/python/3.11.9 2>/dev/null || true
fi

# Use absolute path — SLURM working directory is not guaranteed to be ondemand/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/my_script.sh"

