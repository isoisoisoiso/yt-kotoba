# Claude Code Instructions

Before editing this repository, read and follow `AGENTS.md`. It is the
canonical AI contributor guide for this OSS project.

Minimum rules even if you only see this file:

- This is public OSS. Never commit secrets, cookies, private URLs, local `.env`
  values, personal data, downloaded media, private transcripts, or generated
  `output/` artifacts.
- Preserve the default no-API-key, local-first workflow. Do not add hidden
  OpenAI, Anthropic, hosted LLM, telemetry, or external service calls.
- The CLI should produce `packed.md`; agents read `SKILL.md` and generate
  downstream content themselves.
- When behavior changes, update the relevant docs in the same change:
  `README.md` for user-facing CLI/install behavior, `SKILL.md` for agent
  behavior, and `ROADMAP.md` for scope or priority changes.
