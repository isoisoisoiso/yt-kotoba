"""Transcribe audio with faster-whisper (NVIDIA / CPU) or mlx-whisper (Apple Silicon).

Output JSON shape: {segments: [{text, offset, duration}], fullText, lang}
The shape matches insight-boost-13's existing scripts so transcripts are interchangeable.
"""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import TypedDict

from .config import get_whisper_compute_type, get_whisper_device, get_whisper_model

USE_MLX = platform.system() == "Darwin" and platform.processor() == "arm"


class Segment(TypedDict):
    text: str
    offset: int   # ms
    duration: int  # ms


class TranscriptResult(TypedDict):
    segments: list[Segment]
    fullText: str
    lang: str


def _transcribe_mlx(audio_path: Path, lang: str) -> TranscriptResult:
    try:
        import mlx_whisper
    except ImportError as e:
        raise RuntimeError(
            "mlx-whisper not installed. Run: pip install -e '.[mlx]'"
        ) from e

    repo_map = {
        "large-v3": "mlx-community/whisper-large-v3-mlx",
        "large-v2": "mlx-community/whisper-large-v2-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "small": "mlx-community/whisper-small-mlx",
    }
    repo = repo_map.get(get_whisper_model(), "mlx-community/whisper-large-v3-mlx")

    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=repo,
        language=lang,
        word_timestamps=False,
        verbose=False,
    )

    segments: list[Segment] = []
    for seg in result.get("segments", []):
        segments.append(Segment(
            text=seg["text"].strip(),
            offset=round(seg["start"] * 1000),
            duration=round((seg["end"] - seg["start"]) * 1000),
        ))

    return TranscriptResult(
        segments=segments,
        fullText=str(result.get("text", "")).strip(),
        lang=lang,
    )


def _transcribe_faster(audio_path: Path, lang: str) -> TranscriptResult:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper not installed. Run: pip install -e '.[cuda]'"
        ) from e

    model_size = get_whisper_model()
    device = get_whisper_device()
    compute_type = get_whisper_compute_type()

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception:
        # GPU 不在等で失敗 → CPU + int8 にフォールバック
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments_iter, _info = model.transcribe(
        str(audio_path),
        language=lang,
        word_timestamps=False,
        vad_filter=False,
    )

    segments: list[Segment] = []
    full_text_parts: list[str] = []
    for seg in segments_iter:
        text = seg.text.strip()
        segments.append(Segment(
            text=text,
            offset=round(seg.start * 1000),
            duration=round((seg.end - seg.start) * 1000),
        ))
        full_text_parts.append(text)

    return TranscriptResult(
        segments=segments,
        fullText=" ".join(full_text_parts).strip(),
        lang=lang,
    )


def transcribe_audio(audio_path: Path, lang: str = "ja") -> TranscriptResult:
    """Transcribe an audio file, picking backend by platform."""
    if USE_MLX:
        return _transcribe_mlx(audio_path, lang)
    return _transcribe_faster(audio_path, lang)


def transcribe_with_cache(audio_path: Path, lang: str = "ja") -> TranscriptResult:
    """Transcribe + persist JSON next to the audio. Reuses cache if present."""
    audio_path = Path(audio_path)
    # "<id>.audio.m4a" → "<id>.transcript.json"
    cache_path = audio_path.parent / (audio_path.stem.replace(".audio", "") + ".transcript.json")

    if cache_path.exists() and cache_path.stat().st_size > 0:
        with cache_path.open(encoding="utf-8") as f:
            return json.load(f)

    result = transcribe_audio(audio_path, lang)
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Transcribe audio file")
    parser.add_argument("audio", help="Audio file path")
    parser.add_argument("--lang", default="ja", help="Language code (default: ja)")
    parser.add_argument("--no-cache", action="store_true", help="Skip cache")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}", file=sys.stderr)
        return 1

    if args.no_cache:
        result = transcribe_audio(audio_path, args.lang)
    else:
        result = transcribe_with_cache(audio_path, args.lang)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
