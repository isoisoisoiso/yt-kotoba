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
from .download import download_audio, extract_video_id
from .pack_transcript import pack_transcript
from .transcribe import transcribe_with_cache


def cmd_run(args: argparse.Namespace) -> int:
    load_env()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    video_id = extract_video_id(args.url)
    print(f"[yt-kotoba] video_id = {video_id}")

    print("[1/3] downloading audio...")
    audio_path = download_audio(
        args.url,
        out_dir,
        audio_format=args.audio_format,
        cookies_browser=args.cookies_browser,
        cookies_file=args.cookies_file,
    )
    print(f"      -> {audio_path.name}")

    print("[2/3] transcribing (this may take a while on first run)...")
    transcript = transcribe_with_cache(audio_path, lang=args.lang)
    transcript_path = out_dir / f"{video_id}.transcript.json"
    print(f"      -> {transcript_path.name}  ({len(transcript['segments'])} segments)")

    print("[3/3] packing transcript...")
    packed = pack_transcript(transcript)
    packed_path = out_dir / f"{video_id}.packed.md"
    packed_path.write_text(packed, encoding="utf-8")
    print(f"      -> {packed_path.name}")

    print("\n[OK] pipeline done.")
    print(f"\n     Next: feed {packed_path.name} to your agent (Claude Code etc).")
    print(f"     The agent reads SKILL.md and produces X thread / note article")
    print(f"     directly into {out_dir}/")
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
    result = transcribe_with_cache(audio_path, lang=args.lang)
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
    p_run.set_defaults(func=cmd_run)

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
    p_tr.set_defaults(func=cmd_transcribe)

    p_pk = sub.add_parser("pack", help="Pack a transcript JSON into Markdown")
    p_pk.add_argument("transcript_json")
    p_pk.add_argument("--out")
    p_pk.set_defaults(func=cmd_pack)

    return parser


def main() -> int:
    parser = build_parser()
    # Treat bare `yt-kotoba <url>` as `yt-kotoba run <url>` for ergonomics
    argv = sys.argv[1:]
    if argv and argv[0] not in {"run", "download", "transcribe", "pack", "-h", "--help"}:
        argv = ["run"] + argv
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
