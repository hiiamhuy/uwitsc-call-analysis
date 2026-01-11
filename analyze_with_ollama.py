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
DEFAULT_MODEL = "deepseek-r1:32b"
DEFAULT_THRESHOLD = 75

PROMPT_TEMPLATE = """Analyze this customer service call transcription and provide a detailed scoring breakdown based on the following criteria:

1. NetID obtained within 120 seconds (Max 10 points)
2. Issue resolution (Max 15 points)
3. Quality of instructions provided (Max 15 points)
4. Use of Zoom for verification (Max 5 points)
5. Keeping confidential information confidential until verification (Max 7 points)
6. Overall technical support quality (Max 48 points)

CRITICAL INSTRUCTIONS:
- Read the entire transcription word by word.
- Award all 5 points for criterion 4 if the agent mentions Zoom verification anywhere.
- Give agents the credit they deserve; deduct points only for clear failures.
- Focus scoring on observed actions rather than hypothetical improvements.
- Full completion of all tasks can merit a score of 95 or higher.

Transcription to analyze:
{transcription}

Respond in VALID JSON format with the following keys:
- 'score_netid': Score for NetID acquisition (0-10)
- 'score_resolution': Score for issue resolution (0-15)
- 'score_instruction': Score for instruction quality (0-15)
- 'score_zoom': Score for Zoom verification usage (0-5)
- 'score_confidentiality': Score for confidentiality (0-7)
- 'score_tech_quality': Score for technical support quality (0-48)
- 'total_score': Sum of all scores (0-100)
- 'reasoning': A detailed analysis justifying the scores, explicitly addressing any points deducted."""


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


def call_ollama(model: str, prompt: str) -> Dict[str, Any]:
    """Call Ollama and return the parsed JSON response."""
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

    # Default fallback values
    result = {
        "score_netid": 0,
        "score_resolution": 0,
        "score_instruction": 0,
        "score_zoom": 0,
        "score_confidentiality": 0,
        "score_tech_quality": 0,
        "total_score": 0,  # Will be mapped to 'score' for compatibility
        "reasoning": raw_reply or "Analysis failed",
    }

    try:
        start = raw_reply.index("{")
        end = raw_reply.rindex("}") + 1
        parsed = json.loads(raw_reply[start:end])
        
        if isinstance(parsed, dict):
            # Update result with parsed values, keeping defaults if missing
            for key in result.keys():
                if key in parsed:
                    result[key] = parsed[key]
            
            # Handle potential nested reasoning structure (legacy handling)
            reasoning = result.get("reasoning")
            if isinstance(reasoning, dict):
                 print(f"  Warning: Received nested dict structure in reasoning field: {reasoning}")
                 # functionality to extract score from nested dict is deprecated with new schema, 
                 # but we keep simple string extraction
                 result["reasoning"] = str(reasoning)

    except (ValueError, json.JSONDecodeError) as exc:
        print(f"  Warning: Failed to parse JSON response: {exc}")
        print(f"  Raw reply: {raw_reply[:200]}...")
        
    return result


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
        analysis_result = call_ollama(model, prompt)
    except requests.RequestException as exc:
        print(f"  Ollama request for {vtt_file.name} failed: {exc}")
        return None

    # Merge file metadata with analysis results
    return {
        "audio_file": discover_audio_name(vtt_file),
        "transcription_file": vtt_file.name,
        **analysis_result,
        "score": analysis_result.get("total_score", 0), # Backwards compatibility
        "transcription_preview": transcription[:200] + ("..." if len(transcription) > 200 else ""),
    }


def discover_audio_name(vtt_file: Path) -> str:
    candidates = [vtt_file.with_suffix(ext) for ext in (".wav", ".mp3", ".m4a", ".flac", ".ogg")]
    for candidate in candidates:
        if candidate.exists():
            return candidate.name
    return vtt_file.stem


def generate_markdown_report(folder: Path, results: Dict[str, Dict[str, Any]]) -> None:
    """Generate a readable Markdown summary of the analysis results."""
    report_path = folder / "analysis_report.md"
    
    lines = [
        "# Call Analysis Report",
        f"\n**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Calls Analyzed:** {len(results)}",
        "\n## Summary Table",
        "\n| File | Score | Reasoning |",
        "|---|---|---|",
    ]
    
    for filename, data in results.items():
        score = data.get("total_score", 0)
        # Truncate reasoning for table
        reasoning = str(data.get("reasoning", "")).replace("\n", " ")
        short_reasoning = (reasoning[:100] + "...") if len(reasoning) > 100 else reasoning
        lines.append(f"| {filename} | {score} | {short_reasoning} |")
        
    lines.append("\n## Detailed Analysis")
    
    for filename, data in results.items():
        lines.append(f"\n### {filename}")
        lines.append(f"\n**Audio Source:** `{data.get('audio_file', 'Unknown')}`")
        lines.append(f"**Total Score:** {data.get('total_score', 0)} / 100")
        
        lines.append("\n**Score Breakdown:**")
        lines.append(f"- NetID Acquisition: {data.get('score_netid', 0)}/10")
        lines.append(f"- Issue Resolution: {data.get('score_resolution', 0)}/15")
        lines.append(f"- Instructions: {data.get('score_instruction', 0)}/15")
        lines.append(f"- Zoom Usage: {data.get('score_zoom', 0)}/5")
        lines.append(f"- Confidentiality: {data.get('score_confidentiality', 0)}/7")
        lines.append(f"- Technical Quality: {data.get('score_tech_quality', 0)}/48")
        
        lines.append("\n**Reasoning:**")
        lines.append(f"{data.get('reasoning', 'No reasoning provided')}")
        lines.append("\n---")
        
    try:
        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Generated Markdown report at {report_path}")
    except OSError as e:
        print(f"Failed to write markdown report: {e}")


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
    
    # Generate human-readable report
    generate_markdown_report(folder, results)
    
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
