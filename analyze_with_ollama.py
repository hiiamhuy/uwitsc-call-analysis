#!/usr/bin/env python3
"""Ollama-based quality analysis for call transcripts."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests  # type: ignore
except ImportError as exc:  # pragma: no cover - runtime validation
    raise SystemExit(
        "The requests package is required. Run inside the ollama container."
    ) from exc

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_THRESHOLD = 75

PROMPT_TEMPLATE = """Analyze this customer service call transcription and provide a score from 0-100 based on the following criteria:
1. NetID obtained within 120 seconds (10 points)
2. Issue resolution (15 points)
3. Quality of instructions provided (15 points)
4. Use of Zoom for verification (5 points)
5. Keeping confidential information confidential until verification (7 points)
6. Overall technical support quality (48 points)

CRITICAL INSTRUCTIONS:
- Read the entire transcription word by word
- Award all 5 points for criterion 4 if the agent mentions Zoom verification anywhere
- Give agents the credit they deserve; deduct points only for clear failures
- Focus scoring on observed actions rather than hypothetical improvements
- Full completion of all tasks can merit a score of 95 or higher

Transcription to analyze:
{transcription}

Respond in JSON with keys 'score' (integer 0-100) and 'reasoning' (string summarising the rationale and explicitly addressing Zoom usage)."""


def wait_for_ollama(max_wait: int = 180, model: str = DEFAULT_MODEL) -> bool:
    """Poll the Ollama server until the requested model is ready."""
    print("Waiting for Ollama server...")
    server_ready = False

    for second in range(max_wait):
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        except requests.RequestException:
            pass
        else:
            if response.status_code == 200:
                if not server_ready:
                    print("  Server is online")
                    server_ready = True
                models = response.json().get("models", [])
                available = {model_info.get("name") for model_info in models}
                if model in available:
                    print(f"  Model '{model}' detected")
                    return True
                if second % 15 == 0:
                    print(f"  Still waiting for model '{model}' (found: {sorted(available)})")
        time.sleep(1)

    print("Proceeding without explicit confirmation that the model is ready")
    return False


def extract_transcription_text(vtt_path: Path) -> str:
    raw_text = vtt_path.read_text(encoding="utf-8")
    lines = []
    for line in raw_text.splitlines():
        if "-->" in line:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("WEBVTT"):
            continue
        lines.append(stripped)
    return " ".join(lines)


def call_ollama(model: str, prompt: str) -> Tuple[int, str]:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.9},
        },
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()
    raw_reply = payload.get("response", "")

    score, reasoning = 50, raw_reply or "Analysis failed"
    try:
        start = raw_reply.index("{")
        end = raw_reply.rindex("}") + 1
        parsed = json.loads(raw_reply[start:end])
        if isinstance(parsed, dict):
            score = int(parsed.get("score", score))
            reasoning = parsed.get("reasoning", reasoning)
            # If reasoning field contains nested structure, log warning and extract
            if isinstance(reasoning, dict):
                print(f"  Warning: Received nested dict structure in reasoning field: {reasoning}")
                score = int(reasoning.get("score", score))
                reasoning = reasoning.get("reasoning", str(reasoning))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"  Warning: Failed to parse JSON response: {exc}")
    return score, reasoning


def analyze_transcription_file(vtt_file: Path, model: str) -> Optional[Dict[str, Any]]:
    try:
        transcription = extract_transcription_text(vtt_file)
    except OSError as exc:
        print(f"  Failed to read {vtt_file}: {exc}")
        return None

    if not transcription.strip():
        print(f"  Skipping {vtt_file.name}: empty transcript")
        return None

    prompt = PROMPT_TEMPLATE.format(transcription=transcription)

    try:
        score, reasoning = call_ollama(model, prompt)
    except requests.RequestException as exc:
        print(f"  Ollama request for {vtt_file.name} failed: {exc}")
        return None

    return {
        "audio_file": discover_audio_name(vtt_file),
        "transcription_file": vtt_file.name,
        "score": score,
        "reasoning": reasoning,
        "transcription_preview": transcription[:200] + ("..." if len(transcription) > 200 else ""),
    }


def discover_audio_name(vtt_file: Path) -> str:
    candidates = [vtt_file.with_suffix(ext) for ext in (".wav", ".mp3", ".m4a", ".flac", ".ogg")]
    for candidate in candidates:
        if candidate.exists():
            return candidate.name
    return vtt_file.stem


def analyze_speaker_folder(folder: Path, model: str, threshold: int) -> Dict[str, Dict[str, Any]]:
    wait_for_ollama(model=model)

    results: Dict[str, Dict[str, Any]] = {}
    vtt_files = sorted(folder.glob("*.vtt"))
    if not vtt_files:
        print(f"No VTT files found in {folder}")
        return results

    for vtt_file in vtt_files:
        print(f"Analyzing {vtt_file.name}")
        analysis = analyze_transcription_file(vtt_file, model)
        if analysis is None:
            continue
        results[vtt_file.name] = analysis

    if not results:
        print("No transcription analyses were successful")
        return results

    output_path = folder / "analysis_results.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved consolidated results to {output_path}")
    return results


def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze WhisperX VTT files with Ollama")
    parser.add_argument("speaker_folder", type=Path, help="Folder containing VTT transcripts")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help="Score threshold (kept for compatibility; not used directly here)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_cli()
    speaker_folder = args.speaker_folder.expanduser().resolve()
    if not speaker_folder.exists():
        raise SystemExit(f"Speaker folder not found: {speaker_folder}")

    analyze_speaker_folder(speaker_folder, args.model, args.threshold)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
