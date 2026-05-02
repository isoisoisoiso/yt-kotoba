"""Convert raw transcript JSON into a packed Markdown that's optimized for LLM reading.

Idea borrowed from browser-use's video-use: instead of feeding the LLM raw
seconds-resolution segments, group into phrase blocks split on long silences
and label each block with start time. Result: ~5-10x shorter context, ~same
information for content-generation tasks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _format_ts(ms: int) -> str:
    s = ms // 1000
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def pack_transcript(
    transcript: dict[str, Any],
    silence_threshold_ms: int = 1500,
    block_target_chars: int = 240,
) -> str:
    """Group segments into phrase blocks. Returns Markdown."""
    segments = transcript.get("segments", [])
    if not segments:
        return "# Transcript\n\n_(empty)_\n"

    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        offset = int(seg["offset"])
        duration = int(seg["duration"])
        end = offset + duration

        start_new = False
        if current is None:
            start_new = True
        else:
            gap = offset - current["end"]
            if gap >= silence_threshold_ms:
                start_new = True
            elif len(current["text"]) >= block_target_chars:
                start_new = True

        if start_new:
            current = {"start": offset, "end": end, "text": text}
            blocks.append(current)
        else:
            current["text"] += " " + text
            current["end"] = end

    lang = transcript.get("lang", "ja")
    lines = [
        f"# Transcript ({lang})",
        "",
        f"- Total blocks: {len(blocks)}",
        f"- Total duration: ~{_format_ts(blocks[-1]['end'])}",
        "",
        "---",
        "",
    ]
    for b in blocks:
        ts = _format_ts(b["start"])
        lines.append(f"## [{ts}]")
        lines.append("")
        lines.append(b["text"])
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Pack transcript JSON into Markdown")
    parser.add_argument("transcript_json", help="Path to transcript JSON")
    parser.add_argument("--out", help="Output .md path (default: stdout)")
    parser.add_argument("--silence-ms", type=int, default=1500)
    parser.add_argument("--block-chars", type=int, default=240)
    args = parser.parse_args()

    src = Path(args.transcript_json)
    with src.open(encoding="utf-8") as f:
        transcript = json.load(f)

    md = pack_transcript(transcript, args.silence_ms, args.block_chars)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
