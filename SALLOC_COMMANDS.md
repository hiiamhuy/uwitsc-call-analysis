# Hyak salloc Commands Reference

**Quick reference guide for interactive SLURM allocations on Hyak**

This guide provides additional salloc commands for the UWITSC call analysis pipeline beyond the basic commands in [Hyak_Setup.md](Hyak_Setup.md). Use these for development, debugging, testing, and maintenance tasks on the login node.

---

## Quick Reference Table

| Use Case | Partition | CPUs | Memory | GPUs | Time | When to Use |
|----------|-----------|------|--------|------|------|-------------|
| Python debugging | compute | 4 | 8G | 0 | 2h | Script development, testing code changes |
| GPU debugging | gpu-rtx6k | 4 | 32G | 1 | 1h | WhisperX issues, CUDA errors |
| File organization | compute | 8 | 4G | 0 | 1h | Batch file operations, validation |
| VTT cleanup | compute | 4 | 8G | 0 | 30m | Text processing, format conversion |
| Model comparison | gpu-rtx6k | 4 | 64G | 1 | 2h | Testing different Ollama models |
| Prompt engineering | gpu-rtx6k | 4 | 81G | 1 | 1.5h | Tuning analysis prompts |
| Transcription benchmark | gpu-rtx6k | 8 | 32G | 1 | 1h | Performance profiling |
| Pipeline profiling | gpu-rtx6k | 4 | 81G | 1 | 3h | End-to-end testing |
| Cache cleanup | compute | 2 | 4G | 0 | 30m | Disk space maintenance |
| Container validation | compute | 4 | 16G | 0 | 1h | Post-build testing |
| Fast single file | compute | 2 | 8G | 0 | 15m | Quick iteration cycles |
| Small batch test | gpu-rtx6k | 4 | 32G | 1 | 30m | Pre-production validation |
| Data staging | compute | 8 | 8G | 0 | 1h | Unzip/organize downloads |
| Results archiving | compute | 4 | 16G | 0 | 1h | Package outputs for download |
| Experimental build | compute | 6 | 24G | 0 | 3h | Container development |
| Model download | compute | 4 | 32G | 0 | 2h | Interactive model management |

---

## 1. Development & Debugging

### Interactive Python Development Session

**Command:**
```bash
salloc -A uwit -p compute -c 4 --mem=8G --time=2:00:00
```

**Purpose:** Test script modifications, debug Python code, inspect outputs without GPU overhead

**Example:**
```bash
salloc -A uwit -p compute -c 4 --mem=8G --time=2:00:00

# Test analysis script modifications
python3 -c "from analyze_with_ollama import extract_transcription_text; print('Import successful')"

# Debug VTT parsing
python3 -c "import json; print(json.load(open('audio_data/TestAgent/analysis_results.json')))"

exit
```

---

### GPU Debugging Session

**Command:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=32G --time=1:00:00
```

**Purpose:** Debug WhisperX transcription failures, investigate CUDA errors, test GPU availability

**Example:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=32G --time=1:00:00

# Verify GPU access
python3 test_gpu_access.py

# Test WhisperX on single file
apptainer exec --nv $WHISPERX_IMAGE python3 whisperx_script.py \
  audio_data/TestAgent/call_001.wav --device cuda

# Check CUDA memory
nvidia-smi

exit
```

---

## 2. Data Management

### Audio File Organization & Validation

**Command:**
```bash
salloc -A uwit -p compute -c 8 --mem=4G --time=1:00:00
```

**Purpose:** Batch rename files, validate audio formats, check file integrity, organize downloads

**Example:**
```bash
salloc -A uwit -p compute -c 8 --mem=4G --time=1:00:00

# Validate audio file formats
find audio_data -type f \( -name "*.wav" -o -name "*.mp3" \) -print0 | \
  xargs -0 -P 8 -I {} file {}

# Count audio files per agent
for agent in audio_data/*/; do
  echo "$(basename $agent): $(find $agent -name "*.wav" | wc -l) files"
done

# Check total size
du -sh audio_data/*/

exit
```

---

### VTT File Cleanup & Batch Conversion

**Command:**
```bash
salloc -A uwit -p compute -c 4 --mem=8G --time=30:00
```

**Purpose:** Remove orphaned VTT files, convert formats, clean up failed transcriptions

**Example:**
```bash
salloc -A uwit -p compute -c 4 --mem=8G --time=30:00

# Find VTT files without corresponding audio
cd audio_data
for vtt in */*.vtt; do
  base="${vtt%.vtt}"
  if [[ ! -f "${base}.wav" && ! -f "${base}.mp3" ]]; then
    echo "Orphaned: $vtt"
  fi
done

# Validate VTT format
find audio_data -name "*.vtt" -exec grep -q "WEBVTT" {} \; -print

exit
```

---

## 3. Model Testing & Experimentation

### Ollama Model Comparison

**Command:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=64G --time=2:00:00
```

**Purpose:** Test different Ollama models (alternatives to deepseek-r1:32b), benchmark inference speed

**Example:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=64G --time=2:00:00

# Start Ollama server
export OLLAMA_HOST="127.0.0.1:11434"
apptainer exec --nv $OLLAMA_IMAGE ollama serve &
OLLAMA_PID=$!
sleep 15

# Pull and test alternative models
apptainer exec --nv $OLLAMA_IMAGE ollama pull llama3.1:8b

# Benchmark inference
time apptainer exec --nv $OLLAMA_IMAGE \
  python3 analyze_with_ollama.py test_data/TestAgent --model llama3.1:8b

# List models
apptainer exec --nv $OLLAMA_IMAGE ollama list

kill $OLLAMA_PID
exit
```

---

### Prompt Engineering Session

**Command:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=81G --time=1:30:00
```

**Purpose:** Test different prompt templates, tune scoring criteria, validate JSON parsing

**Example:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=81G --time=1:30:00

# Start Ollama
export OLLAMA_HOST="127.0.0.1:11434"
apptainer exec --nv $OLLAMA_IMAGE ollama serve &
OLLAMA_PID=$!
sleep 15

# Test modified analysis script
apptainer exec --nv $OLLAMA_IMAGE \
  python3 analyze_with_ollama.py test_data/TestAgent --model deepseek-r1:32b

# Review results
cat test_data/TestAgent/analysis_report.md

kill $OLLAMA_PID
exit
```

---

## 4. Performance Analysis

### Transcription Benchmarking

**Command:**
```bash
salloc -A uwit -p gpu-rtx6k -c 8 --gpus=1 --mem=32G --time=1:00:00
```

**Purpose:** Measure transcription speed, compare CPU vs GPU, profile memory usage

**Example:**
```bash
salloc -A uwit -p gpu-rtx6k -c 8 --gpus=1 --mem=32G --time=1:00:00

# Benchmark GPU transcription
time apptainer exec --nv $WHISPERX_IMAGE \
  python3 whisperx_script.py test_data/TestAgent/call_001.wav --device cuda

# Benchmark CPU transcription
time apptainer exec --nv $WHISPERX_IMAGE \
  python3 whisperx_script.py test_data/TestAgent/call_002.wav --device cpu

# Monitor GPU utilization
nvidia-smi dmon -s u

exit
```

---

### End-to-End Pipeline Profiling

**Command:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=81G --time=3:00:00
```

**Purpose:** Profile complete pipeline, identify bottlenecks, estimate production resource needs

**Example:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=81G --time=3:00:00

# Create timing log
LOGFILE="pipeline_profile_$(date +%Y%m%d_%H%M%S).log"

# Transcription phase
echo "=== TRANSCRIPTION ===" | tee -a $LOGFILE
time apptainer exec --nv $WHISPERX_IMAGE \
  python3 transcribe_calls.py test_data/TestAgent --device cuda 2>&1 | tee -a $LOGFILE

# Analysis phase
echo "=== ANALYSIS ===" | tee -a $LOGFILE
export OLLAMA_HOST="127.0.0.1:11434"
apptainer exec --nv $OLLAMA_IMAGE ollama serve &
OLLAMA_PID=$!
sleep 15

time apptainer exec --nv $OLLAMA_IMAGE \
  python3 analyze_with_ollama.py test_data/TestAgent 2>&1 | tee -a $LOGFILE

kill $OLLAMA_PID
exit
```

---

## 5. Maintenance & Administration

### Cache Cleanup Session

**Command:**
```bash
salloc -A uwit -p compute -c 2 --mem=4G --time=30:00
```

**Purpose:** Clean Apptainer cache, remove old models, free gscratch space

**Example:**
```bash
salloc -A uwit -p compute -c 2 --mem=4G --time=30:00

# Check current usage
du -sh $APPTAINER_CACHEDIR $OLLAMA_MODELS $HF_HOME

# Clean Apptainer cache
apptainer cache clean -f

# List Ollama models
apptainer exec $OLLAMA_IMAGE ollama list

# Clean old SLURM logs
find audio_data/logs -name "*.out" -mtime +7 -delete
find audio_data/logs -name "*.err" -mtime +7 -delete

# Verify cleanup
du -sh $APPTAINER_CACHEDIR $OLLAMA_MODELS

exit
```

---

### Container Testing After Rebuild

**Command:**
```bash
salloc -A uwit -p compute -c 4 --mem=16G --time=1:00:00
```

**Purpose:** Verify containers after rebuilding, test imports, validate dependencies

**Example:**
```bash
salloc -A uwit -p compute -c 4 --mem=16G --time=1:00:00

# Test WhisperX container
echo "Testing WhisperX..."
apptainer exec $WHISPERX_IMAGE python3 -c "
import whisperx
import torch
import transformers
print('✓ All imports successful')
print(f'WhisperX version: {whisperx.__version__}')
print(f'PyTorch version: {torch.__version__}')
"

# Test Ollama container
echo "Testing Ollama..."
apptainer exec $OLLAMA_IMAGE python3 -c "
import requests
print('✓ Requests imported')
"

# Test Ollama binary
apptainer exec $OLLAMA_IMAGE ollama --version

# Run health check
./test_llama.sh

exit
```

---

## 6. Quick Testing & Iteration

### Fast Single-File Test

**Command:**
```bash
salloc -A uwit -p compute -c 2 --mem=8G --time=15:00
```

**Purpose:** Quickly test script changes on one file, validate fixes, check output format

**Example:**
```bash
salloc -A uwit -p compute -c 2 --mem=8G --time=15:00

# Quick transcription test (CPU mode)
apptainer exec $WHISPERX_IMAGE \
  python3 whisperx_script.py test_data/TestAgent/call_001.wav --device cpu

# Verify output
ls -lh test_data/TestAgent/call_001.vtt
head -20 test_data/TestAgent/call_001.vtt

exit
```

---

### Small Batch GPU Test

**Command:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=32G --time=30:00
```

**Purpose:** Test pipeline on 2-5 files before full production run

**Example:**
```bash
salloc -A uwit -p gpu-rtx6k -c 4 --gpus=1 --mem=32G --time=30:00

# Create small test subset
mkdir -p /tmp/small_test/TestAgent
cp test_data/TestAgent/call_00{1,2}.wav /tmp/small_test/TestAgent/

# Run transcription
apptainer exec --nv $WHISPERX_IMAGE \
  python3 transcribe_calls.py /tmp/small_test/TestAgent --device cuda

# Run analysis
export OLLAMA_HOST="127.0.0.1:11434"
apptainer exec --nv $OLLAMA_IMAGE ollama serve &
OLLAMA_PID=$!
sleep 15

apptainer exec --nv $OLLAMA_IMAGE \
  python3 analyze_with_ollama.py /tmp/small_test/TestAgent

cat /tmp/small_test/TestAgent/analysis_report.md

kill $OLLAMA_PID
exit
```

---

## 7. File Transfer & Data Staging

### Data Preparation from Engage Downloads

**Command:**
```bash
salloc -A uwit -p compute -c 8 --mem=8G --time=1:00:00
```

**Purpose:** Unzip Engage downloads, organize into agent folders

**Example:**
```bash
salloc -A uwit -p compute -c 8 --mem=8G --time=1:00:00

cd /mmfs1/gscratch/fellows/$UWNETID/staging

# Unzip all archives in parallel
find . -name "*.zip" -print0 | xargs -0 -P 8 -I {} unzip -q {}

# Organize into audio_data structure
for dir in */; do
  agent_name=$(basename "$dir" | cut -d'_' -f1)
  mkdir -p ../uwitsc-call-analysis/audio_data/"$agent_name"
  mv "$dir"/*.wav ../uwitsc-call-analysis/audio_data/"$agent_name"/ 2>/dev/null || true
done

# Verify
for agent in ../uwitsc-call-analysis/audio_data/*/; do
  echo "$(basename $agent): $(find "$agent" -name "*.wav" | wc -l) files"
done

exit
```

---

### Results Archiving for Download

**Command:**
```bash
salloc -A uwit -p compute -c 4 --mem=16G --time=1:00:00
```

**Purpose:** Package analysis results for Globus download, create summary archives

**Example:**
```bash
salloc -A uwit -p compute -c 4 --mem=16G --time=1:00:00

cd audio_data

# Create tar.gz archives per agent
for agent in */; do
  agent_name=$(basename "$agent")
  echo "Archiving $agent_name..."
  tar -czf "${agent_name}_results_$(date +%Y%m%d).tar.gz" \
    "$agent_name/reviewed/" \
    "$agent_name/needs_further_attention/" \
    "$agent_name/analysis_report.md" \
    "$agent_name/analysis_results.json"
done

# Move to transfer location
mkdir -p /mmfs1/gscratch/fellows/$UWNETID/transfer
mv *_results_*.tar.gz /mmfs1/gscratch/fellows/$UWNETID/transfer/

ls -lh /mmfs1/gscratch/fellows/$UWNETID/transfer/

exit
```

---

## 8. Container Development

### Experimental Container Build & Test

**Command:**
```bash
salloc -A uwit -p compute --mem=24G -c 6 --time=3:00:00
```

**Purpose:** Build and test experimental container modifications

**Example:**
```bash
salloc -A uwit -p compute --mem=24G -c 6 --time=3:00:00

cd /mmfs1/gscratch/fellows/$UWNETID/uwitsc-call-analysis

# Create experimental definition
cp whisperx_python.def whisperx_python_experimental.def

# Build experimental container
apptainer build whisperx_experimental.sif whisperx_python_experimental.def

# Test the new container
apptainer exec whisperx_experimental.sif python3 -c "
import whisperx
print('✓ WhisperX loaded successfully')
"

exit
```

---

### Ollama Model Pre-download (Interactive)

**Command:**
```bash
salloc -A uwit -p compute -c 4 --mem=32G --time=2:00:00
```

**Purpose:** Interactively download and verify Ollama models (alternative to sbatch download_model.slurm)

**Example:**
```bash
salloc -A uwit -p compute -c 4 --mem=32G --time=2:00:00

# Start Ollama server
export OLLAMA_HOST="127.0.0.1:11434"
apptainer exec --bind $HOME:$HOME $OLLAMA_IMAGE ollama serve &
OLLAMA_PID=$!
sleep 15

# Pull model
apptainer exec --bind $HOME:$HOME $OLLAMA_IMAGE ollama pull deepseek-r1:32b

# Verify
apptainer exec --bind $HOME:$HOME $OLLAMA_IMAGE ollama list

# Test model loads
echo '{"model": "deepseek-r1:32b", "prompt": "Hello", "stream": false}' | \
  curl -s -X POST http://127.0.0.1:11434/api/generate -d @-

kill $OLLAMA_PID
exit
```

---

## Decision Criteria

### Partition Selection

**Use `compute` partition when:**
- No GPU needed (file operations, Python development, container builds)
- Need network access (model downloads, pip installs)
- CPU transcription is acceptable for testing

**Use `gpu-rtx6k` partition when:**
- GPU required (WhisperX, Ollama inference)
- Testing production-like environment
- Need fast transcription on real audio files

### Memory Guidelines

- **4-8 GB**: File operations, text processing, simple scripts
- **16 GB**: Container builds (standard), batch VTT processing
- **24-32 GB**: Experimental builds, model downloads, small GPU workloads
- **64 GB**: Testing alternative Ollama models (<30B parameters)
- **81 GB**: Production specs for deepseek-r1:32b model

### Time Guidelines

- **15-30 min**: Quick tests, single file operations, cleanup tasks
- **1 hour**: Standard development sessions, benchmarking, validation
- **2 hours**: Model downloads, container builds, experimentation
- **3 hours**: Full pipeline profiling, complex build iterations

### CPU Guidelines

- **2-4 CPUs**: Most single-threaded work, standard processing
- **6-8 CPUs**: Parallel file operations, compression, batch processing

---

## Related Documentation

- **[Hyak_Setup.md](Hyak_Setup.md)** - Complete installation and setup guide
- **[README.md](README.md)** - Project overview and workflow
- **[submit_slurm.py](submit_slurm.py)** - Production SLURM configuration
- **[docs/hyak_bashrc.example.sh](docs/hyak_bashrc.example.sh)** - Environment setup

---

**Last Updated:** 2026-01-06
**Version:** 1.0
