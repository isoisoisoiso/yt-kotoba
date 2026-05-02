# Roadmap

> Living document. Priorities shift based on user feedback. Open issues / discussions to influence direction.

## v0.1 — Pre-release (current)

The narrow MVP. Validates the core hypothesis: *local Whisper + agent-driven generation can replace paid SaaS for video → text repurposing.*

- [x] YouTube URL → 音声 DL (yt-dlp)
- [x] 音声 → 文字起こし (faster-whisper / mlx-whisper auto-pick)
- [x] 文字起こし → packed.md (LLM 用構造化)
- [x] SKILL.md による Claude Code agent への生成委譲
- [x] X スレ / Threads (Meta) / note 記事の生成ルール (in SKILL.md)
- [x] voice.yaml によるブランドボイス対応

## v0.2 — More outputs (next ~1 month)

- [ ] Blog post generation (longer-form, SEO 寄り)
- [ ] LinkedIn post 形式
- [ ] Markdown front matter 自動生成（Hugo / Astro / Zenn 互換）

## v0.3+ — Input adapters (community-driven)

The current pipeline assumes YouTube. The architecture is structured so additional input adapters can be added with minimal core changes.

- [ ] ローカル動画ファイル (mp4 / mov / m4a / wav) — 会議録音・講演用
- [ ] Vimeo URL
- [ ] ポッドキャスト RSS feed
- [ ] Obsidian Vault からの video link 自動拾い

## v0.5+ — Output integrations (Phase 2)

- [ ] Obsidian Vault への直接書き込み
- [ ] Notion API 経由でデータベース投入
- [ ] note 投稿 API（公開され次第）

## v1.0 — Name lock

By v1.0 we'll commit to a final name. The current `yt-kotoba` may evolve into something that better reflects the broader scope (e.g. `kotoba-loom` if we extend beyond YouTube). Migration will be automatic via GitHub redirects.

## Possibly later (no commitment)

- Frame extraction (ffmpeg-based) — content asset 用
- Speaker diarization (pyannote.audio) — 対談動画・会議用
- Local web dashboard for editing drafts (no auth, local-only)
- Cloudflare Workers cloud version (only if scale demands)

## Won't do

- 動画生成 (Sora / Veo / Venice 系統合) — 別プロダクトの守備範囲
- 動画編集 (cuts / overlays) — [video-use](https://github.com/browser-use/video-use) との併用を推奨
- テロップ自動除去 — 品質保証できないため見送り

## Contributing

Issues / discussions / PRs welcome. See `CONTRIBUTING.md` (TBD).
