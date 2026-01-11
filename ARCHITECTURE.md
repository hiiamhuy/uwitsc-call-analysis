# UWITSC Call Analysis Pipeline - Architecture

## Overview

This pipeline processes customer service call audio files through transcription, speaker diarization, and AI-powered quality analysis on the Hyak supercomputer.

## High-Level Flow

```mermaid
flowchart TB
    subgraph Input["Input Data"]
        audio["Audio Files<br/>(wav, mp3, m4a, flac)"]
    end

    subgraph LoginNode["Login Node (Python 3.11)"]
        entry["run_speaker_analysis.sh"]
        orchestrator["submit_slurm.py<br/>SpeakerAnalysisOrchestrator"]
        organize["Result Organization<br/>(score-based sorting)"]
    end

    subgraph GPUNode["GPU Node (SLURM Job per Agent)"]
        subgraph Transcription["Stage 1: Transcription"]
            batch["transcribe_calls.py<br/>(Batch Transcriber)"]
            whisper["whisperx_script.py<br/>(WhisperX large-v2)"]
            diarize["Speaker Diarization<br/>(Pyannote + Keyword Fallback)"]
        end

        subgraph Analysis["Stage 2: Analysis"]
            ollama_server["Ollama Server"]
            analyzer["analyze_with_ollama.py"]
            model["DeepSeek-R1 32B"]
        end
    end

    subgraph Output["Output"]
        vtt["WebVTT Transcripts<br/>(with speaker labels)"]
        json["analysis_results.json"]
        report["analysis_report.md"]
        reviewed["reviewed/<br/>(score > 75)"]
        attention["needs_further_attention/<br/>(score <= 75)"]
    end

    audio --> entry
    entry --> orchestrator
    orchestrator -->|"Creates & Submits<br/>SLURM Jobs"| batch
    batch -->|"For each audio file"| whisper
    whisper --> diarize
    diarize --> vtt
    vtt --> analyzer
    ollama_server --> model
    analyzer --> model
    model --> json
    model --> report
    orchestrator -->|"Monitors Jobs"| organize
    json --> organize
    organize --> reviewed
    organize --> attention
```

## Detailed Component Diagram

```mermaid
flowchart LR
    subgraph Containers["Apptainer Containers"]
        whisperx_sif["whisperx_python.sif<br/>(~9.1 GB)<br/>CUDA 12.2 + WhisperX"]
        ollama_sif["ollama_python.sif<br/>(~14 GB)<br/>Ollama + DeepSeek"]
    end

    subgraph Scripts["Python Scripts"]
        submit["submit_slurm.py"]
        transcribe["transcribe_calls.py"]
        whisperx_py["whisperx_script.py"]
        analyze["analyze_with_ollama.py"]
    end

    subgraph EnvVars["Required Environment"]
        hf["HF_TOKEN"]
        whisperx_img["WHISPERX_IMAGE"]
        ollama_img["OLLAMA_IMAGE"]
    end

    submit -->|"Uses"| whisperx_sif
    submit -->|"Uses"| ollama_sif
    transcribe -->|"Runs inside"| whisperx_sif
    whisperx_py -->|"Runs inside"| whisperx_sif
    analyze -->|"Runs inside"| ollama_sif
    hf --> whisperx_py
    whisperx_img --> submit
    ollama_img --> submit
```

## SLURM Job Flow

```mermaid
sequenceDiagram
    participant User
    participant Shell as run_speaker_analysis.sh
    participant Orch as submit_slurm.py
    participant SLURM
    participant GPU as GPU Node
    participant WhisperX as WhisperX Container
    participant Ollama as Ollama Container

    User->>Shell: ./run_speaker_analysis.sh audio_data
    Shell->>Shell: Load Python 3.11 module
    Shell->>Shell: Validate HF_TOKEN & container paths
    Shell->>Orch: Execute orchestrator

    Orch->>Orch: Discover agent folders

    loop For each agent folder
        Orch->>SLURM: sbatch job_script.sh
        SLURM-->>Orch: Job ID
    end

    loop Monitor jobs (every 3 min)
        Orch->>SLURM: squeue check
        SLURM-->>Orch: Job status
    end

    Note over GPU: Per-Agent SLURM Job

    GPU->>WhisperX: Start transcription phase

    loop For each audio file
        WhisperX->>WhisperX: Load WhisperX model
        WhisperX->>WhisperX: Transcribe audio
        WhisperX->>WhisperX: Speaker diarization
        WhisperX->>WhisperX: Output .vtt file
    end

    GPU->>Ollama: Start analysis phase
    Ollama->>Ollama: ollama serve (start server)
    Ollama->>Ollama: ollama pull deepseek-r1:32b

    loop For each .vtt file
        Ollama->>Ollama: Extract text from VTT
        Ollama->>Ollama: Score with DeepSeek
        Ollama->>Ollama: Write analysis_results.json
    end

    SLURM-->>Orch: All jobs complete
    Orch->>Orch: Organize results by score threshold
    Orch-->>User: Pipeline complete
```

## Scoring System

```mermaid
pie showData
    title "Call Quality Scoring (100 points total)"
    "Overall Technical Support Quality" : 48
    "Issue Resolution" : 15
    "Quality of Instructions" : 15
    "NetID within 120 sec" : 10
    "Confidentiality Protection" : 7
    "Zoom Verification Used" : 5
```

## File Structure After Processing

```mermaid
flowchart TB
    subgraph Before["Before Processing"]
        audio_data["audio_data/"]
        agent1["Darlene/"]
        agent2["Jarrett/"]
        calls1["call1.wav, call2.wav, call3.wav"]
        calls2["call1.wav, call2.wav"]

        audio_data --> agent1
        audio_data --> agent2
        agent1 --> calls1
        agent2 --> calls2
    end

    subgraph After["After Processing"]
        audio_data2["audio_data/"]
        agent1a["Darlene/"]
        results["analysis_results.json<br/>analysis_report.md"]
        reviewed["reviewed/"]
        attention["needs_further_attention/"]
        call_good["call_001/"]
        call_bad["call_002/"]
        good_files[".wav + .vtt + .json"]
        bad_files[".wav + .vtt + .json"]
        logs["logs/"]
        log_files["*_pipeline_*.out<br/>*_pipeline_*.err"]

        audio_data2 --> agent1a
        audio_data2 --> logs
        agent1a --> results
        agent1a --> reviewed
        agent1a --> attention
        reviewed --> call_good
        attention --> call_bad
        call_good --> good_files
        call_bad --> bad_files
        logs --> log_files
    end

    Before -->|"Pipeline Execution"| After
```

## Speaker Detection Logic

```mermaid
flowchart TD
    start["Audio Transcribed"]
    diarize{"GPU Diarization<br/>Available?"}
    pyannote["Pyannote Speaker<br/>Identification"]
    keyword["Keyword-Based<br/>Classification"]

    subgraph Keywords["Keyword Detection"]
        agent_kw["AGENT_KEYWORDS:<br/>service, support, help,<br/>technical, uw, zoom, verify"]
        user_kw["USER_PHRASES:<br/>my netid is, i'll open zoom,<br/>that worked"]
        short["SHORT_RESPONSES:<br/>yes, no, ok, exactly"]
    end

    label["Label Speakers:<br/>[Agent] or [user]"]
    output["WebVTT with<br/>Speaker Labels"]

    start --> diarize
    diarize -->|"Yes (HF_TOKEN)"| pyannote
    diarize -->|"No"| keyword
    pyannote --> label
    keyword --> agent_kw
    keyword --> user_kw
    keyword --> short
    agent_kw --> label
    user_kw --> label
    short --> label
    label --> output
```

## Quick Reference

| Component | Location | Purpose |
|-----------|----------|---------|
| `run_speaker_analysis.sh` | Root | Entry point, environment setup |
| `submit_slurm.py` | Root | Job orchestration & result organization |
| `transcribe_calls.py` | Root | Batch audio transcription |
| `whisperx_script.py` | Root | Single-file transcription & diarization |
| `analyze_with_ollama.py` | Root | LLM-based quality scoring |
| `whisperx_python.sif` | Container | WhisperX + CUDA environment |
| `ollama_python.sif` | Container | Ollama + DeepSeek model |
