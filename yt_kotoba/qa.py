"""Local QA for source analysis packs.

This checks whether analysis JSON files line up with the downloaded source
video. It intentionally does not compare a generated video; that belongs in the
renderer/production project.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .source_pack import write_source_pack_manifest


class QaError(RuntimeError):
    pass


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise QaError(f"{name} is required but was not found in PATH.")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _run_quiet(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _ffprobe_json(video: Path) -> dict[str, Any]:
    output = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration,r_frame_rate",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video),
        ],
        text=True,
    )
    return json.loads(output)


def _duration(probe: dict[str, Any]) -> float:
    stream = (probe.get("streams") or [{}])[0]
    raw = stream.get("duration") or (probe.get("format") or {}).get("duration")
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise QaError("Could not read source video duration with ffprobe.") from exc


def _bbox_ok(bbox: Any) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    if not all(isinstance(v, (int, float)) for v in bbox):
        return False
    x, y, w, h = [float(v) for v in bbox]
    return (
        0 <= x <= 1
        and 0 <= y <= 1
        and 0 < w <= 1
        and 0 < h <= 1
        and x + w <= 1.05
        and y + h <= 1.05
    )


def _time_ok(start: Any, end: Any, duration: float) -> tuple[bool, str | None]:
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return False, "start/end must be numeric"
    if end <= start:
        return False, "end must be greater than start"
    if start < -0.05:
        return False, "start is before 0"
    if end > duration + 0.5:
        return False, f"end exceeds video duration ({duration:.2f}s)"
    if end - start < 0.35:
        return True, "very short interval; verify manually"
    return True, None


def _add_issue(
    issues: list[dict[str, Any]],
    severity: str,
    item_type: str,
    item_id: str,
    message: str,
) -> None:
    issues.append(
        {
            "severity": severity,
            "item_type": item_type,
            "id": item_id,
            "message": message,
        }
    )


def _render_frame(
    video: Path,
    timestamp: float,
    out_path: Path,
    bbox: list[float] | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    vf = "scale=360:-2"
    if bbox is not None:
        x, y, w, h = bbox
        vf = (
            f"drawbox=x=iw*{x:.6f}:y=ih*{y:.6f}:w=iw*{w:.6f}:h=ih*{h:.6f}:"
            "color=red@0.85:t=8,scale=360:-2"
        )
    _run_quiet(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            "-vf",
            vf,
            str(out_path),
        ]
    )


def _contact_sheet(input_dir: Path, pattern: str, count: int, out_path: Path) -> None:
    if count <= 0:
        return
    cols = min(6, max(1, count))
    rows = max(1, math.ceil(count / cols))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run_quiet(
        [
            "ffmpeg",
            "-y",
            "-start_number",
            "1",
            "-framerate",
            "1",
            "-i",
            str(input_dir / pattern),
            "-vf",
            f"scale=180:-2,tile={cols}x{rows}:padding=6:margin=6:color=white",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(out_path),
        ]
    )


def _rights_checks(source_dir: Path, issues: list[dict[str, Any]]) -> None:
    expected = {
        "telops.raw.json": "internal_analysis_only",
        "visual_events.json": "internal_analysis_only",
        "style_recipe.json": "abstracted_style_only",
        "audio_recipe.json": "abstracted_audio_style_only",
        "source_audio_analysis.json": "third_party_source_audio_do_not_clone",
    }
    for filename, expected_mode in expected.items():
        path = source_dir / filename
        data = _load_json(path)
        if data is None:
            _add_issue(issues, "info", "file", filename, "file is not present")
            continue
        actual = data.get("rights_mode")
        if actual != expected_mode:
            _add_issue(
                issues,
                "warning",
                "rights_mode",
                filename,
                f"rights_mode is {actual!r}; expected {expected_mode!r}",
            )


def run_source_qa(
    source_dir: Path,
    out_dir: Path | None = None,
    max_telop_previews: int = 48,
) -> dict[str, Any]:
    """Run QA for one source directory and return a JSON-serializable summary."""
    _require_tool("ffmpeg")
    _require_tool("ffprobe")

    source_dir = source_dir.resolve()
    if out_dir is None:
        out_dir = source_dir / "qa"
    else:
        out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    video = source_dir / "video.mp4"
    if not video.exists():
        raise QaError(f"source video not found: {video}")

    probe = _ffprobe_json(video)
    duration = _duration(probe)
    stream = (probe.get("streams") or [{}])[0]
    issues: list[dict[str, Any]] = []

    _rights_checks(source_dir, issues)

    telops_data = _load_json(source_dir / "telops.raw.json") or {}
    telops = telops_data.get("telops") or []
    if not isinstance(telops, list):
        _add_issue(issues, "error", "telops", "telops.raw.json", "`telops` must be a list")
        telops = []

    telop_frames = out_dir / "telop_frames"
    rendered_telops = 0
    for idx, item in enumerate(telops[:max_telop_previews], start=1):
        item_id = str(item.get("id") or f"telop_{idx:03d}")
        start = item.get("start")
        end = item.get("end")
        ok, message = _time_ok(start, end, duration)
        if not ok:
            _add_issue(issues, "error", "telop", item_id, message or "invalid interval")
            continue
        if message:
            _add_issue(issues, "warning", "telop", item_id, message)
        text = str(item.get("text") or "").strip()
        if not text:
            _add_issue(issues, "warning", "telop", item_id, "text is empty")
        bbox = item.get("bbox")
        bbox_for_render: list[float] | None = None
        if _bbox_ok(bbox):
            bbox_for_render = [float(v) for v in bbox]
        else:
            _add_issue(
                issues,
                "warning",
                "telop",
                item_id,
                "bbox is missing or outside normalized bounds",
            )
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.75:
            _add_issue(issues, "info", "telop", item_id, f"low confidence ({confidence})")

        mid = max(0.0, min(duration - 0.05, (float(start) + float(end)) / 2.0))
        _render_frame(video, mid, telop_frames / f"telop_{idx:03d}.jpg", bbox_for_render)
        rendered_telops += 1

    telop_sheet = out_dir / "telop_check_sheet.jpg"
    if rendered_telops:
        _contact_sheet(telop_frames, "telop_%03d.jpg", rendered_telops, telop_sheet)

    events_data = _load_json(source_dir / "visual_events.json") or {}
    events = events_data.get("events") or []
    if not isinstance(events, list):
        _add_issue(
            issues,
            "error",
            "visual_events",
            "visual_events.json",
            "`events` must be a list",
        )
        events = []

    event_frames = out_dir / "event_frames"
    rendered_events = 0
    for idx, item in enumerate(events, start=1):
        item_id = str(item.get("type") or f"event_{idx:03d}")
        start = item.get("start")
        end = item.get("end")
        ok, message = _time_ok(start, end, duration)
        if not ok:
            _add_issue(issues, "error", "event", item_id, message or "invalid interval")
            continue
        if message:
            _add_issue(issues, "warning", "event", item_id, message)
        mid = max(0.0, min(duration - 0.05, (float(start) + float(end)) / 2.0))
        _render_frame(video, mid, event_frames / f"event_{idx:03d}.jpg")
        rendered_events += 1

    event_sheet = out_dir / "event_check_sheet.jpg"
    if rendered_events:
        _contact_sheet(event_frames, "event_%03d.jpg", rendered_events, event_sheet)

    summary = {
        "source_dir": str(source_dir),
        "video": str(video),
        "duration_sec": round(duration, 3),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "telops_total": len(telops),
        "telop_previews": rendered_telops,
        "events_total": len(events),
        "event_previews": rendered_events,
        "outputs": {
            "analysis_check": str(out_dir / "analysis_check.md"),
            "mismatches": str(out_dir / "mismatches.json"),
            "telop_sheet": str(telop_sheet) if rendered_telops else None,
            "event_sheet": str(event_sheet) if rendered_events else None,
        },
        "issue_counts": {
            "error": sum(1 for i in issues if i["severity"] == "error"),
            "warning": sum(1 for i in issues if i["severity"] == "warning"),
            "info": sum(1 for i in issues if i["severity"] == "info"),
        },
        "issues": issues,
    }

    (out_dir / "mismatches.json").write_text(
        json.dumps({"issues": issues}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path = out_dir / "analysis_check.md"
    _write_report(summary, report_path)
    manifest_path, _ = write_source_pack_manifest(source_dir, qa_summary=summary)
    summary["outputs"]["source_pack_manifest"] = str(manifest_path)
    _write_report(summary, report_path)
    return summary


def _write_report(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Analysis QA",
        "",
        "This report checks analysis artifacts against the downloaded source video.",
        "It does not compare a generated video.",
        "",
        "## Source",
        "",
        f"- Source dir: `{summary['source_dir']}`",
        f"- Video: `{summary['video']}`",
        f"- Duration: {summary['duration_sec']} sec",
        f"- Resolution: {summary.get('width')}x{summary.get('height')}",
        "",
        "## Outputs",
        "",
    ]
    outputs = summary["outputs"]
    for label in ["telop_sheet", "event_sheet", "mismatches", "source_pack_manifest"]:
        value = outputs.get(label)
        if value:
            lines.append(f"- {label}: `{value}`")

    lines += [
        "",
        "## Counts",
        "",
        f"- Telops: {summary['telops_total']} total, {summary['telop_previews']} previewed",
        f"- Visual events: {summary['events_total']} total, {summary['event_previews']} previewed",
        f"- Errors: {summary['issue_counts']['error']}",
        f"- Warnings: {summary['issue_counts']['warning']}",
        f"- Info: {summary['issue_counts']['info']}",
        "",
        "## Issues",
        "",
    ]
    if not summary["issues"]:
        lines.append("- None")
    else:
        for issue in summary["issues"]:
            lines.append(
                f"- [{issue['severity']}] {issue['item_type']} `{issue['id']}`: {issue['message']}"
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="QA analysis artifacts against a source video")
    parser.add_argument("source_dir", help="Directory containing video.mp4 and analysis JSON files")
    parser.add_argument("--out", help="Output QA directory (default: <source_dir>/qa)")
    parser.add_argument("--max-telop-previews", type=int, default=48)
    args = parser.parse_args()

    summary = run_source_qa(
        Path(args.source_dir),
        out_dir=Path(args.out) if args.out else None,
        max_telop_previews=args.max_telop_previews,
    )
    printable = {k: v for k, v in summary.items() if k != "issues"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0 if summary["issue_counts"]["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
