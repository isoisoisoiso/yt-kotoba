"""Environment / config loading. No LLM credentials needed — generation is
delegated to whatever agent invokes the skill (Claude Code, Cursor, etc.).
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_env(start: Path | None = None) -> None:
    """Load .env from cwd / start dir / repo root, in that order."""
    if load_dotenv is None:
        return
    candidates = []
    if start is not None:
        candidates.append(start / ".env")
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parent.parent / ".env")
    for p in candidates:
        if p.exists():
            load_dotenv(p, override=False)


def get_whisper_model() -> str:
    return os.environ.get("WHISPER_MODEL", "large-v3").strip()


def get_whisper_compute_type() -> str:
    return os.environ.get("WHISPER_COMPUTE_TYPE", "float16").strip()


def get_whisper_device() -> str:
    return os.environ.get("WHISPER_DEVICE", "cuda").strip()
