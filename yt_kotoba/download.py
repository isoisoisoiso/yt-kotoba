"""Download audio from YouTube via yt-dlp."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

YOUTUBE_ID_RE = re.compile(r"^[\w-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    """Extract 11-char YouTube video ID from URL or accept bare ID."""
    s = url_or_id.strip()
    if YOUTUBE_ID_RE.match(s):
        return s
    try:
        u = urlparse(s if "://" in s else f"https://{s}")
    except ValueError as e:
        raise ValueError(f"Could not parse URL: {url_or_id}") from e

    qs = parse_qs(u.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]

    if u.hostname and u.hostname.endswith("youtu.be"):
        return u.path.lstrip("/")

    parts = [p for p in u.path.split("/") if p]
    if parts and parts[0] in ("shorts", "embed", "live") and len(parts) >= 2:
        return parts[1]

    raise ValueError(f"Not a recognizable YouTube URL: {url_or_id}")


def download_audio(
    url_or_id: str,
    out_dir: Path,
    audio_format: str = "m4a",
    cookies_browser: str | None = None,
    cookies_file: str | None = None,
) -> Path:
    """Download audio. Returns Path to the audio file. Skips if already cached.

    YouTube has tightened anti-bot measures (PO Token / "Sign in to confirm
    you're not a bot"). For most videos you'll need to pass cookies. Easiest:
    `cookies_browser="chrome"` (close the browser first so its DB isn't locked)
    or `cookies_browser="firefox"`. For headless environments, export cookies
    to a Netscape-format file and pass `cookies_file`.
    """
    video_id = extract_video_id(url_or_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video_id}.audio.{audio_format}"

    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", audio_format,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "-o", str(out_dir / f"{video_id}.audio.%(ext)s"),
    ]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    elif cookies_file:
        cmd += ["--cookies", cookies_file]
    cmd.append(f"https://www.youtube.com/watch?v={video_id}")

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as e:
        raise RuntimeError(
            "yt-dlp not found. Install with: brew install yt-dlp / scoop install yt-dlp"
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"yt-dlp failed for {video_id}: exit {e.returncode}") from e

    if not out_path.exists():
        # yt-dlp picks the extension itself; find what landed
        candidates = list(out_dir.glob(f"{video_id}.audio.*"))
        if not candidates:
            raise RuntimeError(f"yt-dlp ran but no audio file found for {video_id}")
        return candidates[0]
    return out_path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Download YouTube audio")
    parser.add_argument("url", help="YouTube URL or 11-char video ID")
    parser.add_argument("--out", default="./output", help="Output directory")
    parser.add_argument("--format", default="m4a", help="Audio format (m4a / mp3)")
    parser.add_argument(
        "--cookies-browser",
        help="Extract cookies from this browser (chrome/edge/firefox/brave/...). "
             "Required for many YouTube videos due to anti-bot measures. "
             "Close the browser first to release the cookie DB lock.",
    )
    parser.add_argument(
        "--cookies-file",
        help="Path to a Netscape-format cookies.txt file (alternative to --cookies-browser).",
    )
    args = parser.parse_args()

    out_path = download_audio(
        args.url,
        Path(args.out),
        args.format,
        cookies_browser=args.cookies_browser,
        cookies_file=args.cookies_file,
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
