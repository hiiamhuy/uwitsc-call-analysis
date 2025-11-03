# HYAK Verification Plan for Bug Fixes

This document outlines a systematic verification plan to test all bug fixes on the HYAK cluster.

## Prerequisites

Before starting verification, ensure you have:
- [ ] SSH access to HYAK cluster
- [ ] HF_TOKEN environment variable set
- [ ] SLURM_ACCOUNT environment variable set (if required)
- [ ] Built WhisperX and Ollama container images
- [ ] Test audio files in a test directory

## Test Environment Setup

```bash
# 1. SSH into HYAK
ssh <netid>@klone.hyak.uw.edu

# 2. Navigate to repository
cd /path/to/uw-call-center-codex

# 3. Verify repo structure
ls -la uwitsc-call-analysis/

# 4. Set environment variables
export HF_TOKEN="your_huggingface_token"
export SLURM_ACCOUNT="your_slurm_account"  # if required
export WHISPERX_IMAGE="/path/to/whisperx_python.sif"
export OLLAMA_IMAGE="/path/to/ollama_python.sif"
export OLLAMA_MODEL="llama3.2:3b"
```

## Verification Tests

### Test 1: Path Resolution Verification (Bugs #1, #2, #3)

**Purpose:** Verify all script paths are correctly resolved

```bash
# Test 1a: Check if scripts exist at corrected paths
test -f uwitsc-call-analysis/transcribe_calls.py && echo "✓ transcribe_calls.py found" || echo "✗ transcribe_calls.py missing"
test -f uwitsc-call-analysis/analyze_with_ollama.py && echo "✓ analyze_with_ollama.py found" || echo "✗ analyze_with_ollama.py missing"
test -f uwitsc-call-analysis/submit_slurm.py && echo "✓ submit_slurm.py found" || echo "✗ submit_slurm.py missing"

# Test 1b: Verify paths in generated SLURM scripts
cd uwitsc-call-analysis
grep -n "transcribe_calls.py" submit_slurm.py
grep -n "analyze_with_ollama.py" submit_slurm.py
grep -n "submit_slurm.py" run_speaker_analysis.sh

# Expected output should show: uwitsc-call-analysis/ prefix in all paths
```

**Expected Results:**
- All three scripts exist in `uwitsc-call-analysis/` directory
- All grep results show paths with `uwitsc-call-analysis/` prefix

---

### Test 2: Diarization Model Loading (Bug #4)

**Purpose:** Verify WhisperX diarization model loads correctly with HF_TOKEN

```bash
# Test 2a: Check whisperx_script.py imports os module
grep -n "^import os" uwitsc-call-analysis/whisperx_script.py

# Test 2b: Check DiarizationPipeline is used instead of load_model
grep -A5 "def load_diarization_model" uwitsc-call-analysis/whisperx_script.py

# Test 2c: Interactive test inside container (if possible)
apptainer exec --nv $WHISPERX_IMAGE python3 << 'EOF'
import os
os.environ['HF_TOKEN'] = 'test'
try:
    import whisperx
    print("✓ WhisperX imported successfully")
    print("✓ DiarizationPipeline available:", hasattr(whisperx, 'DiarizationPipeline'))
except Exception as e:
    print("✗ Error:", e)
EOF
```

**Expected Results:**
- `import os` found on line 14
- `DiarizationPipeline` method used in `load_diarization_model` function
- WhisperX imports successfully and has DiarizationPipeline attribute

---

### Test 3: Diarization Method Call (Bug #5)

**Purpose:** Verify diarization is called with correct parameters

```bash
# Test 3a: Check diarization call parameters
grep -n "diarize_segments = diarization_model(audio" uwitsc-call-analysis/whisperx_script.py

# Should NOT contain: min_speakers=1, max_speakers=2
# Should show: diarization_model(audio)
```

**Expected Results:**
- Line should show `diarization_model(audio)` without min/max speaker parameters

---

### Test 4: Threshold Logic (Bug #6)

**Purpose:** Verify threshold comparison uses < instead of <=

```bash
# Test 4a: Check threshold comparison
grep -n "score < self.score_threshold" uwitsc-call-analysis/submit_slurm.py

# Should show line 254 with: score < self.score_threshold
```

**Expected Results:**
- Line 254 uses `<` operator (not `<=`)
- Calls scoring exactly at threshold go to "reviewed" folder

---

### Test 5: Error Handling Improvements (Bug #7)

**Purpose:** Verify warning messages are added for debugging

```bash
# Test 5a: Check for warning messages in analyze_with_ollama.py
grep -n "Warning:" uwitsc-call-analysis/analyze_with_ollama.py

# Should show warnings for nested dict and JSON parsing failures
```

**Expected Results:**
- Warning message for nested dict structure (around line 109)
- Warning message for JSON parsing failures (around line 113)

---

### Test 6: End-to-End Pipeline Test

**Purpose:** Run complete pipeline with test data

```bash
# Test 6a: Create test directory with sample audio
mkdir -p test_audio/TestAgent
cp /path/to/sample.wav test_audio/TestAgent/

# Test 6b: Run the pipeline
cd uwitsc-call-analysis
./run_speaker_analysis.sh ../test_audio 75 \
  --whisperx-image "$WHISPERX_IMAGE" \
  --ollama-image "$OLLAMA_IMAGE" \
  --ollama-model "$OLLAMA_MODEL" \
  --partition gpu-h200 \
  --account "$SLURM_ACCOUNT"

# Test 6c: Monitor job
squeue -u $USER

# Test 6d: Check logs after completion
tail -100 test_audio/logs/TestAgent_pipeline_*.out
tail -100 test_audio/logs/TestAgent_pipeline_*.err
```

**Expected Results:**
- Job submits successfully (no "file not found" errors)
- Transcription runs and produces VTT files
- Ollama analysis runs and produces JSON results
- No path resolution errors in logs
- Diarization runs without errors (if GPU available)

---

### Test 7: Output Validation

**Purpose:** Verify all expected outputs are created

```bash
# Test 7a: Check transcription outputs
ls -lh test_audio/TestAgent/*.vtt

# Test 7b: Check analysis results
cat test_audio/TestAgent/analysis_results.json | python3 -m json.tool

# Test 7c: Check folder organization
ls -R test_audio/TestAgent/needs_further_attention/
ls -R test_audio/TestAgent/reviewed/
```

**Expected Results:**
- VTT files created for each audio file
- `analysis_results.json` contains valid JSON with score and reasoning
- Files organized into folders based on threshold
- Speaker labels present in VTT files

---

## Verification Checklist

After running all tests, verify:

- [ ] **Bug #1 Fixed:** transcribe_calls.py path resolves correctly in SLURM script
- [ ] **Bug #2 Fixed:** analyze_with_ollama.py path resolves correctly in SLURM script
- [ ] **Bug #3 Fixed:** submit_slurm.py path resolves correctly in bash wrapper
- [ ] **Bug #4 Fixed:** Diarization model loads with DiarizationPipeline and HF_TOKEN
- [ ] **Bug #5 Fixed:** Diarization called without min/max speaker parameters
- [ ] **Bug #6 Fixed:** Threshold comparison uses < (scores at threshold go to reviewed)
- [ ] **Bug #7 Fixed:** Warning messages appear in logs for debugging issues

---

## Troubleshooting Common Issues

### Issue: "Module not found" errors in container
**Solution:** Verify container images were built with all dependencies

### Issue: HF_TOKEN authentication failures
**Solution:** Verify HF_TOKEN is valid and exported before running scripts

### Issue: SLURM job doesn't start
**Solution:** Check SLURM account and partition settings with `sinfo` and `sacctmgr`

### Issue: Diarization fails silently
**Solution:** Check logs for warnings; diarization gracefully degrades to heuristics if unavailable

---

## Success Criteria

All fixes are successfully verified when:
1. ✅ All path resolution tests pass without errors
2. ✅ Diarization model loads correctly with proper API
3. ✅ End-to-end pipeline completes successfully
4. ✅ Output files are generated in expected locations
5. ✅ No "file not found" or "module not found" errors in logs
6. ✅ Threshold logic correctly categorizes results
7. ✅ Warning messages provide useful debugging information

---

## Next Steps After Verification

Once all tests pass:
1. Commit changes to version control
2. Update documentation with any HYAK-specific notes
3. Create a release tag for the bug-fix version
4. Notify team of fixes and verification results