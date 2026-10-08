"""Attach anonymous speaker labels to Whisper transcript segments with pyannote.audio."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, TypedDict

from .tools import find_ffmpeg


DEFAULT_DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"
UNKNOWN_SPEAKER = "SPEAKER_UNKNOWN"


class SpeakerTurn(TypedDict):
    start: float
    end: float
    speaker: str


def _validate_speaker_bounds(
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
) -> None:
    values = {
        "--num-speakers": num_speakers,
        "--min-speakers": min_speakers,
        "--max-speakers": max_speakers,
    }
    for flag, value in values.items():
        if value is not None and value < 1:
            raise RuntimeError(f"{flag} must be at least 1")
    if num_speakers is not None and (min_speakers is not None or max_speakers is not None):
        raise RuntimeError("--num-speakers cannot be combined with speaker min/max bounds")
    if (
        min_speakers is not None
        and max_speakers is not None
        and min_speakers > max_speakers
    ):
        raise RuntimeError("--min-speakers cannot be greater than --max-speakers")


def _speaker_request(
    model: str,
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
) -> dict[str, Any]:
    return {
        "model": model,
        "numSpeakers": num_speakers,
        "minSpeakers": min_speakers,
        "maxSpeakers": max_speakers,
    }


def _cache_matches(transcript: dict[str, Any], request: dict[str, Any]) -> bool:
    metadata = transcript.get("diarization")
    if not isinstance(metadata, dict):
        return False
    if any(metadata.get(key) != value for key, value in request.items()):
        return False
    segments = transcript.get("segments", [])
    return bool(segments) and all(segment.get("speaker") for segment in segments)


def _turns_from_output(output: Any) -> list[SpeakerTurn]:
    annotation = getattr(output, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = getattr(output, "speaker_diarization", output)

    turns: list[SpeakerTurn] = []
    for item in annotation:
        if len(item) == 2:
            turn, speaker = item
        elif len(item) == 3:
            turn, _track, speaker = item
        else:
            raise RuntimeError("Unexpected pyannote diarization output")
        turns.append(
            SpeakerTurn(
                start=float(turn.start),
                end=float(turn.end),
                speaker=str(speaker),
            )
        )
    turns.sort(key=lambda turn: (turn["start"], turn["end"], turn["speaker"]))
    return turns


def assign_speakers(
    transcript: dict[str, Any],
    turns: list[SpeakerTurn],
) -> dict[str, Any]:
    """Return a transcript copy whose segments are labeled by maximum time overlap."""
    result = dict(transcript)
    labeled_segments: list[dict[str, Any]] = []

    for original in transcript.get("segments", []):
        segment = dict(original)
        start = int(segment["offset"]) / 1000
        end = start + int(segment["duration"]) / 1000
        best_overlap = 0.0
        best_speaker = UNKNOWN_SPEAKER

        for turn in turns:
            overlap = max(0.0, min(end, turn["end"]) - max(start, turn["start"]))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn["speaker"]

        segment["speaker"] = best_speaker
        labeled_segments.append(segment)

    result["segments"] = labeled_segments
    return result


def _load_waveform(audio_path: Path, torch: Any) -> dict[str, Any]:
    """Decode to a mono 16 kHz tensor without relying on TorchCodec shared libraries."""
    command = [
        find_ffmpeg(),
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "f32le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        details = e.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg could not decode audio for diarization: {details}") from e

    if not completed.stdout:
        raise RuntimeError("ffmpeg decoded no audio for diarization")
    samples = torch.frombuffer(bytearray(completed.stdout), dtype=torch.float32)
    return {"waveform": samples.unsqueeze(0), "sample_rate": 16000}


def diarize_transcript(
    audio_path: Path,
    transcript: dict[str, Any],
    *,
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    model: str = DEFAULT_DIARIZATION_MODEL,
) -> dict[str, Any]:
    """Run local pyannote diarization and attach anonymous labels to transcript segments."""
    _validate_speaker_bounds(num_speakers, min_speakers, max_speakers)
    if sys.version_info < (3, 10):
        raise RuntimeError(
            "Speaker diarization requires Python 3.10 or newer. "
            "Create a newer environment before installing the diarization extra."
        )

    # The project is local-first and does not enable pyannote's optional usage metrics.
    os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "0")
    matplotlib_cache = Path(tempfile.gettempdir()) / "yt-kotoba-matplotlib"
    matplotlib_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))

    try:
        import torch
        # TorchCodec can warn at import time when only a static ffmpeg is available.
        # We intentionally bypass it by passing a preloaded waveform below.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"(?s).*torchcodec is not installed correctly.*",
            )
            from pyannote.audio import Pipeline
    except ImportError as e:
        raise RuntimeError(
            "pyannote.audio not installed. Run: pip install -e '.[diarization]' "
            "(Python 3.10+)"
        ) from e

    try:
        # token=True reads HF_TOKEN or the credential saved by `hf auth login`.
        pipeline = Pipeline.from_pretrained(model, token=True)
    except Exception as e:
        raise RuntimeError(
            "Could not load the pyannote Community-1 model. Accept its Hugging Face "
            "user conditions, then run `hf auth login` with a read token. "
            f"Details: {e}"
        ) from e

    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))

    inference_kwargs = {
        key: value
        for key, value in {
            "num_speakers": num_speakers,
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
        }.items()
        if value is not None
    }
    audio = _load_waveform(audio_path, torch)
    output = pipeline(audio, **inference_kwargs)
    turns = _turns_from_output(output)
    if not turns:
        raise RuntimeError("pyannote found no speech or speakers in the audio")

    result = assign_speakers(transcript, turns)
    request = _speaker_request(model, num_speakers, min_speakers, max_speakers)
    result["diarization"] = {
        **request,
        "speakers": sorted({turn["speaker"] for turn in turns}),
    }
    return result


def diarize_with_cache(
    audio_path: Path,
    transcript: dict[str, Any],
    *,
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    model: str = DEFAULT_DIARIZATION_MODEL,
) -> dict[str, Any]:
    """Diarize a transcript and persist the enriched deterministic transcript cache."""
    _validate_speaker_bounds(num_speakers, min_speakers, max_speakers)
    request = _speaker_request(model, num_speakers, min_speakers, max_speakers)
    if _cache_matches(transcript, request):
        return transcript

    result = diarize_transcript(
        audio_path,
        transcript,
        num_speakers=num_speakers,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        model=model,
    )
    cache_path = audio_path.parent / (
        audio_path.stem.replace(".audio", "") + ".transcript.json"
    )
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
