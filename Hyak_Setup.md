# Hyak Setup Guide - UW ITSC Call Analysis Pipeline

**Last Updated**: 2025-12-30
**Status**: Production Ready
**Tested On**: Hyak Klone cluster

This guide provides step-by-step instructions for installing and running the UW ITSC Call Analysis pipeline on the Hyak supercomputer.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Installation Methods](#installation-methods)
4. [Container Building](#container-building)
5. [Running the Pipeline](#running-the-pipeline)
6. [Verification Tests](#verification-tests)
7. [Troubleshooting](#troubleshooting)
8. [Performance Notes](#performance-notes)

---

## Quick Start

**For experienced users** - complete setup in ~10 minutes (plus container build time):

```bash
# 1. SSH to Hyak
ssh <your-netid>@klone.hyak.uw.edu

# 2. Clone repository
cd /mmfs1/gscratch/fellows/<your-netid>
git clone https://github.com/hiiamhuy/uwitsc-call-analysis.git
cd uwitsc-call-analysis

# 3. Configure environment (edit with your details)
nano docs/hyak_bashrc.example
# Change: UWNETID="your_uwnetid" → UWNETID="<your-netid>"
# Add: Your Hugging Face token: export HF_TOKEN="hf_your_token_here"

# 4. Add to your ~/.bashrc
echo "source /mmfs1/gscratch/fellows/<your-netid>/uwitsc-call-analysis/docs/hyak_bashrc.example" >> ~/.bashrc
source ~/.bashrc

# 5. Download Ollama binary archive (~1.3GB)
cd container_artifacts/ollama/
wget https://ollama.com/download/ollama-linux-amd64.tgz
cd ../..

# 6. Build containers (~2-4 hours total) (you can run in parallel)
salloc -A uwit -p compute --mem=16G -c 4 --time=4:00:00
apptainer build whisperx_python.sif whisperx_python.def
salloc -A uwit -p compute --mem=16G -c 4 --time=4:00:00
apptainer build ollama_python.sif ollama_python.def
exit  # Exit build node

# 7. Run analysis
./run_speaker_analysis.sh audio_data
```

**Done!** Your environment is configured and persists across logins.

---

## Prerequisites

Before starting, ensure you have:

### Required Access
- **Hyak account** on the Klone cluster
- **SLURM account** (typically `uwit` for UW-IT)
- **SSH access** to `klone.hyak.uw.edu`

### Required Tokens/Credentials
- **Hugging Face Token** - Get from: https://huggingface.co/settings/tokens
  - Needed for downloading WhisperX models
  - Free account sufficient

### Storage Requirements
- **~30GB in gscratch** for:
  - Containers: ~23GB (WhisperX 9.1GB + Ollama 14GB)
  - Models/cache: ~5-7GB
  - Audio data: Variable

### Knowledge Prerequisites
- Basic Linux command line
- Understanding of SSH
- Familiarity with SLURM job scheduler (helpful but not required)

---

## Installation Methods

### Method 1: Using docs/hyak_bashrc.example (RECOMMENDED)

This method provides:
- **Persistent configuration** across all login sessions
- **Auto-creation** of cache directories
- **Helper functions** for diagnostics
- **All variables** pre-configured

#### Step 1: Clone Repository

```bash
# SSH to Hyak
ssh <your-netid>@klone.hyak.uw.edu

# Navigate to your gscratch directory
cd /mmfs1/gscratch/fellows/<your-netid>

# Clone the repository
git clone https://github.com/hiiamhuy/uwitsc-call-analysis.git uwitsc-call-analysis
cd uwitsc-call-analysis
```

#### Step 2: Configure docs/hyak_bashrc.example

```bash
# Open the configuration file
nano docs/hyak_bashrc.example
```

**Make these changes:**

1. **Line 19** - Update your NetID:
   ```bash
   export UWNETID="your_netid_here"  # Change from "hiiamhuy"
   ```

2. **After line 81** - Add your Hugging Face token:
   ```bash
   # Keep Hugging Face token out of history (set the value manually once)
   export HF_TOKEN="hf_your_actual_token_here"  # Add this line
   ```

**Save and exit** (Ctrl+X, Y, Enter in nano)

#### Step 3: Add to ~/.bashrc

```bash
# Add source line to your ~/.bashrc
echo "source /mmfs1/gscratch/fellows/<your-netid>/uwitsc-call-analysis/docs/hyak_bashrc.example" >> ~/.bashrc

# Load the configuration
source ~/.bashrc
```

You should see: `[Hyak] caches → /mmfs1/gscratch/fellows/<your-netid>; project → ...`

#### Step 4: Verify Configuration

```bash
# Use the built-in helper functions
whisperx_check
ollama_check

# Verify all variables are set
echo "NetID: $UWNETID"
echo "HF Token: ${HF_TOKEN:0:7}..."  # Shows first 7 chars
echo "WhisperX: $WHISPERX_IMAGE"
echo "Ollama image: $OLLAMA_IMAGE"
echo "Ollama models: $OLLAMA_MODELS"
```

**Expected output:**
```
WhisperX image: /mmfs1/gscratch/fellows/<your-netid>/uwitsc-call-analysis/whisperx_python.sif
Ollama image: /mmfs1/gscratch/fellows/<your-netid>/uwitsc-call-analysis/ollama_python.sif
Ollama models dir: /mmfs1/gscratch/fellows/<your-netid>/ollama
```

**Configuration complete!** This persists across all future logins.

#### Important: Python Module
The `docs/hyak_bashrc.example` file automatically loads Python 3.11 (required for the orchestrator script). If you encounter Python version errors:

```bash
# Verify Python version (should be 3.11.9)
python3 --version

# If still using system Python 3.6.8, manually load the module:
module load coenv/python/3.11.9
```

**Note**: This only affects the job submission script (`submit_slurm.py`). WhisperX and Ollama use their own Python environments inside containers and are not affected.

---

### Method 2: Using .env File (Alternative)

Use this method if you prefer per-session configuration or don't want to modify ~/.bashrc.

#### Step 1: Clone Repository
```bash
ssh <your-netid>@klone.hyak.uw.edu
cd /mmfs1/gscratch/fellows/<your-netid>
git clone https://github.com/hiiamhuy/uwitsc-call-analysis.git uwitsc-call-analysis
cd uwitsc-call-analysis
```

#### Step 2: Create and Configure .env

```bash
# Copy template
cp .env.example .env

# Edit with your details
nano .env
```

**Update these variables:**
- `UWNETID=your_netid_here`
- `HF_TOKEN=hf_your_actual_token_here`

**Save and exit**

#### Step 3: Load Environment (Required Each Session)

```bash
# Load environment variables
set -a
source .env
set +a

# Verify
echo "UWNETID: $UWNETID"
echo "WHISPERX_IMAGE: $WHISPERX_IMAGE"
```

**Note**: You must run `set -a && source .env && set +a` each time you log in.

---

## Container Building

### Overview

The pipeline uses two Apptainer containers:
- **whisperx_python.sif** (~9.1GB) - Speech-to-text with diarization
- **ollama_python.sif** (~14GB) - LLM-based quality analysis

**Build Time**: 1-2 hours per container (2-4 hours total)

### Preparing Build Artifacts

Before building the containers, you need to download the Ollama binary archive. Hyak compute nodes have network access, so you can download it directly.

#### Download Ollama Archive

```bash
# Navigate to the ollama artifacts directory
cd /mmfs1/gscratch/fellows/$UWNETID/uwitsc-call-analysis/container_artifacts/ollama/

# Download the Ollama Linux binary (takes ~2-5 minutes, ~1.3GB)
wget https://ollama.com/download/ollama-linux-amd64.tgz

# Verify the download
ls -lh ollama-linux-amd64.tgz
# Expected: ~1.3G file size
```

**Note**: The WhisperX container doesn't require any pre-downloaded artifacts - all dependencies will be fetched during the build process.

**Optional**: If you want to pre-download Python wheels for offline builds (useful if network is unreliable), see [container_artifacts/README.md](container_artifacts/README.md) for detailed instructions.

### Build Process

#### Step 1: Allocate Compute Node

```bash
# Allocate a compute node for building
# Use 'compute' partition (has network access for downloads)
salloc -A uwit -p compute --mem=16G -c 4 --time=4:00:00
```

**Wait for allocation** - you'll see: `salloc: Nodes nXXXX are ready for job`

#### Step 2: Build Containers

```bash
# Ensure you're in the project directory
cd /mmfs1/gscratch/fellows/$UWNETID/uwitsc-call-analysis

# Build WhisperX container (takes ~1-2 hours)
echo "Building WhisperX container..."
apptainer build whisperx_python.sif whisperx_python.def

# Build Ollama container (takes ~1-2 hours)
echo "Building Ollama container..."
apptainer build ollama_python.sif ollama_python.def
```

**Progress indicators:**
- You'll see package downloads and installations
- Final message: "INFO:    Build complete: ..."

#### Step 3: Verify Builds

```bash
# Check container files were created
ls -lh *.sif

# Expected output:
# -rwxr-xr-x 1 <you> all 14G <date> ollama_python.sif
# -rwxr-xr-x 1 <you> all 9.1G <date> whisperx_python.sif

# Test WhisperX container
apptainer exec --nv whisperx_python.sif python3 -c "import whisperx; print('WhisperX ready')"

# Test Ollama container
apptainer exec --nv ollama_python.sif python3 -c "import requests; print('Ollama ready')"

# Test Ollama version (warnings are normal)
apptainer exec --nv ollama_python.sif ollama --version
```

**Expected**: "WhisperX ready", "Ollama ready", and version output

#### Step 4: Exit Build Node

```bash
exit  # Return to login node
```

**Container building complete!**

### Build Troubleshooting

**Problem**: `cannot stat 'container_artifacts/ollama/ollama-linux-amd64.tgz': No such file or directory`
**Solution**: Download the Ollama archive before building:
```bash
cd /mmfs1/gscratch/fellows/$UWNETID/uwitsc-call-analysis/container_artifacts/ollama/
wget https://ollama.com/download/ollama-linux-amd64.tgz
```
See the "Preparing Build Artifacts" section above for details.

**Problem**: Build fails with "network error"
**Solution**: Ensure you're using `-p compute` partition (NOT `-p build`)

**Problem**: "disk quota exceeded"
**Solution**: Make sure `APPTAINER_CACHEDIR` points to gscratch (set by hyak_bashrc.example)

**Problem**: Build takes very long (>3 hours)
**Solution**: Normal for first build. Check `squeue -u $USER` to ensure job is still running

---

## Running the Pipeline

### Quick Run (Recommended)

```bash
# Run analysis on all agents in audio_data folder
./run_speaker_analysis.sh audio_data

# Or with custom score threshold (default is 75)
./run_speaker_analysis.sh audio_data 80
```

### Manual Python Execution

```bash
# Full control over parameters
python3 submit_slurm.py audio_data \
  --hf-token "$HF_TOKEN" \
  --whisperx-image "$WHISPERX_IMAGE" \
  --ollama-image "$OLLAMA_IMAGE" \
  --ollama-model "$OLLAMA_MODEL" \
  --score-threshold 75
```

### Monitor Jobs

```bash
# Check job status
squeue -u $USER

# Watch jobs (refreshes every 10 seconds)
watch -n 10 'squeue -u $USER'

# View logs (while jobs are running)
tail -f audio_data/logs/*.out
```

### View Results

```bash
# Results are organized by score threshold
# Default threshold: 75

# High-quality calls (score > 75)
ls audio_data/AgentName/reviewed/

# Calls needing attention (score ≤ 75)
ls audio_data/AgentName/needs_further_attention/

# View summary report
cat audio_data/AgentName/analysis_report.md

# View detailed JSON results
cat audio_data/AgentName/analysis_results.json
```

---

## Verification Tests

### Test 1: Container Import Verification

**Purpose**: Confirm containers can load required libraries

```bash
# Test WhisperX
apptainer exec --nv $WHISPERX_IMAGE python3 -c "import whisperx; print('WhisperX OK')"

# Test Ollama + requests
apptainer exec --nv $OLLAMA_IMAGE python3 -c "import requests; print('Ollama OK')"

# Test Ollama binary (warnings are normal)
apptainer exec --nv $OLLAMA_IMAGE ollama --version
```

**Expected**: "WhisperX OK", "Ollama OK", and version number

---

### Test 2: Sample Data Analysis

**Purpose**: Test full pipeline on included test data

```bash
# The repository includes test_data/TestAgent/ with 2 sample calls:
# - call_001: High-quality (expected score ~95+)
# - call_002: Lower-quality (expected score ~50-70)

# Allocate GPU node for testing
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=81G --time=1:00:00

# Start Ollama server
export OLLAMA_HOST="127.0.0.1:11434"
apptainer exec --nv $OLLAMA_IMAGE ollama serve &
OLLAMA_PID=$!
sleep 15  # Wait for startup

# Pull model (first time only, takes ~10-15 minutes)
apptainer exec --nv $OLLAMA_IMAGE ollama pull $OLLAMA_MODEL

# Run analysis on test data
apptainer exec --nv \
  --bind $(pwd):/workspace \
  $OLLAMA_IMAGE \
  python3 analyze_with_ollama.py test_data/TestAgent --model $OLLAMA_MODEL

# Check results
ls -lh test_data/TestAgent/
cat test_data/TestAgent/analysis_report.md

# Cleanup
kill $OLLAMA_PID
exit  # Exit GPU node
```

**Expected**: Analysis completes, report shows scores for both calls

---

### Test 3: Single Transcription Test

**Purpose**: Verify transcription works on compute nodes

```bash
# Pick a small audio file
find audio_data -name "*.wav" | head -1

# Allocate compute node
salloc -A uwit -p compute -c 4 --mem=16G --time=30:00

# Transcribe single file
apptainer exec --nv $WHISPERX_IMAGE \
  python3 whisperx_script.py /path/to/audio.wav --device cpu

# Check output (.vtt file created)
ls -lh /path/to/audio.vtt

exit  # Exit compute node
```

**Expected**: VTT file created with speaker-labeled transcription

---

## Troubleshooting

### Environment Issues

#### "Command not found" errors
**Problem**: Helper functions or variables not available
**Solution**:
```bash
# Reload environment
source ~/.bashrc

# Or if using .env method:
set -a && source .env && set +a

# Verify
whisperx_check
```

#### Containers not found
**Problem**: `apptainer: command not found` or container path errors
**Solution**:
```bash
# Check container paths are absolute
echo $WHISPERX_IMAGE
# Should show: /mmfs1/gscratch/fellows/<your-netid>/...

# Verify containers exist
ls -lh $WHISPERX_IMAGE
ls -lh $OLLAMA_IMAGE

# Reload environment if needed
source ~/.bashrc
```

---

### Container Build Issues

#### PyTorch pickle loading error
**Problem**: `_pickle.UnpicklingError: Weights only load failed`
**Status**: **FIXED** - Environment variable already set
**Details**: PyTorch 2.6+ changed security defaults. The fix (`TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=true`) is already included in both `docs/hyak_bashrc.example` and `.env.example`.

**Verify fix is active**:
```bash
echo $TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD
# Should show: true
```

#### Ollama version warnings
**Problem**: Warnings when checking `ollama --version`
**Status**: **NORMAL** - Not an error
**Example**:
```
Warning: could not connect to a running Ollama instance
Warning: client version is 0.13.0
```
**Explanation**: These warnings appear when checking the version without a running server. The version number still displays correctly. Ignore these warnings.

#### Network errors during build
**Problem**: "Could not resolve host" or download failures
**Solutions**:
1. Ensure using `-p compute` partition (has network access)
2. Check allocation: `squeue -u $USER`
3. Retry build after a few minutes

#### Disk quota exceeded
**Problem**: "No space left on device" during build
**Solutions**:
```bash
# Check home directory usage (should be <10GB)
du -sh ~

# Check cache directories are in gscratch
echo $APPTAINER_CACHEDIR
# Should show: /mmfs1/gscratch/fellows/<netid>/apptainer-cache

# Clean up if needed
rm -rf ~/apptainer-cache  # Remove if exists in home
```

---

### Runtime Issues

#### Jobs stay in queue (pending)
**Problem**: `squeue` shows jobs stuck in PD (pending) state
**Solutions**:
```bash
# Check job details
squeue -u $USER -o "%.18i %.9P %.30j %.8u %.2t %.10M %.6D %R"

# Check allocation availability
hyakalloc

# If no resources, wait or reduce requirements in submit_slurm.py
```

#### Analysis fails with JSON parsing errors
**Problem**: Ollama returns non-JSON output
**Solutions**:
```bash
# Check Ollama logs in audio_data/logs/*.err
cat audio_data/logs/AgentName_*.err

# Verify model is loaded
apptainer exec $OLLAMA_IMAGE ollama list

# Restart Ollama server if needed
```

#### Missing transcription files (.vtt)
**Problem**: No .vtt files generated after transcription
**Solutions**:
```bash
# Check SLURM logs for errors
cat audio_data/logs/*_transcription.err

# Verify HF_TOKEN is set
echo ${HF_TOKEN:0:7}...  # Should show "hf_XXXX..."

# Test WhisperX manually on small file
apptainer exec --nv $WHISPERX_IMAGE \
  python3 whisperx_script.py <audio_file.wav> --device cpu
```

---

### Performance Issues

#### Transcription very slow
**Problem**: Processing taking much longer than expected
**Solutions**:
- Ensure using GPU: Check `--device cuda` vs `--device cpu`
- Verify GPU allocation: `nvidia-smi` on compute node
- Check file sizes: Very large files (>1GB) take longer

#### Out of memory errors
**Problem**: "CUDA out of memory" or similar
**Solutions**:
```bash
# Request more memory
salloc -A uwit -p gpu-rtx6k --mem=81G  # Instead of default

# Or reduce batch size in processing scripts
# (Advanced - modify submit_slurm.py)
```

---

## Performance Notes

### Container Sizes
- **WhisperX**: 9.1 GB
- **Ollama**: 14 GB
- **Total**: ~23 GB

### Build Times
- **WhisperX**: 1-2 hours
- **Ollama**: 1-2 hours
- **Total**: 2-4 hours
- **Tip**: Build both in same allocation to save time

### Processing Times (Approximate)

**Transcription (WhisperX)**:
- Small audio (2-5 min, 200-500KB): ~30 seconds
- Medium audio (10-20 min, 1-2MB): ~1-2 minutes
- Large audio (30+ min, 5+MB): ~3-5 minutes
- **Note**: GPU vs CPU makes ~10x difference

**Analysis (Ollama)**:
- Per call: ~30-60 seconds
- Batch (10 calls): ~5-10 minutes
- **Note**: First run slower (model loading)

**Full Pipeline (per agent)**:
- Small folder (5-10 calls): ~10-15 minutes
- Medium folder (20-50 calls): ~30-60 minutes
- Large folder (100+ calls): 2-4 hours

### Parallel Testing Framework

For faster testing across multiple agents:

```bash
# Run tests in parallel across 4 nodes
./scripts/run-parallel-tests.sh --all --nodes 4

# Time savings: 40-50% vs sequential
# Example: 5 hours sequential → ~2.5-3 hours parallel
```

See [scripts/PARALLEL_TESTING_README.md](scripts/PARALLEL_TESTING_README.md) for details.

---

## Additional Resources

### Documentation
- **Full README**: [README.md](README.md) - Complete project documentation
- **Test Plan**: [Testing/00_TEST_PLAN.md](Testing/00_TEST_PLAN.md) - Comprehensive testing guide
- **Test Data**: [test_data/README.md](test_data/README.md) - Sample call descriptions
- **Container Artifacts**: [container_artifacts/README.md](container_artifacts/README.md) - Offline build instructions
- **Parallel Testing**: [scripts/PARALLEL_TESTING_README.md](scripts/PARALLEL_TESTING_README.md) - Multi-node testing

### Configuration Files
- **Environment template**: [.env.example](.env.example) - All configuration variables
- **Bashrc template**: [docs/hyak_bashrc.example](docs/hyak_bashrc.example) - Persistent environment
- **Container definitions**: `whisperx_python.def`, `ollama_python.def` - Build specifications

### Test Reports
- **Latest results**: [Testing/Hyak_setup_fresh_install_test_2025-12-22.md](Testing/Hyak_setup_fresh_install_test_2025-12-22.md)
- **Live testing**: [Testing/2025-12-22_10-00_hyak-live-testing.md](Testing/2025-12-22_10-00_hyak-live-testing.md)

---

## Getting Help

### Quick Diagnostics

```bash
# Run built-in diagnostic functions
whisperx_check  # Check WhisperX configuration
ollama_check    # Check Ollama configuration

# Verify all environment variables
env | grep -E 'WHISPERX|OLLAMA|HF_TOKEN|SLURM'

# Check container accessibility
ls -lh $WHISPERX_IMAGE $OLLAMA_IMAGE
```

### Common Commands Reference

```bash
# Check SLURM jobs
squeue -u $USER

# Check allocation
hyakalloc

# View logs
tail -f audio_data/logs/*.out

# Kill stuck job
scancel <job-id>

# Reload environment
source ~/.bashrc  # Or: set -a && source .env && set +a
```

### Support Channels

- **Documentation**: Start with [README.md](README.md)
- **Issues**: Check [Testing/](Testing/) folder for known issues
- **Hyak Help**: https://hyak.uw.edu/docs/

---

**Document Version**: 2.0
**Last Tested**: 2025-12-22
**Status**: Production Ready
