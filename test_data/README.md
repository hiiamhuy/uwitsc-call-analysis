# Test Data

This directory contains sample test data for verifying the call analysis pipeline.

## Directory Structure

```
test_data/
└── TestAgent/                    # Sample agent folder
    ├── call_001/                 # High-quality call example
    │   └── call_001.vtt         # VTT transcription file
    └── call_002/                 # Lower-quality call example
        └── call_002.vtt         # VTT transcription file
```

## Test Call Descriptions

### call_001 - High Quality Call (Expected Score: ~95+)
**Scenario:** Email access issue - password reset

**Key features that should score well:**
- NetID obtained within 12 seconds (10/10 points)
- Zoom verification mentioned and used (5/5 points)
- Issue fully resolved - password successfully reset (15/15 points)
- Clear, step-by-step instructions provided (15/15 points)
- Confidentiality maintained until Zoom verification (7/7 points)
- Strong technical support quality (45-48/48 points)

### call_002 - Lower Quality Call (Expected Score: ~50-70)
**Scenario:** Library printing issue - unresolved

**Key features that should score lower:**
- NetID obtained late (~18 seconds) after asking for student number first (5-7/10 points)
- No Zoom verification used (0/5 points)
- Issue NOT resolved - referred elsewhere (5-8/15 points)
- Vague troubleshooting steps without explanation (8-10/15 points)
- Confidentiality concern - asked for student number before NetID (3-5/7 points)
- Weak technical support - didn't exhaust troubleshooting options (20-30/48 points)

## Usage

### On Hyak

To test the analysis pipeline with this test data:

```bash
# Navigate to your project directory
cd /mmfs1/gscratch/fellows/$UWNETID/uwitsc-call-analysis

# Load environment variables
set -a
source .env
set +a

# Start Ollama server in an interactive session
salloc -A $SLURM_ACCOUNT -p gpu-rtx6k -c 4 --gpus=1 --mem=81G --time=1:00:00

# Inside the session, start Ollama
apptainer exec --nv $OLLAMA_IMAGE ollama serve &
sleep 10

# Pull the model if needed
apptainer exec --nv $OLLAMA_IMAGE ollama pull $OLLAMA_MODEL

# Run analysis on test data
apptainer exec --nv \
  --bind $(pwd):/workspace \
  $OLLAMA_IMAGE \
  python3 analyze_with_ollama.py test_data/TestAgent --model $OLLAMA_MODEL
```

### Expected Output

After analysis completes, you should see:

```
test_data/TestAgent/
├── call_001/
│   └── call_001.vtt
├── call_002/
│   └── call_002.vtt
├── analysis_results.json          # NEW: Consolidated scores for all calls
└── analysis_report.md              # NEW: Human-readable report
```

The `analysis_results.json` will contain detailed scores for each call, and `analysis_report.md` will provide a formatted summary with reasoning.

## Purpose

These test files allow you to:
1. Verify the analysis pipeline is working correctly
2. Validate scoring criteria without processing real call data
3. Test different quality scenarios (high vs. low performance)
4. Confirm output file generation (JSON and Markdown reports)
5. Debug issues without consuming GPU resources on full datasets
