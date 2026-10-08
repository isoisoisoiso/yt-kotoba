"""YouTube context without an API key: metadata, description, thumbnail, comments.

Everything goes through yt-dlp, so the default workflow stays API-key-free.
Files are written with stable names inside one video directory:
metadata.json, description.md, thumbnail.jpg, comments.json.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .tools import find_yt_dlp

# Only these fields are kept in metadata.json; the raw yt-dlp dump also holds
# format URLs and HTTP headers that are useless for analysis and noisy to share.
METADATA_FIELDS = [
    "id", "title", "channel", "channel_id", "uploader", "channel_follower_count",
    "view_count", "like_count", "comment_count", "upload_date", "duration",
    "chapters", "tags", "categories", "webpage_url", "language", "was_live",
]

COMMENT_FIELDS = [
    "id", "parent", "author", "author_is_uploader", "is_pinned", "is_favorited",
    "text", "like_count", "timestamp",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yt_dlp(args: list[str], cookies_browser: str | None, cookies_file: str | None) -> None:
    cmd = [find_yt_dlp(), "--no-playlist", "--quiet", "--no-warnings"]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    elif cookies_file:
        cmd += ["--cookies", cookies_file]
    subprocess.run(cmd + args, check=True)


def fetch_metadata(
    video_id: str,
    out_dir: Path,
    cookies_browser: str | None = None,
    cookies_file: str | None = None,
) -> dict[str, Any]:
    """Write metadata.json, description.md and thumbnail.jpg. Returns the metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory(prefix="yt_kotoba_meta_") as tmp:
        _yt_dlp(
            ["--skip-download", "--write-info-json", "--write-thumbnail",
             "--convert-thumbnails", "jpg", "-o", str(Path(tmp) / "src.%(ext)s"), url],
            cookies_browser, cookies_file,
        )
        with (Path(tmp) / "src.info.json").open(encoding="utf-8") as f:
            info = json.load(f)
        thumb = next(iter(Path(tmp).glob("src*.jpg")), None)
        if thumb is not None:
            (out_dir / "thumbnail.jpg").write_bytes(thumb.read_bytes())

    meta = {k: info.get(k) for k in METADATA_FIELDS}
    meta["fetched_at"] = _now()
    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    desc = info.get("description") or ""
    (out_dir / "description.md").write_text(
        f"# {info.get('title', '')}\n\n{desc}\n", encoding="utf-8"
    )
    return meta


def normalize_comments(raw: list[dict[str, Any]] | None, status: str) -> dict[str, Any]:
    """Shape yt-dlp comments into comments.json with counts split by role.

    Root comments, replies and the uploader's own posts are counted apart so
    that a creator replying to everyone does not look like broad engagement.
    """
    items = [{k: c.get(k) for k in COMMENT_FIELDS} for c in (raw or [])]
    root = [c for c in items if c.get("parent") == "root"]
    replies = [c for c in items if c.get("parent") != "root"]
    uploader = [c for c in items if c.get("author_is_uploader")]
    return {
        "status": status,
        "fetched_at": _now(),
        "source": "yt-dlp",
        "counts": {
            "total": len(items),
            "root": len(root),
            "replies": len(replies),
            "uploader_posts": len(uploader),
            "viewer_root": len([c for c in root if not c.get("author_is_uploader")]),
        },
        "comments": items,
    }


def fetch_comments(
    video_id: str,
    out_dir: Path,
    max_comments: int = 2000,
    sort: str = "top",
    cookies_browser: str | None = None,
    cookies_file: str | None = None,
) -> dict[str, Any]:
    """Write comments.json. Never raises on fetch failure; the status says what happened."""
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    raw: list[dict[str, Any]] | None = None
    status = "ok"
    with tempfile.TemporaryDirectory(prefix="yt_kotoba_comments_") as tmp:
        try:
            _yt_dlp(
                ["--skip-download", "--write-comments",
                 "--extractor-args", f"youtube:comment_sort={sort};max_comments={max_comments},all,200",
                 "-o", str(Path(tmp) / "c.%(ext)s"), url],
                cookies_browser, cookies_file,
            )
            with (Path(tmp) / "c.info.json").open(encoding="utf-8") as f:
                info = json.load(f)
            raw = info.get("comments")
            if raw is None:
                status = "disabled_or_unavailable"
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            status = f"error: {e.__class__.__name__}"
    result = normalize_comments(raw, status)
    (out_dir / "comments.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
