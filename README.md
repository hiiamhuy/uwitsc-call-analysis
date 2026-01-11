# UWITSC AI Integration - Audio Transcription and Analysis

This pipeline processes customer service call audio files through automated transcription, speaker diarization, and quality analysis using WhisperX and Ollama, via the UW's Hyak supercomputer.

## Table of Contents

- [File Structure](#file-structure)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Step 1: Upload Call Files](#step-1-upload-call-files-to-hyak)
  - [Step 2: Set Up Environment](#step-2-set-up-environment)
  - [Step 3: Run the Pipeline](#step-3-run-the-pipeline)
  - [Step 4: Monitor Progress](#step-4-monitor-progress)
  - [Step 5: Review Results](#step-5-review-results)
  - [Step 6: Archive Processed Data](#step-6-archive-processed-data)
- [Advanced Usage](#advanced-usage)
  - [Manual Execution](#manual-execution)
  - [Standalone Testing](#standalone-testing)
- [Configuration](#configuration)
- [Output Files](#output-files)
- [Requirements](#requirements)
- [Troubleshooting](#troubleshooting)
- [Testing & Utilities](#testing--utilities)


## File Structure

```
home-directory/
├── submit_slurm.py                          # manages/submits SLURM jobs, one per agent
├── transcribe_calls.py                      # finds audio files of a given agent and calls WhisperX (large-v2 model) on them
├── whisperx_script.py                       # speech-to-text on each individual audio file with speaker diarization and timestamps
├── analyze_with_ollama.py                   # LLM-based scoring using deepseek-r1:32b model via Ollama
├── run_speaker_analysis.sh                  # shell script to run the above .py files via the command line
├── ollama_python.def                        # Apptainer definition for Ollama container
├── whisperx_python.def                      # Apptainer definition for WhisperX container
└── audio_data/                              # input/output directory
    ├── [AgentName]/                         # speaker folders, named after call agents
    │   ├── analysis_report.md               # human-readable markdown summary of all analyses
    │   ├── needs_further_attention/         # calls analyzed and with score ≤ 75
    │   │   └── [AgentID]/                   # individual call folders
    │   │       ├── [AgentID].wav            # original audio file
    │   │       ├── [AgentID].vtt            # transcription with speaker labels
    │   │       └── analysis_results.json    # quality analysis results
    │   └── reviewed/                        # calls analyzed and with score > 75
    │       └── [CallID]/                    # individual call folders
    │           ├── [CallID].wav             # original audio file
    │           ├── [CallID].vtt             # transcription with speaker labels
    │           └── analysis_results.json    # quality analysis results
    └── logs/                                # SLURM job logs
```

## Quick Start

### Prerequisites

1. Access to UW Hyak supercomputer
2. Hugging Face account and token ([get one here](https://huggingface.co/settings/tokens))
3. Container images built (see [Hyak_Setup.md](Hyak_Setup.md) for full installation instructions)

### Step 1: Upload Call Files to Hyak

1. Download call files from Engage (one .zip file per agent)
2. Unzip and rename folders to use just the agent's first name
3. Transfer to Hyak using Globus (see [Hyak team's Globus docs](https://hyak.uw.edu/docs/storage/gui#globus))
4. Ensure files are in the `audio_data/[AgentName]/` structure (see [File Structure](#file-structure) above)

### Step 2: Set Up Environment

**One-time setup** - Add to your `~/.bashrc`:

```bash
# Hugging Face token for WhisperX
export HF_TOKEN=your_hugging_face_token_here

# Container image paths
export WHISPERX_IMAGE=/mmfs1/gscratch/fellows/$UWNETID/whisperx_python.sif
export OLLAMA_IMAGE=/mmfs1/gscratch/fellows/$UWNETID/ollama_python.sif

# Cache directories (to avoid filling up home directory)
export APPTAINER_CACHEDIR=/mmfs1/gscratch/fellows/$UWNETID/apptainer-cache
export APPTAINER_TMPDIR=/mmfs1/gscratch/fellows/$UWNETID/apptainer-tmp
export OLLAMA_MODELS=/mmfs1/gscratch/fellows/$UWNETID/ollama
export XDG_CACHE_HOME=/mmfs1/gscratch/fellows/$UWNETID/xgd-cache
```

Then reload your profile:
```bash
source ~/.bashrc
```

### Step 3: Run the Pipeline

#### Option A: Command Line (SSH)

**Simple execution** (uses default threshold of 75):
```bash
./run_speaker_analysis.sh audio_data
```

**With custom threshold** (e.g., 80):
```bash
./run_speaker_analysis.sh audio_data 80
```

**With custom model and memory:**
```bash
./run_speaker_analysis.sh --ollama-model deepseek-r1:32b --mem 32 audio_data 75
```

### Step 4: Monitor Progress

Check SLURM job status:
```bash
squeue -u $USER
```

View logs in real-time:
```bash
tail -f audio_data/logs/slurm-*.out
```

### Step 5: Review Results

Results are organized by score:
- **needs_further_attention/** - Calls with score ≤ threshold
- **reviewed/** - Calls with score > threshold

Each agent folder contains:
- `analysis_report.md` - Human-readable markdown summary with detailed score breakdowns

Each call folder contains:
- `[CallID].wav` - Original audio file
- `[CallID].vtt` - Transcription with speaker labels
- `analysis_results.json` - Quality analysis with detailed component scores

### Step 6: Archive Processed Data

> **IMPORTANT**: Any agent folders left in `audio_data/` will be reprocessed the next time you run the pipeline. This wastes compute resources and time.

After reviewing your results, move the processed agent folders to your Globus-connected OneDrive for archival:

1. Open [Globus File Manager](https://app.globus.org/file-manager)
2. Set your source endpoint to your Hyak storage location
3. Set your destination endpoint to your OneDrive collection
4. Navigate to `audio_data/` on the source side
5. Select the agent folders you want to archive (e.g., `David/`, `Sarah/`)
6. Transfer the folders to your OneDrive

After the transfer completes, delete the folders from Hyak to prevent reprocessing:
1. In Globus File Manager, navigate to `audio_data/` on your Hyak endpoint
2. Check the boxes next to the agent folders you want to remove
3. Click **"Delete Selected"**

**Tip**: Keep the `audio_data/logs/` folder on Hyak for troubleshooting, but archive and delete the agent data folders after each batch.

## Advanced Usage

### Manual Execution
```bash
# Run orchestrator directly (requires HF_TOKEN and container paths)
python3 submit_slurm.py \
  audio_data \
  --hf-token "$HF_TOKEN" \
  --whisperx-image /path/to/whisperx_python.sif \
  --ollama-image /path/to/ollama_python.sif \
  --threshold 75
```

### Standalone Testing
```bash
# Test transcription only
python3 transcribe_calls.py audio_data/David
```

## Configuration

### Environment Variables

#### Required Variables
- **`HF_TOKEN`**: Hugging Face token for WhisperX model access
  - **How to get**: Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
  - **How to set**: `export HF_TOKEN=your_token_here`
  - **Security**: Never commit this token to version control
  - **Validation**: The script will check if this variable is set before running

#### Optional Variables
- **`WHISPERX_IMAGE`**: Path to the WhisperX Apptainer image (default: none)
- **`OLLAMA_IMAGE`**: Path to the Ollama Apptainer image (default: none)
- **`OLLAMA_MODEL`**: Name of the preloaded Ollama model (default: `deepseek-r1:32b`)
- **`CUDA_VISIBLE_DEVICES`**: GPU device selection (default: auto-detect)

**Note**: The Ollama server address is hardcoded to `127.0.0.1:11434` in the analysis script and is not configurable via environment variables.

#### Setting Environment Variables Permanently
To avoid setting the token every time you log in, add it to your shell profile:
```bash
# Add to ~/.bashrc or ~/.profile
echo 'export HF_TOKEN=your_token_here' >> ~/.bashrc
source ~/.bashrc
```

### Hyak Storage & Cache Locations
Hyak home directories (`/mmfs1/home/$UWNETID`) are capped at 10 GB, so place
container caches and Ollama model files on gscratch before running the
pipeline. Create persistent directories once:

```bash
mkdir -p /mmfs1/gscratch/fellows/$UWNETID/{ollama,apptainer-cache,apptainer-tmp,xgd-cache}
mv ~/.ollama ~/.ollama.bak && ln -s /mmfs1/gscratch/fellows/$UWNETID/ollama ~/.ollama
```

Append these exports to your shell profile (or SLURM wrapper) so every session
and batch job uses the redirected caches:

```bash
export APPTAINER_CACHEDIR=/mmfs1/gscratch/fellows/$UWNETID/apptainer-cache
export APPTAINER_TMPDIR=/mmfs1/gscratch/fellows/$UWNETID/apptainer-tmp
export OLLAMA_MODELS=/mmfs1/gscratch/fellows/$UWNETID/ollama
export XDG_CACHE_HOME=/mmfs1/gscratch/fellows/$UWNETID/xgd-cache
export PIP_CACHE_DIR=$XDG_CACHE_HOME/pip
export HF_HOME=$XDG_CACHE_HOME/huggingface
export TRANSFORMERS_CACHE=$HF_HOME/transformers
```

Reload the profile (`source ~/.bashrc`) and confirm the directories are
growing on gscratch with `du -sh /mmfs1/gscratch/fellows/$UWNETID/*` while
`~/.ollama` remains a lightweight symlink.

### Default Values

The pipeline uses the following default values for resource allocation and scoring:

| Parameter | Default Value | Description |
|-----------|--------------|-------------|
| Score Threshold | 75 | Calls at or above go to `reviewed/`, below go to `needs_further_attention/` |
| GPU Partition | `gpu-rtx6k` | SLURM partition for GPU jobs |
| Job Time Limit | 2 hours | Maximum runtime per job |
| Memory | 32GB | RAM allocated per job |
| GPUs | 1 | Number of GPUs per job |
| CPUs | 4 | Number of CPU cores per job |
| WhisperX Model | `large-v2` | Speech-to-text model |
| Ollama Model | `deepseek-r1:32b` | LLM for quality analysis |

### Advanced Configuration

#### Command-Line Arguments

The `submit_slurm.py` orchestrator accepts additional arguments for customizing job resources:

```bash
python3 submit_slurm.py audio_data \
  --hf-token "$HF_TOKEN" \
  --whisperx-image /path/to/whisperx_python.sif \
  --ollama-image /path/to/ollama_python.sif \
  --threshold 80 \
  --partition gpu-rtx6k \
  --gpus 1 \
  --mem 32 \
  --time-limit 02:00:00 \
  --account your_account \
  --qos your_qos
```

**Available arguments:**
- `--threshold` - Score threshold for categorization (default: 75)
- `--partition` - SLURM partition to use (default: gpu-rtx6k)
- `--gpus` - Number of GPUs per job (default: 1)
- `--mem` - Memory in GB (default: 81)
- `--time-limit` - Max job runtime in HH:MM:SS format (default: 02:00:00)
- `--account` - SLURM account name (optional)
- `--qos` - SLURM quality of service (optional, auto-determined if not set)

#### Transcription Options

The `transcribe_calls.py` script supports:
- `--device` - Compute device (default: "cuda")
- `--output-format` - Output format (only "vtt" supported)
- `--whisperx-script` - Custom path to whisperx_script.py
- `--extra-args` - Additional arguments to forward to whisperx_script.py

The `whisperx_script.py` supports:
- `--diarization` - Force enable speaker diarization
- `--no-diarization` - Disable speaker diarization
- `--output-dir` - Custom output directory

### Container Images
- Build `whisperx_python.sif` and `ollama_python.sif` using the definitions in this repository.
- Populate `container_artifacts/` with offline wheels and the Ollama tarball before invoking `apptainer build`.
- Provide the resulting `.sif` paths via `WHISPERX_IMAGE`/`OLLAMA_IMAGE` (or the matching CLI flags) when launching the pipeline.


### Prompting

To change the prompt Ollama uses in analyzing and grading calls, go to [`analyze_with_ollama.py`](analyze_with_ollama.py) and modify the `prompt` variable in the `analyze_transcription_file()` function. The current prompt evaluates calls based on:

- NetID obtained within 120 seconds (10 points)
- Issue resolution (15 points) 
- Quality of instructions provided (15 points)
- Use of Zoom for verification (5 points)
- Keeping confidential information secure (7 points)
- Overall technical support quality (48 points)

You can customize the scoring criteria, point values, or add new evaluation metrics by editing the prompt text. 

### Speaker Diarization

To improve or change keywords used to differentiate between speakers and call agents, go to [`whisperx_script.py`](whisperx_script.py) and modify the following lists:

**Agent Keywords:**
- `AGENT_KEYWORDS` - Main agent identification keywords (lines 26-30)

**User Keywords:**
- `USER_PHRASES` - Specific user phrases indicating customer speech (lines 33-55)
- `SHORT_RESPONSES` - Common user responses like "yes", "no", "ok" (lines 57-74)

You can also modify the user detection logic in the `analyze_sentence_speaker()` function (starting at line 177) to improve accuracy in identifying user responses and conversational patterns. 

## Output Files

### VTT Files
WebVTT format with speaker labels and timestamps:
```
WEBVTT

00:00:01.516 --> 00:00:04.605
[Agent] UW-IT Service Center, how can I help you?

00:00:04.605 --> 00:00:06.571
[user] Hello! I have a problem with my password.
```

### Analysis Results (JSON)
JSON format with detailed scoring breakdown:
```json
{
  "call_transcription.vtt": {
    "audio_file": "<audio_file>.wav",
    "transcription_file": "<transcription_file>.vtt",
    "score_netid": 10,
    "score_resolution": 15,
    "score_instruction": 14,
    "score_zoom": 5,
    "score_confidentiality": 7,
    "score_tech_quality": 47,
    "total_score": 98,
    "score": 98,
    "reasoning": "The agent successfully obtained the NetID within 120 seconds...",
    "transcription_preview": "First 200 characters of the transcription..."
  }
}
```

### Analysis Report (Markdown)
Human-readable summary generated alongside JSON results:
- **File**: `analysis_report.md` (created in each agent folder after analysis)
- **Contains**:
  - Summary table of all calls with scores and truncated reasoning
  - Detailed breakdown for each call with individual component scores:
    - NetID Acquisition (0-10 points)
    - Issue Resolution (0-15 points)
    - Instructions Quality (0-15 points)
    - Zoom Usage (0-5 points)
    - Confidentiality (0-7 points)
    - Technical Quality (0-48 points)
  - Full LLM reasoning for each analysis
- **Automatically generated** after analysis completes

## Requirements

### Software Dependencies
- Python 3.9+
- Apptainer/Singularity
- SLURM job scheduler
- CUDA-capable GPU
- Hugging Face token

### Container Images
- `whisperx_python.sif`: WhisperX transcription environment
- `ollama_python.sif`: Ollama LLM analysis environment

### System Requirements
- Access to UW Hyak cluster
- GPU partition access
- Sufficient storage for audio files and outputs

## Troubleshooting

### Common Issues

#### 1. **Missing HF Token Error**
```
Error: HF_TOKEN environment variable is required
Please set it with: export HF_TOKEN=your_token_here
```
**Solution**: Set your Hugging Face token as an environment variable:
```bash
export HF_TOKEN=your_actual_token_here
```

#### 2. **Token Validation Issues**
- **Check if token is set**: `echo $HF_TOKEN`
- **Verify token format**: Should start with `hf_`
- **Test token**: Visit [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) to verify

#### 3. **GPU Availability**
- Check `hyakalloc` output for available GPUs
- Verify SLURM partition availability: `sinfo -p gpu-rtx6k`

#### 4. **Container Issues**
- Verify container images exist: `ls -la *.sif`
- Check container permissions: `ls -la ollama_python.sif whisperx_python.sif`

#### 5. **Environment Variable Not Persisting**
If your token disappears after logging out:
```bash
# Add to your shell profile
echo 'export HF_TOKEN=your_token_here' >> ~/.bashrc
source ~/.bashrc
```
4. **File Permissions**: Ensure write access to output directories

### Logs
- SLURM job logs: [`audio_data/logs/`](#file-structure)
- Transcription errors: Check job output files
- Analysis failures: Verify Ollama server connectivity

## Testing & Utilities

The repository includes several testing and utility scripts to help verify your setup:

### GPU Testing
Test GPU/CUDA availability before running the pipeline:
```bash
python3 test_gpu_access.py
```
This simple script verifies that PyTorch can detect and access CUDA-enabled GPUs.

### Ollama Health Check
Verify the Ollama container and model are working correctly:
```bash
./test_llama.sh
```
This script:
- Starts the Ollama server in a container
- Tests connectivity to the Ollama API
- Verifies the model can generate responses
- Reports server status and model availability

### Pre-download Models
Download the Ollama model before running analysis jobs to avoid timeouts:
```bash
sbatch download_model.slurm
```
**Note**: Edit `download_model.slurm` to update the following before using:
- Line 4: Change `SIF_PATH` to your ollama_python.sif location
- Line 17-18: Update `ACCOUNT` to your SLURM account name
This pre-downloads the ~40GB+ model file, preventing download delays during analysis.

## Credits
Many thanks to Kaichen and Kristen for creating the Apptainer containers and helping me with Hyak, Huy for guiding me through this project, and Jeff and Co. for making this opportunity possible!
