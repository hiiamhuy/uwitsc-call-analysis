# HYAK Verification Plan

This document outlines a systematic verification plan to test the call analysis pipeline on the HYAK cluster.

## Prerequisites

Before starting verification, ensure you have:
- [ ] SSH access to HYAK 
- [ ] `HF_TOKEN` environment variable set (Hugging Face token)
- [ ] `SLURM_ACCOUNT` environment variable set (if required)
- [ ] Built WhisperX and Ollama container images (`whisperx_python.sif` and `ollama_python.sif`)
- [ ] Test audio files in a test directory

## Test Environment Setup

### Option 1: Using .env file (Recommended)

The repository includes a `.env` file for managing environment variables. This approach keeps your configuration organized and prevents accidentally committing sensitive tokens.

```bash
# 1. SSH into HYAK
ssh <netid>@klone.hyak.uw.edu

# 2. Clone the repository
git clone https://github.com/hiiamhuy/uwitsc-call-analysis.git
cd uwitsc-call-analysis

# 3. Update the .env file with your actual token
# Edit the .env file and replace the placeholder HF_TOKEN with your actual token
nano .env

# 4. Load environment variables from .env file
set -a
source .env
set +a

# 5. Verify environment is loaded
echo "SLURM_ACCOUNT: $SLURM_ACCOUNT"
echo "OLLAMA_MODEL: $OLLAMA_MODEL"
echo "WHISPERX_IMAGE: $WHISPERX_IMAGE"
```

**What's in the .env file:**
- `UWNETID` - Your UW NetID
- `SLURM_ACCOUNT` - Your SLURM account (e.g., "uwit")
- `GSCRATCH_BASE` - Base directory for all caches and data
- `PROJECT_ROOT` - Project repository location
- `APPTAINER_CACHEDIR`, `APPTAINER_TMPDIR` - Apptainer cache directories (prevents home directory quota issues)
- `OLLAMA_MODELS`, `OLLAMA_HOST` - Ollama configuration
- `XDG_CACHE_HOME` - Base cache directory for pip, Hugging Face, and transformers
- `PIP_CACHE_DIR` - pip package cache location
- `HF_HOME`, `TRANSFORMERS_CACHE` - Hugging Face model cache locations (used by WhisperX)
- `WHISPERX_IMAGE`, `OLLAMA_IMAGE` - Container image paths
- `HF_TOKEN` - Your Hugging Face token (required for model downloads)
- `OLLAMA_MODEL` - Default Ollama model to use

**Why these cache directories matter:**
- WhisperX and Hugging Face libraries download large models (several GB each)
- By default, these cache to your home directory, which has limited quota on Hyak
- Setting `HF_HOME` and `TRANSFORMERS_CACHE` redirects model downloads to gscratch
- `PIP_CACHE_DIR` prevents pip from filling up home directory during package installs

### Option 2: Manual export (Alternative)

If you prefer not to use the `.env` file:

```bash
# 1. SSH into HYAK
ssh <netid>@klone.hyak.uw.edu

git clone https://github.com/hiiamhuy/uwitsc-call-analysis.git

# 2. Navigate to repository
cd /path/to/uwitsc-call-analysis

# 3. Export required environment variables
export HF_TOKEN="your_huggingface_token_here"
export SLURM_ACCOUNT="uwit"
export WHISPERX_IMAGE="/path/to/whisperx_python.sif"
export OLLAMA_IMAGE="/path/to/ollama_python.sif"
export OLLAMA_MODEL="deepseek-r1:70b"

# 4. Set cache directories to avoid home directory quota issues
export XDG_CACHE_HOME="/mmfs1/gscratch/fellows/$UWNETID/xgd-cache"
export HF_HOME="$XDG_CACHE_HOME/huggingface"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export PIP_CACHE_DIR="$XDG_CACHE_HOME/pip"
```

## Verification Tests

### Test 1: Component Verification

**Purpose:** Verify that the core container images and scripts are functional.

```bash
# Test 1a: Verify WhisperX container allows imports
apptainer exec --nv $WHISPERX_IMAGE python3 -c "import whisperx; print('WhisperX ready')"

# Test 1b: Verify Ollama container structure
apptainer exec --nv $OLLAMA_IMAGE ollama --version
```

**Expected Results:**
- "WhisperX ready" printed.
- Ollama version number printed.

---

### Test 2: Reporting Logic Verification

**Purpose:** Verify that the analysis script correctly parses the detailed JSON scoring and produces a Markdown report.

**Note:** This test requires a running Ollama instance or can be mocked. If running on a login node without GPU, Ollama might be slow or fail. Ideally, run this within an interactive GPU session (`salloc`).

```bash
# Interactive session (optional but recommended)
# Note: We use gpu-rtx6k - our allocation: 10 CPUs, 81GB RAM, 2 GPUs with 48GB VRAM each
salloc -A $SLURM_ACCOUNT -p gpu-rtx6k -c 4 --gpus=1 --mem=81G --time=1:00:00


# Inside the session:
# 1. Start Ollama (in background)
export OLLAMA_HOST="127.0.0.1:11434"
apptainer exec --nv $OLLAMA_IMAGE ollama serve &
PID=$!
sleep 10 # Wait for startup

# 2. Pull model (if not present)
apptainer exec --nv $OLLAMA_IMAGE ollama pull $OLLAMA_MODEL

# 3. Run analysis on test data
# The repository includes sample test data in test_data/TestAgent/
# See test_data/README.md for details on the test scenarios

apptainer exec --nv \
  --bind $(pwd):/workspace \
  $OLLAMA_IMAGE \
  python3 analyze_with_ollama.py test_data/TestAgent --model $OLLAMA_MODEL

# 4. Cleanup
kill $PID
```

**Expected Results:**

After running the analysis, you should see new files created in `test_data/TestAgent/`:

1. **`analysis_results.json`** - Consolidated JSON with detailed scores for each call
2. **`analysis_report.md`** - Human-readable Markdown report with summary table and detailed breakdown

**Verify the results:**
```bash
# Check that analysis output files were created
ls -lh test_data/TestAgent/

# View the JSON results
cat test_data/TestAgent/analysis_results.json

# View the Markdown report
cat test_data/TestAgent/analysis_report.md
```

**About the test data:**
The repository includes two sample calls in `test_data/TestAgent/`:
- **call_001**: High-quality call (expected score ~95+) - demonstrates best practices
- **call_002**: Lower-quality call (expected score ~50-70) - demonstrates common issues

See [test_data/README.md](../test_data/README.md) for detailed information about each test scenario and expected scoring.

---

### Test 3: End-to-End Pipeline

**Purpose:** Run complete pipeline with test data to ensure orchestration works.

```bash
# 1. Create test directory
mkdir -p ../test_audio_input/AgentZero
cp /path/to/sample_audio.wav ../test_audio_input/AgentZero/

# 2. Run the pipeline wrapper
./run_speaker_analysis.sh ../test_audio_input 75 \
  --whisperx-image "$WHISPERX_IMAGE" \
  --ollama-image "$OLLAMA_IMAGE" \
  --ollama-model "$OLLAMA_MODEL" \
  --partition gpu-rtx6k \
  --account "$SLURM_ACCOUNT"

# 3. Monitor
squeue -u $USER
```

**Expected Results:**
- Job submits successfully.
- Logs in `../test_audio_input/logs/` show successful transcription and analysis.
- Output files organized into `needs_further_attention` or `reviewed`.
- `analysis_report.md` generated in the agent folder.

---

## Troubleshooting

### "Analysis failed" or JSON Errors
- Check the logs for "Raw reply". The model might be outputting text before/after the JSON.
- Ensure `analyze_with_ollama.py` has the latest robust JSON parsing logic.

### Visualization Issues
- If `analysis_report.md` looks broken, check the `generate_markdown_report` function in `analyze_with_ollama.py`.