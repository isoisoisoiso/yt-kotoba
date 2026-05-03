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

## v0.2 — Project workspaces + YouTube context (next)

Shift from "one URL produces files under `./output/`" to a project-first
workflow. The user creates a project directory, decides the product/genre, then
adds videos as source material. Each video keeps metadata, comments, transcript,
and generated drafts together so agents can reuse the material without losing
source context.

Target workflow:

```bash
yt-kotoba init my-product --genre "Japanese business commentary"
cd my-product

yt-kotoba add "https://www.youtube.com/watch?v=XXXX" \
  --with-metadata \
  --with-comments \
  --comments-max 100
```

Target directory layout:

```text
my-product/
├── project.yaml          # product name, genre, audience, source policy
├── voice.yaml            # brand voice for generated outputs
├── sources/
│   └── youtube/
│       └── <video-id>/
│           ├── metadata.json
│           ├── description.md
│           ├── thumbnail.jpg
│           ├── comments.json
│           ├── audio.m4a
│           ├── transcript.json
│           └── packed.md
└── drafts/
    └── <video-id>/
        ├── x_thread.md
        ├── threads.md
        └── note.md
```

Implementation steps:

- [ ] Add `yt-kotoba init <project-dir>` to create a working project directory.
- [ ] Add `project.yaml` with product/genre/audience fields that agents can read
      before generating content.
- [ ] Add `yt-kotoba add <url>` as the project-root command for ingesting a
      YouTube source into `sources/youtube/<video-id>/`.
- [ ] Keep `yt-kotoba run <url> --out ./output` working as a legacy/simple mode
      until the project workflow is stable.
- [ ] Store source files with stable names inside each video directory rather
      than prefixing every file with the video ID.
- [ ] Update `SKILL.md` so agents treat the project root as the working context
      and write drafts under `drafts/<video-id>/`.
- [ ] Update `README.md` with the project workflow once the commands exist.

YouTube context collection:

- [ ] Fetch video metadata via YouTube Data API `videos.list`: title, channel,
      published date, duration, statistics, description, tags, and thumbnail
      URLs.
- [ ] Download the best available thumbnail from the metadata into
      `thumbnail.jpg` or `thumbnail.webp`.
- [ ] Fetch comments via YouTube Data API `commentThreads.list`.
- [ ] Fetch full replies via `comments.list(parentId=...)` when requested.
- [ ] Require `YOUTUBE_API_KEY` only when metadata/comments flags need the Data
      API. The default transcript-only path remains API-key-free.
- [ ] Add limits such as `--comments-max`, `--comments-order`, and
      `--include-replies` so large comment sections do not blow up context.
- [ ] Record API fetch status/errors in metadata so agents can distinguish
      "comments disabled", "API key missing", "quota exceeded", and "not
      requested".

Packing and reuse:

- [ ] Extend `packed.md` to include a compact source card: title, channel,
      description summary, thumbnail path, comment count, and source file paths.
- [ ] Include only selected/top comments in `packed.md`; keep full comments in
      `comments.json`.
- [ ] Preserve source references so generated drafts can reuse angles, patterns,
      and audience reactions without fabricating or copying unattributed text.

## v0.3 — More output formats

- [ ] Blog post generation (longer-form, SEO 寄り)
- [ ] LinkedIn post 形式
- [ ] Markdown front matter 自動生成（Hugo / Astro / Zenn 互換）

## v0.4+ — Input adapters (community-driven)

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
