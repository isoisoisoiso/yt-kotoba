"""Locate the external tools (yt-dlp, ffmpeg) that yt-kotoba shells out to.

PATH comes first. When a tool is missing there, fall back to the copy installed
next to the running Python (a venv's bin/) and, for ffmpeg, to imageio-ffmpeg,
so a plain `pip install -e '.[mlx]'` works without Homebrew.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _beside_python(name: str) -> str | None:
    candidate = Path(sys.executable).with_name(name)
    return str(candidate) if candidate.exists() else None


def find_yt_dlp() -> str:
    found = shutil.which("yt-dlp") or _beside_python("yt-dlp")
    if found is None:
        raise RuntimeError(
            "yt-dlp not found. Install with: brew install yt-dlp / scoop install yt-dlp"
        )
    return found


def find_ffmpeg(required: bool = True) -> str | None:
    found = shutil.which("ffmpeg") or _beside_python("ffmpeg")
    if found is None:
        try:
            import imageio_ffmpeg

            found = str(imageio_ffmpeg.get_ffmpeg_exe())
        except Exception:
            found = None
    if found is None and required:
        raise RuntimeError("ffmpeg not found. Install ffmpeg or the imageio-ffmpeg package.")
    return found
