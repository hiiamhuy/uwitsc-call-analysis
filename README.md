# UWITSC AI Integration - Audio Transcription and Analysis

This pipeline processes customer service call audio files through automated transcription, speaker diarization, and quality analysis using WhisperX and Ollama, via the UW's Hyak supercomputer.

## Table of Contents

- [File Structure](#file-structure)
- [Usage](#usage)
  - [Uploading call files to Hyak via Globus](#uploading-call-files-to-hyak-via-globus)
  - [Quick Start](#quick-start)
  - [Manual Execution](#manual-execution)
  - [Standalone Testing](#standalone-testing)
- [Configuration](#configuration)
- [Output Files](#output-files)
- [Requirements](#requirements)
- [Troubleshooting](#troubleshooting)


## File Structure

```
home-directory/
├── submit_slurm.py                          # manages/submits SLURM jobs, one per agent
├── transcribe_calls.py                      # finds audio files of a given agent and calls WhisperX (large-v2 model) on them
├── whisperx_script.py                       # speech-to-text on each individual audio file with speaker diarization and timestamps
├── analyze_with_ollama.py                   # LLM-based scoring using Ollama 3.2
├── run_speaker_analysis.sh                  # shell script to run the above .py files via the command line
├── ollama_python.def                        # Apptainer definition for Ollama container
├── whisperx_python.def                      # Apptainer definition for WhisperX container
└── audio_data/                              # input/output directory
    ├── [AgentName]/                         # speaker folders, named after call agents
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

## Usage

### Uploading call files to Hyak via Globus

1. Download the call files from Engage, one .zip file per agent. Use the agent's first name, as the script will use their first name when transcribing.

2. Unzip those .zip files and rename them to remove the automatic numbering Engage uses. The folder name should just be the first name of the agent.

3. To abide by privacy/data laws and maintain confidentiality, please follow the [Hyak team's Globus documentation](https://hyak.uw.edu/docs/storage/gui#globus) on how to transfer these call files via Globus. Make sure they transfer to the `audio_data` folder (create this on Hyak if it does not already exist).

4. Double-check that the file structure on Hyak follows the one in [File Structure](#file-structure) above.

5. You can now proceed to the [Quick Start](#quick-start) section below to start analysis!

### Quick Start

**Set container image environment variables once (or pass inline as shown below):**
```bash
export WHISPERX_IMAGE=/mmfs1/gscratch/fellows/$UWNETID/whisperx_python.sif
export OLLAMA_IMAGE=/mmfs1/gscratch/fellows/$UWNETID/ollama_python.sif
```

**First, set up your Hugging Face token:**
```bash
# Set your Hugging Face token as an environment variable
export HF_TOKEN=your_hugging_face_token_here

# Verify it's set (optional)
echo "Token set: ${HF_TOKEN:0:10}..."
```

**Then run the complete pipeline:**
```bash
# Run the complete pipeline
WHISPERX_IMAGE=/path/to/whisperx_python.sif \
OLLAMA_IMAGE=/path/to/ollama_python.sif \
./run_speaker_analysis.sh audio_data

# With custom threshold
WHISPERX_IMAGE=/path/to/whisperx_python.sif \
OLLAMA_IMAGE=/path/to/ollama_python.sif \
./run_speaker_analysis.sh audio_data 80
```

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
- **`OLLAMA_MODEL`**: Name of the preloaded Ollama model (default: `llama3.2:3b`)
- **`CUDA_VISIBLE_DEVICES`**: GPU device selection (default: auto-detect)
- **`OLLAMA_HOST`**: Ollama server binding address (default: `127.0.0.1:11434`)

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

### Key Parameters
- **Score Threshold**: Default 75 (calls at or above this score go to [`reviewed/`](#file-structure), below go to [`needs_further_attention/`](#file-structure))
- **GPU Partition**: `gpu-h200` (configurable based on availability)
- **Model**: WhisperX "large-v2" for transcription, Ollama "llama3.2:3b" for analysis
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
- `AGENT_KEYWORDS` list (lines 25-35) - Main agent identification keywords

**User Keywords:**
- `user_phrases` list (lines 136-139, 338-341) - Specific user phrases
- `short_responses` list (lines 147-150, 358-362) - Common user responses like "yes", "no", "ok"
- `question_indicators` list (lines 351-354) - Agent questions that typically get user responses
- `repeat_patterns` list (lines 370-373) - User repeating agent information (Zoom IDs, names, etc.)

You can also modify the user detection logic in the `analyze_sentence_speaker()` function to improve accuracy in identifying user responses and conversational patterns. 

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

### Analysis Results
JSON format with scores and reasoning:
```json
{
  "call_transcription.vtt": {
    "audio_file": "<audio_file>.wav",
    "transcription_file": "<transcription_file>.vtt",
    "score": 98,
    "reasoning": "The agent successfully obtained the NetID within 120 seconds..."
  }
}
```

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
- Verify SLURM partition availability: `sinfo -p gpu-h200`

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

## Credits
Many thanks to Kaichen and Kristen for creating the Apptainer containers and helping me with Hyak, Huy for guiding me through this project, and Jeff and Co. for making this opportunity possible!
