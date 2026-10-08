"""yt-kotoba — CLI orchestrating download → transcribe → pack.

Generation (X thread / note article) is intentionally NOT in the CLI.
The pipeline produces `<id>.packed.md`; the agent invoking the skill
(Claude Code, Cursor, etc.) reads SKILL.md and writes the downstream
content from packed.md using its own context.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_env
from .diarize import diarize_transcript, diarize_with_cache
from .download import download_audio, extract_video_id
from .pack_transcript import pack_transcript
from .qa import run_source_qa
from .repair import repair_transcript
from .source_pack import write_source_pack_manifest
from .transcribe import transcribe_audio, transcribe_with_cache


def cmd_run(args: argparse.Namespace) -> int:
    load_env()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    video_id = extract_video_id(args.url)
    print(f"[yt-kotoba] video_id = {video_id}")

    total_steps = 4 if args.diarize else 3

    print(f"[1/{total_steps}] downloading audio...")
    audio_path = download_audio(
        args.url,
        out_dir,
        audio_format=args.audio_format,
        cookies_browser=args.cookies_browser,
        cookies_file=args.cookies_file,
    )
    print(f"      -> {audio_path.name}")

    print(f"[2/{total_steps}] transcribing (this may take a while on first run)...")
    transcript = transcribe_with_cache(audio_path, lang=args.lang)
    transcript_path = out_dir / f"{video_id}.transcript.json"
    if not args.no_repair:
        transcript, report = repair_transcript(transcript, audio_path, args.lang)
        if report["repaired"]:
            transcript_path.write_text(
                json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _print_repair(report)
    print(f"      -> {transcript_path.name}  ({len(transcript['segments'])} segments)")

    if args.diarize:
        # After repair, so speaker labels attach to the repaired segments.
        print(f"[3/{total_steps}] identifying speakers (anonymous labels)...")
        transcript = diarize_with_cache(
            audio_path,
            transcript,
            num_speakers=args.num_speakers,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
        )
        speaker_count = len(transcript["diarization"]["speakers"])
        print(f"      -> {transcript_path.name}  ({speaker_count} speakers)")

    print(f"[{total_steps}/{total_steps}] packing transcript...")
    packed = pack_transcript(transcript)
    packed_path = out_dir / f"{video_id}.packed.md"
    packed_path.write_text(packed, encoding="utf-8")
    print(f"      -> {packed_path.name}")

    print("\n[OK] pipeline done.")
    print(f"\n     Next: feed {packed_path.name} to your agent (Claude Code etc).")
    print("     The agent reads SKILL.md and produces X thread / note article")
    print(f"     directly into {out_dir}/")
    return 0


def _print_repair(report: dict) -> None:
    for r in report["repaired"]:
        span = f"{r['start_ms'] // 60000:02d}:{r['start_ms'] // 1000 % 60:02d}-" \
               f"{r['end_ms'] // 60000:02d}:{r['end_ms'] // 1000 % 60:02d}"
        note = "  (loop remains: listen to this part)" if r["loop_remains"] else ""
        print(f"      repaired Whisper repeat loop {span}{note}")


def cmd_add(args: argparse.Namespace) -> int:
    """Ingest one video as a source pack with stable file names under <out>/<video-id>/."""
    from .context import fetch_comments, fetch_metadata
    from .visual import download_video, measure_rhythm, sample_frames

    load_env()
    video_id = extract_video_id(args.url)
    src = Path(args.out) / video_id
    src.mkdir(parents=True, exist_ok=True)
    cookies = {"cookies_browser": args.cookies_browser, "cookies_file": args.cookies_file}
    steps = 3 + int(args.with_comments) + int(args.with_frames)
    n = 0

    def step(msg: str) -> None:
        nonlocal n
        n += 1
        print(f"[{n}/{steps}] {msg}")

    print(f"[yt-kotoba] video_id = {video_id} -> {src}")
    step("metadata, description, thumbnail...")
    meta = fetch_metadata(video_id, src, **cookies)
    print(f"      -> {meta.get('title')}")

    step("audio + transcript (repeat loops are repaired)...")
    audio = src / "audio.m4a"
    if not (audio.exists() and audio.stat().st_size > 0):
        downloaded = download_audio(video_id, src, audio_format="m4a", **cookies)
        downloaded.rename(audio)
    transcript_path = src / "transcript.json"
    if transcript_path.exists() and transcript_path.stat().st_size > 0:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    else:
        transcript = transcribe_audio(audio, lang=args.lang)
        report = {"repaired": [], "detected_spans": 0, "skipped": bool(args.no_repair)}
        if not args.no_repair:
            transcript, report = repair_transcript(transcript, audio, args.lang)
            _print_repair(report)
        transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
        (src / "transcript_repair.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"      -> transcript.json ({len(transcript['segments'])} segments)")

    step("packing transcript...")
    (src / "packed.md").write_text(pack_transcript(transcript), encoding="utf-8")

    if args.with_comments:
        step("comments...")
        c = fetch_comments(video_id, src, max_comments=args.comments_max,
                           sort=args.comments_order, **cookies)
        k = c["counts"]
        print(f"      -> {c['status']}: {k['total']} total = {k['root']} root + {k['replies']} replies "
              f"({k['uploader_posts']} by uploader)")

    if args.with_frames:
        step(f"video, frames every {args.frame_every}s, contact sheets, picture-change rhythm...")
        video = download_video(video_id, src, max_height=args.max_height, **cookies)
        sample_frames(video, src, every_sec=args.frame_every)
        r = measure_rhythm(video, src)
        spans = ", ".join(f"th{t}: {v['sec_per_change']}s" for t, v in r["by_threshold"].items())
        print(f"      -> picture changes about every {spans}")
        if args.drop_video:
            video.unlink()
            print("      -> video.mp4 deleted (--drop-video)")

    manifest_path, _ = write_source_pack_manifest(src)
    print(f"\n[OK] {manifest_path}")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    out = download_audio(
        args.url,
        Path(args.out),
        args.audio_format,
        cookies_browser=args.cookies_browser,
        cookies_file=args.cookies_file,
    )
    print(out)
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    load_env()
    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}", file=sys.stderr)
        return 1
    if args.no_cache:
        result = transcribe_audio(audio_path, lang=args.lang)
        if args.diarize:
            result = diarize_transcript(
                audio_path,
                result,
                num_speakers=args.num_speakers,
                min_speakers=args.min_speakers,
                max_speakers=args.max_speakers,
            )
    else:
        result = transcribe_with_cache(audio_path, lang=args.lang)
        if args.diarize:
            result = diarize_with_cache(
                audio_path,
                result,
                num_speakers=args.num_speakers,
                min_speakers=args.min_speakers,
                max_speakers=args.max_speakers,
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    src = Path(args.transcript_json)
    with src.open(encoding="utf-8") as f:
        transcript = json.load(f)
    md = pack_transcript(transcript)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    else:
        print(md)
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    summary = run_source_qa(
        Path(args.source_dir),
        out_dir=Path(args.out) if args.out else None,
        max_telop_previews=args.max_telop_previews,
    )
    printable = {k: v for k, v in summary.items() if k != "issues"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0 if summary["issue_counts"]["error"] == 0 else 1


def cmd_manifest(args: argparse.Namespace) -> int:
    manifest_path, manifest = write_source_pack_manifest(Path(args.source_dir))
    print(json.dumps({"manifest": str(manifest_path), "schema": manifest["schema"]}, indent=2))
    return 0


def _add_diarization_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Label transcript segments by speaker with local pyannote.audio",
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        help="Known exact speaker count (improves diarization when accurate)",
    )
    parser.add_argument("--min-speakers", type=int, help="Minimum expected speaker count")
    parser.add_argument("--max-speakers", type=int, help="Maximum expected speaker count")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-kotoba",
        description="YouTube -> packed transcript. Delegate generation to your agent.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    cookies_help_browser = (
        "Extract cookies from this browser (chrome/edge/firefox/brave/...). "
        "Required for many YouTube videos due to anti-bot measures. "
        "Close the browser first to release the cookie DB lock."
    )
    cookies_help_file = "Path to a Netscape-format cookies.txt file (alternative)."

    p_run = sub.add_parser("run", help="End-to-end: URL -> packed.md")
    p_run.add_argument("url", help="YouTube URL or 11-char video ID")
    p_run.add_argument("--out", default="./output", help="Output directory")
    p_run.add_argument("--lang", default="ja", help="Transcription language (default: ja)")
    p_run.add_argument("--audio-format", default="m4a", help="Audio format")
    p_run.add_argument("--cookies-browser", help=cookies_help_browser)
    p_run.add_argument("--cookies-file", help=cookies_help_file)
    p_run.add_argument("--no-repair", action="store_true",
                       help="Do not re-transcribe Whisper repeat loops")
    _add_diarization_args(p_run)
    p_run.set_defaults(func=cmd_run)

    p_add = sub.add_parser(
        "add",
        help="Ingest a video as a source pack: <out>/<id>/ with metadata, transcript, "
             "optional comments and frames",
    )
    p_add.add_argument("url", help="YouTube URL or 11-char video ID")
    p_add.add_argument("--out", default="./sources/youtube",
                       help="Parent directory; files go to <out>/<video-id>/")
    p_add.add_argument("--lang", default="ja")
    p_add.add_argument("--no-repair", action="store_true",
                       help="Do not re-transcribe Whisper repeat loops")
    p_add.add_argument("--with-comments", action="store_true",
                       help="Fetch comments via yt-dlp (no API key) into comments.json")
    p_add.add_argument("--comments-max", type=int, default=2000)
    p_add.add_argument("--comments-order", choices=["top", "new"], default="top")
    p_add.add_argument("--with-frames", action="store_true",
                       help="Download video, sample frames, contact sheets, picture-change rhythm")
    p_add.add_argument("--frame-every", type=int, default=10, help="Seconds between frames")
    p_add.add_argument("--max-height", type=int, default=1080)
    p_add.add_argument("--drop-video", action="store_true",
                       help="Delete video.mp4 after frames are taken (saves disk)")
    p_add.add_argument("--cookies-browser", help=cookies_help_browser)
    p_add.add_argument("--cookies-file", help=cookies_help_file)
    p_add.set_defaults(func=cmd_add)

    p_dl = sub.add_parser("download", help="Download audio only")
    p_dl.add_argument("url")
    p_dl.add_argument("--out", default="./output")
    p_dl.add_argument("--audio-format", default="m4a")
    p_dl.add_argument("--cookies-browser", help=cookies_help_browser)
    p_dl.add_argument("--cookies-file", help=cookies_help_file)
    p_dl.set_defaults(func=cmd_download)

    p_tr = sub.add_parser("transcribe", help="Transcribe an existing audio file")
    p_tr.add_argument("audio")
    p_tr.add_argument("--lang", default="ja")
    p_tr.add_argument("--no-cache", action="store_true", help="Skip cache")
    _add_diarization_args(p_tr)
    p_tr.set_defaults(func=cmd_transcribe)

    p_pk = sub.add_parser("pack", help="Pack a transcript JSON into Markdown")
    p_pk.add_argument("transcript_json")
    p_pk.add_argument("--out")
    p_pk.set_defaults(func=cmd_pack)

    p_qa = sub.add_parser("qa", help="QA analysis JSON against a downloaded source video")
    p_qa.add_argument("source_dir", help="Directory containing video.mp4 and analysis JSON files")
    p_qa.add_argument("--out", help="Output QA directory (default: <source_dir>/qa)")
    p_qa.add_argument("--max-telop-previews", type=int, default=48)
    p_qa.set_defaults(func=cmd_qa)

    p_manifest = sub.add_parser(
        "manifest",
        help="Write source_pack_manifest.json for a source directory",
    )
    p_manifest.add_argument("source_dir", help="Directory containing source analysis files")
    p_manifest.set_defaults(func=cmd_manifest)

    return parser


def main() -> int:
    parser = build_parser()
    # Treat bare `yt-kotoba <url>` as `yt-kotoba run <url>` for ergonomics
    argv = sys.argv[1:]
    if argv and argv[0] not in {
        "run",
        "add",
        "download",
        "transcribe",
        "pack",
        "qa",
        "manifest",
        "-h",
        "--help",
    }:
        argv = ["run"] + argv
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except RuntimeError as e:
        print(f"yt-kotoba: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
