"""Visual samples for structure analysis: video, frames, contact sheets, cut rhythm.

Frames are for reading how a video *looks* (art style, captions, how often the
picture changes). They are internal reference material; never publish them.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .tools import find_ffmpeg, find_yt_dlp

# HLS (m3u8) formats can be 10x slower to fetch than DASH over https, so prefer https.
VIDEO_FORMAT = "bv*[height<={h}][protocol=https]+ba[ext=m4a]/bv*[height<={h}]+ba/b"
THRESHOLDS = (8, 15, 25)
DIFF_W, DIFF_H, DIFF_FPS = 64, 36, 2


def download_video(
    video_id: str,
    out_dir: Path,
    max_height: int = 1080,
    cookies_browser: str | None = None,
    cookies_file: str | None = None,
) -> Path:
    """Download video.mp4 into out_dir (skips if present)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "video.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    cmd = [find_yt_dlp(), "--no-playlist", "--quiet", "--no-warnings", "-N", "8",
           "-f", VIDEO_FORMAT.format(h=max_height), "--merge-output-format", "mp4",
           "-o", str(out_dir / "video.%(ext)s")]
    ffmpeg = find_ffmpeg(required=False)
    if ffmpeg is not None:
        cmd += ["--ffmpeg-location", ffmpeg]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    elif cookies_file:
        cmd += ["--cookies", cookies_file]
    subprocess.run(cmd + [f"https://www.youtube.com/watch?v={video_id}"], check=True)
    return out


def sample_frames(video: Path, out_dir: Path, every_sec: int = 10) -> dict[str, str]:
    """Write frames/every_<n>s/t%04d.jpg and frames/sheets/every_<n>s_sheet%02d.jpg (5x4 tiles)."""
    frames = out_dir / "frames" / f"every_{every_sec}s"
    sheets = out_dir / "frames" / "sheets"
    frames.mkdir(parents=True, exist_ok=True)
    sheets.mkdir(parents=True, exist_ok=True)
    base = [find_ffmpeg(), "-loglevel", "error", "-y", "-i", str(video)]
    subprocess.run(base + ["-vf", f"fps=1/{every_sec},scale=1280:-2", "-q:v", "3",
                           str(frames / "t%04d.jpg")], check=True)
    subprocess.run(base + ["-vf", f"fps=1/{every_sec},scale=384:-2,tile=5x4", "-q:v", "4",
                           str(sheets / f"every_{every_sec}s_sheet%02d.jpg")], check=True)
    return {
        "frames": f"frames/every_{every_sec}s",
        "sheets": f"frames/sheets/every_{every_sec}s_sheet%02d.jpg",
    }


def count_changes(diffs: list[float], threshold: float) -> int:
    """Count rising edges where the frame difference crosses `threshold`.

    Consecutive changed frames (a crossfade, a pan) count as one change.
    """
    events, prev = 0, False
    for d in diffs:
        changed = d > threshold
        if changed and not prev:
            events += 1
        prev = changed
    return events


def frame_diffs(raw: bytes, frame_size: int = DIFF_W * DIFF_H) -> list[float]:
    """Mean absolute difference between consecutive grayscale frames."""
    n = len(raw) // frame_size
    out = []
    for i in range(1, n):
        a = raw[(i - 1) * frame_size: i * frame_size]
        b = raw[i * frame_size: (i + 1) * frame_size]
        out.append(sum(abs(x - y) for x, y in zip(a, b)) / frame_size)
    return out


def measure_rhythm(video: Path, out_dir: Path) -> dict[str, Any]:
    """Estimate how often the picture changes. Writes visual_rhythm.json.

    This is a rough proxy, not a cut list: a speech-bubble swap on the same
    drawing can stay under the lower thresholds, so report a range.
    """
    raw = subprocess.run(
        [find_ffmpeg(), "-loglevel", "error", "-i", str(video),
         "-vf", f"fps={DIFF_FPS},scale={DIFF_W}:{DIFF_H},format=gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True,
    ).stdout
    diffs = frame_diffs(raw)
    duration = (len(diffs) + 1) / DIFF_FPS
    by_threshold = {}
    for th in THRESHOLDS:
        ev = count_changes(diffs, th)
        by_threshold[str(th)] = {
            "changes": ev,
            "sec_per_change": round(duration / ev, 1) if ev else None,
        }
    result = {
        "method": f"{DIFF_FPS}fps {DIFF_W}x{DIFF_H} grayscale mean abs diff, rising edges",
        "duration_sec": duration,
        "by_threshold": by_threshold,
    }
    (out_dir / "visual_rhythm.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
