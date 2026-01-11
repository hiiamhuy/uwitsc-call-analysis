#!/bin/bash
#SBATCH --job-name=pull_ollama
#SBATCH --partition=compute
#SBATCH --account=uwit
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=pull_log.out
#SBATCH --error=pull_log.err

# Required environment variables (defined in ~/.bashrc):
#   OLLAMA_IMAGE   - Path to ollama_python.sif container
#   PROJECT_ROOT   - Base path to uwitsc-call-analysis directory
# See docs/hyak_bashrc.example for setup instructions

set -e

module load apptainer

# Define paths
SIF_PATH="${OLLAMA_IMAGE:-${PROJECT_ROOT}/ollama_python.sif}"
MODEL="deepseek-r1:32b"

# Configure Ollama env
# Using a custom port to avoid any potential conflicts on the shared node
export OLLAMA_HOST="127.0.0.1:11435" 

echo "Starting Ollama Server..."
# We bind HOME because that's where ~/.ollama/models lives by default
apptainer exec --bind $HOME:$HOME $SIF_PATH ollama serve > ollama_server.log 2>&1 &
PID=$!

echo "Waiting for server (PID $PID) to initialize..."
sleep 20

echo "Pulling model: $MODEL"
apptainer exec --bind $HOME:$HOME $SIF_PATH ollama pull $MODEL

echo "Pull complete. Stopping server."
kill $PID
