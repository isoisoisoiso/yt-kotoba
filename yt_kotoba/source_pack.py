"""Source pack manifests for cross-product handoff.

The manifest is intentionally small and path-based. It lets renderer/checking
projects consume a yt-kotoba analysis directory without importing yt-kotoba or
guessing local filenames.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA = "yt-kotoba.source_pack.v1"
MANIFEST_FILENAME = "source_pack_manifest.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _infer_project_name(source_dir: Path) -> str | None:
    parts = source_dir.parts
    if "projects" not in parts:
        return None
    index = parts.index("projects")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _relative_path(source_dir: Path, path: Path) -> str | None:
    try:
        return path.relative_to(source_dir).as_posix()
    except ValueError:
        return None


def _first_existing(source_dir: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = source_dir / candidate
        if path.exists():
            return path
    return source_dir / candidates[0]


def _file_ref(
    source_dir: Path,
    relative_path: str | None,
    distribution: str,
    role: str,
) -> dict[str, Any]:
    if relative_path is None:
        return {
            "path": None,
            "exists": False,
            "distribution": distribution,
            "role": role,
        }

    path = source_dir / relative_path
    ref: dict[str, Any] = {
        "path": relative_path,
        "exists": path.exists(),
        "distribution": distribution,
        "role": role,
    }
    if path.exists():
        ref["type"] = "directory" if path.is_dir() else "file"
        if path.suffix == ".json" and path.is_file():
            data = _load_json(path)
            rights_mode = data.get("rights_mode")
            if rights_mode:
                ref["rights_mode"] = rights_mode
    return ref


def _file_ref_from_path(
    source_dir: Path,
    path: Path | None,
    distribution: str,
    role: str,
) -> dict[str, Any]:
    return _file_ref(
        source_dir,
        _relative_path(source_dir, path) if path is not None else None,
        distribution,
        role,
    )


def _item_count(path: Path, key: str) -> int | None:
    data = _load_json(path)
    items = data.get(key)
    return len(items) if isinstance(items, list) else None


def _comments_status(path: Path) -> str | None:
    data = _load_json(path)
    status = data.get("status")
    return str(status) if status else None


def _existing_qa_issue_counts(source_dir: Path) -> dict[str, int] | None:
    data = _load_json(source_dir / "qa" / "mismatches.json")
    issues = data.get("issues")
    if not isinstance(issues, list):
        return None
    return {
        "error": sum(1 for item in issues if item.get("severity") == "error"),
        "warning": sum(1 for item in issues if item.get("severity") == "warning"),
        "info": sum(1 for item in issues if item.get("severity") == "info"),
    }


def build_source_pack_manifest(
    source_dir: Path,
    qa_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a manifest for one source analysis directory.

    All paths are relative to the directory that contains the manifest.
    """
    source_dir = source_dir.resolve()
    metadata = _load_json(source_dir / "metadata.json")
    source_id = str(metadata.get("id") or source_dir.name)
    source_url = metadata.get("webpage_url") or f"https://www.youtube.com/watch?v={source_id}"

    audio_path = _first_existing(source_dir, ["audio.m4a", f"{source_id}.audio.m4a"])
    transcript_path = _first_existing(
        source_dir,
        ["transcript.json", f"{source_id}.transcript.json"],
    )
    packed_path = _first_existing(source_dir, ["packed.md", f"{source_id}.packed.md"])
    comments_path = source_dir / "comments.json"

    files = {
        "source": {
            "video": _file_ref(
                source_dir,
                "video.mp4",
                "internal_only_do_not_publish",
                "downloaded source video",
            ),
            "audio": _file_ref_from_path(
                source_dir,
                audio_path,
                "internal_only_do_not_publish",
                "downloaded source audio",
            ),
            "metadata": _file_ref(
                source_dir,
                "metadata.json",
                "internal_reference",
                "sanitized source metadata",
            ),
            "description": _file_ref(
                source_dir,
                "description.md",
                "internal_reference",
                "source description",
            ),
            "thumbnail": _file_ref(
                source_dir,
                "thumbnail.jpg",
                "internal_only_do_not_publish",
                "downloaded source thumbnail",
            ),
            "comments": _file_ref(
                source_dir,
                "comments.json",
                "internal_reference",
                "YouTube comments fetch result",
            ),
            "transcript": _file_ref_from_path(
                source_dir,
                transcript_path,
                "internal_reference",
                "local transcription",
            ),
            "packed": _file_ref_from_path(
                source_dir,
                packed_path,
                "internal_reference",
                "agent-readable transcript pack",
            ),
        },
        "visual_samples": {
            "frames_every_1s": _file_ref(
                source_dir,
                "frames/every_1s",
                "internal_only_do_not_publish",
                "sampled source frames",
            ),
            "frames_every_2s": _file_ref(
                source_dir,
                "frames/every_2s",
                "internal_only_do_not_publish",
                "sampled source frames",
            ),
            "sheet_every_1s": _file_ref(
                source_dir,
                "frames/sheets/every_1s_sheet.jpg",
                "internal_only_do_not_publish",
                "frame contact sheet",
            ),
            "sheet_every_2s": _file_ref(
                source_dir,
                "frames/sheets/every_2s_sheet.jpg",
                "internal_only_do_not_publish",
                "frame contact sheet",
            ),
        },
        "internal_analysis": {
            "telops": _file_ref(
                source_dir,
                "telops.raw.json",
                "internal_analysis_only",
                "source telop OCR/timing/placement observations",
            ),
            "visual_events": _file_ref(
                source_dir,
                "visual_events.json",
                "internal_analysis_only",
                "source visual rhythm observations",
            ),
            "source_audio": _file_ref(
                source_dir,
                "source_audio_analysis.json",
                "third_party_source_audio_do_not_clone",
                "source audio observations",
            ),
        },
        "recipes": {
            "style": _file_ref(
                source_dir,
                "style_recipe.json",
                "abstracted_style_only",
                "public-safe visual/telop pattern recipe",
            ),
            "audio": _file_ref(
                source_dir,
                "audio_recipe.json",
                "abstracted_audio_style_only",
                "public-safe audio pattern recipe",
            ),
        },
        "qa": {
            "analysis_report": _file_ref(
                source_dir,
                "qa/analysis_check.md",
                "internal_only_do_not_publish",
                "source analysis QA report",
            ),
            "mismatches": _file_ref(
                source_dir,
                "qa/mismatches.json",
                "internal_only_do_not_publish",
                "source analysis QA issues",
            ),
            "telop_sheet": _file_ref(
                source_dir,
                "qa/telop_check_sheet.jpg",
                "internal_only_do_not_publish",
                "telop QA contact sheet",
            ),
            "event_sheet": _file_ref(
                source_dir,
                "qa/event_check_sheet.jpg",
                "internal_only_do_not_publish",
                "visual event QA contact sheet",
            ),
        },
    }

    telop_count = _item_count(source_dir / "telops.raw.json", "telops")
    event_count = _item_count(source_dir / "visual_events.json", "events")
    comments_status = _comments_status(comments_path)
    if comments_status:
        files["source"]["comments"]["status"] = comments_status

    qa_status = {
        "available": (source_dir / "qa" / "analysis_check.md").exists(),
        "issue_counts": (qa_summary or {}).get("issue_counts")
        or _existing_qa_issue_counts(source_dir),
    }

    return {
        "schema": SCHEMA,
        "source_pack_role": "local_source_analysis_reference",
        "path_base": ".",
        "path_rule": "All file paths are relative to this manifest file.",
        "project": {
            "name": _infer_project_name(source_dir),
        },
        "source": {
            "platform": "youtube",
            "id": source_id,
            "url": source_url,
            "title": metadata.get("title"),
            "channel": metadata.get("channel") or metadata.get("uploader"),
            "duration_sec": metadata.get("duration"),
        },
        "counts": {
            "telops": telop_count,
            "visual_events": event_count,
        },
        "comments": {
            "status": comments_status,
        },
        "files": files,
        "qa_status": qa_status,
        "usage_contract": {
            "for_internal_analysis": [
                "Read internal_analysis and source files to understand the reference.",
                "Do not publish, redistribute, or copy raw source content from this pack.",
            ],
            "for_public_generation": [
                "Use recipes/style and recipes/audio as abstract pattern inputs.",
                "Rewrite wording, use original assets, and avoid cloning source voice or visuals.",
            ],
            "external_check_skill_entrypoint": "source_pack_manifest.json",
        },
    }


def write_source_pack_manifest(
    source_dir: Path,
    qa_summary: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write `source_pack_manifest.json` and return `(path, manifest)`."""
    source_dir = source_dir.resolve()
    manifest = build_source_pack_manifest(source_dir, qa_summary=qa_summary)
    out_path = source_dir / MANIFEST_FILENAME
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path, manifest
