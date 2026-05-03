# AI Contributor Rules

This repository is public OSS. Treat every change as something that may be
read, copied, discussed, and run by people outside the original author's
environment.

## Non-negotiable OSS rules

- Never commit secrets, tokens, cookies, private URLs, local `.env` values, or
  personally identifiable data. Keep only safe placeholders in `.env.example`.
- Do not commit downloaded audio, transcripts from non-public/private videos,
  generated `output/` files, Whisper model caches, or other large artifacts.
- Keep examples, fixtures, and docs safe for redistribution. Use synthetic or
  clearly public sample material when sample content is needed.
- Preserve the project's local-first promise: no required OpenAI, Anthropic, or
  other paid/hosted LLM API calls. Optional integrations must be explicit,
  opt-in, documented, and must not change the default no-API-key workflow.
- Avoid telemetry, network calls, auto-update behavior, or external service
  dependencies unless they are essential, explicit, and documented.
- Respect the MIT license and do not paste third-party code or content unless
  its license is compatible and attribution requirements are met.

## Product invariants

- The CLI stops at `packed.md`. Downstream writing is performed by the agent
  reading `SKILL.md`, not by hidden LLM calls inside the Python package.
- Local Whisper backends remain the default transcription path:
  `faster-whisper` for CUDA and `mlx-whisper` for Apple Silicon.
- Output filenames stay deterministic by video ID:
  `<id>.audio.m4a`, `<id>.transcript.json`, `<id>.packed.md`, and agent-written
  derivatives such as `<id>.x_thread.md`.
- Keep Python support aligned with `pyproject.toml` (`>=3.9`) unless the project
  explicitly decides to raise it.
- Keep the project Japanese-first, but do not hard-code assumptions that block
  other transcription languages where the CLI already supports `--lang`.

## Update checklist

When changing behavior, update every surface that users or agents rely on:

- CLI flags, output paths, cache behavior, or install steps: update `README.md`.
- Agent generation behavior, output formats, or required self-checks: update
  `SKILL.md`.
- Scope, priorities, or future commitments: update `ROADMAP.md`.
- Dependencies, Python versions, entry points, or optional extras: update
  `pyproject.toml` and mirror the install docs.
- Config shape or brand-voice behavior: update `examples/voice.example.yaml`
  and the docs that describe it.

If a change affects contributors or AI agents, update this file. If a rule is
Claude-specific, update `CLAUDE.md` as well.

## Engineering expectations

- Keep changes small and reviewable. Do not mix unrelated refactors into user-
  visible feature or bug-fix changes.
- Prefer standard library and existing project structure before adding
  dependencies.
- Keep platform-specific behavior isolated and documented. Do not make macOS,
  Linux, Windows, CUDA, or Apple Silicon assumptions without a fallback or a
  clear error.
- Fail loudly when a local prerequisite is missing. Do not silently fall back to
  a paid API or external service.
- Before finishing code changes, run focused checks when available, usually:
  `python -m ruff check .` and relevant CLI smoke tests. If checks cannot be
  run because dev dependencies are missing, say so in the handoff.
