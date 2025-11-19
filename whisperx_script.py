#!/usr/bin/env python3
"""
WhisperX transcription entry point.

This script performs ASR and (optionally) diarization for a single audio
recording, then stores a WebVTT transcript with speaker labels. It is intended
to run inside the `whisperx_python.sif` container where WhisperX and its
dependencies are available.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

try:
    import whisperx  # type: ignore
except ImportError as exc:  # pragma: no cover - handled at runtime in container
    raise SystemExit(
        "WhisperX is required. Run this script inside the whisperx container."
    ) from exc

AGENT_KEYWORDS: tuple[str, ...] = (
    "service",
    "support",
    "help",
    "assistance",
    "technical",
    "customer",
    "agent",
    "representative",
    "specialist",
    "advisor",
    "consultant",
    "uw",
    "service center",
    "help desk",
    "net id",
    "netid",
    "recovery code",
    "verify",
    "zoom",
    "meeting",
    "identity",
    "thank you",
    "have a good",
)

USER_PHRASES: tuple[str, ...] = (
    "my netid is",
    "i'll open zoom",
    "that worked",
    "no that's it",
    "take care",
)

SHORT_RESPONSES: tuple[str, ...] = (
    "yes",
    "no",
    "ok",
    "okay",
    "yeah",
    "sure",
    "right",
    "i can",
    "i will",
    "i have",
    "i do",
    "i am",
    "that's right",
    "exactly",
    "correct",
    "true",
    "false",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe a single audio file with WhisperX")
    parser.add_argument("audio_file", type=Path, help="Path to the audio file to transcribe")
    parser.add_argument(
        "--device",
        default="cuda",
        help="Execution device for WhisperX (default: cuda)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for transcription output (defaults to audio directory)",
    )
    parser.add_argument(
        "--diarization",
        action="store_true",
        help="Force diarization (enabled by default when supported)",
    )
    parser.add_argument(
        "--no-diarization",
        action="store_true",
        help="Disable diarization even if models are available",
    )
    return parser.parse_args()


def load_diarization_model(device: str):
    if device == "cpu":
        # Pyannote diarization requires GPU; skip politely.
        return None
    try:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            return None
        return whisperx.DiarizationPipeline(use_auth_token=hf_token, device=device)
    except Exception:
        return None


def select_agent_speaker(segments: Iterable[dict]) -> Optional[str]:
    for segment in segments:
        speaker = segment.get("speaker")
        text = (segment.get("text") or "").lower()
        if speaker and any(keyword in text for keyword in AGENT_KEYWORDS):
            return speaker
    return None


def classify_segment(
    segment: dict,
    agent_name: str,
    agent_speaker: Optional[str],
) -> str:
    text = (segment.get("text") or "").strip()
    speaker = segment.get("speaker")
    lower_text = text.lower()

    if any(keyword in lower_text for keyword in AGENT_KEYWORDS):
        return agent_name
    if any(phrase in lower_text for phrase in USER_PHRASES):
        return "user"
    if len(lower_text) <= 30 and any(lower_text.startswith(resp) for resp in SHORT_RESPONSES):
        return "user"
    if speaker and speaker == agent_speaker:
        return agent_name
    if speaker and agent_speaker is None:
        return agent_name
    return "user"


def build_vtt_content(segments: Iterable[dict], agent_name: str) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        start = segment.get("start")
        end = segment.get("end")
        text = (segment.get("text") or "").strip()
        speaker = segment.get("speaker_label") or segment.get("speaker")
        if start is None or end is None or not text:
            continue
        start_ts = seconds_to_timestamp(float(start))
        end_ts = seconds_to_timestamp(float(end))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(f"[{speaker or agent_name}] {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def seconds_to_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remaining:06.3f}"


def label_segments(segments: list[dict], agent_name: str) -> list[dict]:
    agent_speaker = select_agent_speaker(segments)
    labeled_segments: list[dict] = []
    for segment in segments:
        speaker_label = classify_segment(segment, agent_name, agent_speaker)
        labeled_segments.append({**segment, "speaker_label": speaker_label})
    return labeled_segments


def main() -> None:
    args = parse_args()

    audio_file: Path = args.audio_file.expanduser().resolve()
    if not audio_file.exists():
        raise SystemExit(f"Audio file not found: {audio_file}")

    agent_name = audio_file.parent.name
    output_dir = (args.output_dir or audio_file.parent).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing: {audio_file}")
    print(f"Agent name: {agent_name}")
    print(f"Using device: {args.device}")

    model = whisperx.load_model("large-v2", args.device, compute_type="float16" if args.device != "cpu" else "float32")
    audio = whisperx.load_audio(str(audio_file))

    result = model.transcribe(audio, batch_size=16)
    segments = result.get("segments", [])

    diarization_allowed = not args.no_diarization
    diarization_requested = args.diarization or not args.no_diarization
    diarize_segments = None

    if diarization_requested and diarization_allowed:
        diarization_model = load_diarization_model(args.device)
        if diarization_model is not None:
            print("Running diarization...")
            diarize_segments = diarization_model(audio, min_speakers=1, max_speakers=2)
            result = whisperx.assign_word_speakers(diarize_segments, result)

    if diarize_segments is None:
        print("Diarization unavailable; falling back to keyword heuristics")

    labeled_segments = label_segments(result.get("segments", []), agent_name)
    vtt_content = build_vtt_content(labeled_segments, agent_name)

    output_path = output_dir / f"{audio_file.stem}.vtt"
    output_path.write_text(vtt_content, encoding="utf-8")
    print(f"Saved transcription to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
