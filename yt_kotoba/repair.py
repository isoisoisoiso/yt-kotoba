"""Detect and repair Whisper repeat loops.

On long recordings Whisper sometimes gets stuck and emits the same short
phrase for minutes ("既に、既に、既に、…"), silently dropping the real speech.
This module finds those spans and re-transcribes only the affected audio with
`condition_on_previous_text=False`, which breaks the feedback loop.

Segments use the transcript shape from transcribe.py: {text, offset(ms), duration(ms)}.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .transcribe import transcribe_audio

PAD_MS = 10_000
SAME_TEXT_RUN = 3  # a segment identical to the previous 3 in a row counts as a loop


def _end(seg: dict[str, Any]) -> int:
    return int(seg["offset"]) + int(seg["duration"])


def is_loop_text(text: str) -> bool:
    """True if one short phrase repeats back-to-back for most of the text."""
    t = re.sub(r"\s", "", text)
    if len(t) < 20:
        return False
    for n in range(1, 9):
        m = re.search(r"(.{" + str(n) + r"}?)\1{5,}", t)
        if m and len(m.group(0)) >= len(t) * 0.5:
            return True
    return False


def find_loop_spans(segments: list[dict[str, Any]], pad_ms: int = PAD_MS) -> list[tuple[int, int]]:
    """Return merged (start_ms, end_ms) spans that look like repeat loops, padded on both sides."""
    bad: list[int] = []
    prev = None
    run = 0
    for i, seg in enumerate(segments):
        text = seg["text"].strip()
        run = run + 1 if text and text == prev else 0
        prev = text
        if is_loop_text(text) or run >= SAME_TEXT_RUN:
            bad.append(i)

    spans: list[list[int]] = []
    for i in bad:
        start = max(0, int(segments[i]["offset"]) - pad_ms)
        end = _end(segments[i]) + pad_ms
        if spans and start <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
    return [(a, b) for a, b in spans]


def _cut_audio(audio_path: Path, start_ms: int, end_ms: int, out_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to repair transcripts but was not found in PATH.")
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-y",
            "-ss", f"{start_ms / 1000:.3f}", "-to", f"{end_ms / 1000:.3f}",
            "-i", str(audio_path), "-ac", "1", "-ar", "16000", str(out_path),
        ],
        check=True,
    )


def repair_transcript(
    transcript: dict[str, Any],
    audio_path: Path,
    lang: str = "ja",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-transcribe loop spans. Returns `(transcript, report)`.

    The report lists every span that was redone and whether a loop still
    remains there afterwards (then a human should listen to that part).
    """
    segments = transcript.get("segments", [])
    spans = find_loop_spans(segments)
    report: dict[str, Any] = {"repaired": [], "detected_spans": len(spans)}
    if not spans:
        return transcript, report

    out: list[dict[str, Any]] = []
    cursor = 0
    with tempfile.TemporaryDirectory(prefix="yt_kotoba_repair_") as tmp:
        clip = Path(tmp) / "span.wav"
        for start, end in spans:
            out += [s for s in segments if int(s["offset"]) >= cursor and _end(s) <= start]
            _cut_audio(Path(audio_path), start, end, clip)
            redo = transcribe_audio(clip, lang, condition_on_previous_text=False)
            fixed = [
                {"text": s["text"], "offset": int(s["offset"]) + start, "duration": int(s["duration"])}
                for s in redo["segments"]
            ]
            out += fixed
            cursor = end
            report["repaired"].append({
                "start_ms": start,
                "end_ms": end,
                "segments_after": len(fixed),
                "loop_remains": bool(find_loop_spans(fixed, pad_ms=0)),
            })
    out += [s for s in segments if int(s["offset"]) >= cursor and not is_loop_text(s["text"])]

    repaired = dict(transcript)
    repaired["segments"] = out
    repaired["fullText"] = "".join(s["text"] for s in out).strip()
    return repaired, report


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Detect (and optionally repair) Whisper repeat loops")
    parser.add_argument("transcript", help="transcript JSON from yt-kotoba")
    parser.add_argument("--audio", help="audio file; when given, loop spans are re-transcribed")
    parser.add_argument("--lang", default="ja")
    parser.add_argument("--out", help="write the repaired transcript here (default: stdout report only)")
    args = parser.parse_args()

    with open(args.transcript, encoding="utf-8") as f:
        transcript = json.load(f)
    if not args.audio:
        spans = find_loop_spans(transcript.get("segments", []))
        print(json.dumps([{"start_ms": a, "end_ms": b} for a, b in spans]))
        return 0
    repaired, report = repair_transcript(transcript, Path(args.audio), args.lang)
    if args.out:
        Path(args.out).write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
