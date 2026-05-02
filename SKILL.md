---
name: yt-kotoba
description: Turn a YouTube video into an X thread, a note article, or other downstream Japanese text content. Local Whisper transcription (no OpenAI API needed) + agent-driven generation (no Anthropic API needed). Triggers on YouTube URLs combined with phrases like "X スレ作って" / "note 記事にして" / "この動画から記事書いて" / "repurpose this video" / "この動画を素材にして発信用に整えて".
---

# yt-kotoba

Take a YouTube video and turn it into multi-platform Japanese text content (X thread, note article, ...) through local Whisper transcription and **your own context as the LLM**. No external API key is ever needed — the agent reading this skill (Claude Code, Cursor, etc.) is itself the generator.

## Hard Rules (production correctness — non-negotiable)

These cause silent failures or broken output if violated. Memorize them.

1. **All session outputs go to `<user_dir>/output/`** — never write inside the `yt-kotoba/` project directory. The user invokes the skill from their working directory; outputs land there with deterministic names.
2. **Cache transcripts per video** — never re-transcribe a video whose audio file hasn't changed. The transcribe step writes `<id>.transcript.json` next to the audio; reuse it.
3. **Never invent content** — generated text must come from the transcript. Do not add facts, statistics, or quotes that aren't in `<id>.packed.md`. If the source is short / silent / non-substantive, say so and produce a shorter output rather than padding.
4. **Strict character limits on X output** — each tweet must be ≤ **140 Japanese characters** (count, don't estimate). Verify before showing the user.
5. **Use the local Whisper backend** — never silently fall back to a paid API. The whole point is local. Fail loudly if the local backend isn't installed.
6. **Confirm strategy before generation** — if the user asks vaguely ("この動画から何か作って"), surface 2–3 options (X thread? note article? both? blog?) and wait for confirmation before generating.
7. **All file writes are deterministic by video ID** — `<id>.audio.m4a`, `<id>.transcript.json`, `<id>.packed.md`, `<id>.x_thread.md`, `<id>.threads.md`, `<id>.note.md`. Never timestamp or randomize names.
8. **Apply `voice.yaml` if present** — if `<user_dir>/output/voice.yaml` (or `<user_dir>/voice.yaml`) exists, every generated artifact must obey its rules. Mention which rules are applied in your reply.

Everything else below is a worked example. Deviate when the material calls for it.

## Setup (first time only)

```bash
# yt-dlp + ffmpeg
brew install yt-dlp ffmpeg            # macOS
scoop install yt-dlp ffmpeg           # Windows

# Python deps (pick one)
pip install -e ".[cuda]"  # NVIDIA GPU (Win/Linux) — uses faster-whisper
pip install -e ".[mlx]"   # Apple Silicon — uses mlx-whisper
```

No API keys. No `.env` mandatory.

## Pipeline overview

```
User: "<URL> から X スレと note 記事作って"
   │
   ▼ Bash:  yt-kotoba run <URL> --out ./output
   │       ↳ download.py        →  <id>.audio.m4a       (cached)
   │       ↳ transcribe.py      →  <id>.transcript.json (cached)
   │       ↳ pack_transcript.py →  <id>.packed.md       (LLM reading view)
   │       (CLI stops here — no API call)
   │
   ▼ You (the agent):
   │   1. Read <id>.packed.md
   │   2. Apply the X / note generation rules below
   │   3. Write outputs directly to ./output/<id>.x_thread.md / .note.md
```

## Standard process

1. **Inventory.** Extract the video ID from the URL. Check if `<user_dir>/output/<id>.transcript.json` already exists — if so, skip download + transcribe and reuse.
2. **Strategy.** Confirm with the user: which outputs? (x / note / both / something else). Check for `voice.yaml` — if present, mention what brand-voice rules will be applied.
3. **Pipeline.** Run `yt-kotoba run <url> --out ./output`. This produces `<id>.packed.md`. **Do not call any external LLM API.**
4. **Read.** Read `<id>.packed.md` into your context. If it's longer than ~30K tokens, scan headers and pull the most substantive blocks — don't truncate silently.
5. **Generate.** Apply the generation rules below. Produce one file per requested format under `./output/`. **You are the LLM here — write the content directly using your own reasoning.**
6. **Self-check.** Before showing the user:
   - X thread: every tweet ≤ 140 Japanese chars (count, don't estimate)
   - All facts traceable to packed.md (no fabrication)
   - voice.yaml rules applied
   - Files saved to user dir, not skill dir
7. **Present.** Tell the user the file paths + show a preview (e.g. first 2 tweets, note title + lead). Don't dump full content unless asked.

## Sub-agents for parallel generation

When generating both X thread and note article, **spawn the two generations in parallel** via the `Agent` tool — they're independent and don't need to share context. Total wall time ≈ slowest single generation. Each sub-agent should be given the relevant section of this SKILL.md plus the packed.md.

## Generation rules

### X スレッド (`<id>.x_thread.md`)

Audience: 日本語 X (旧 Twitter) ユーザー。情報密度を高く、感情訴求は控えめに。

Structure:
- **5〜8 ツイート**のスレッド
- 各ツイート ≤ **140 Japanese 文字**（厳守、超過したら短縮 or 分割）
- 番号 (1/, 2/, ...) を必ず先頭に付ける
- 1 ツイート目 = **フックのみ**：読者が「続きを読みたい」と思う一行。問いかけ／意外な事実／逆説 を使う
- 中盤 = 動画の **最も価値ある学び・引用・具体例・数値**を 1 ツイート 1 ポイントで
- 最終ツイート = 要約 + 動画への誘導 (CTA)
- 絵文字: 0〜1 個 / ツイート（記号として控えめに）
- ハッシュタグ: voice.yaml の `required_hashtags` を最終ツイートに。指定なければ最大 1 個まで or 省略
- 動画にない情報を**絶対に捏造しない**

Output format:

```markdown
# X スレッド

## 1/
（1 ツイート目本文）

## 2/
（2 ツイート目本文）

...
```

### Threads 投稿 (`<id>.threads.md`)

Audience: Threads (Meta) ユーザー。Instagram 隣接層、X より文章長め・カジュアル・親密寄り。

X とは**性格が全く違う**ので、X スレを単純に転載してはいけない。投稿の単位・口調・改行感覚を Threads 用に作り直す。

Structure:
- **3〜5 投稿**の連続スレッド（X より少なめ・1 投稿あたりの密度高め）
- 各投稿 ≤ **500 字**（Threads の上限。日本語前提で実質 400-500 字が読み心地良い）
- 1 投稿目: **会話の入り口**。X の "フック" より柔らかく、問いかけや観察から始める（"〜って思うんですよね" 系）
- 中盤: **1 投稿 = 1 つの考えのまとまり**。改行を多めに使い、読み下ししやすく
- 最終投稿: 結びと（必要なら）動画への誘導。CTA は弱め
- 番号 (1/N, 2/N, ...) **付けない**（Threads の文化として番号付きは少ない）
- ハッシュタグ: 最終投稿に最大 3 個、自然に文末に置く（X より緩い）
- 絵文字: 1 投稿 1〜3 個 OK（X より多め）
- 動画にない情報を**絶対に捏造しない**

X との違いまとめ:

| | X | Threads |
|---|---|---|
| 1 投稿の長さ | 140 字 | 500 字 |
| 投稿数 | 5〜8 | 3〜5 |
| トーン | 情報密度高・断定的 | 会話的・ゆるい |
| 番号 | 1/, 2/ で明示 | 付けない |
| ハッシュタグ | 1〜2 個・終盤に | 最大 3 個・自然に |
| 絵文字 | 0〜1 個 | 1〜3 個 OK |
| フック | 強い問いかけ・意外な事実 | 柔らかい観察・共感 |

Output format:

```markdown
# Threads 投稿

## 1
（1 投稿目本文・500 字以内）

## 2
（2 投稿目本文）

...
```

### note 記事 (`<id>.note.md`)

Audience: note.com 読者。落ち着いた解説調、結論まで読ませるリード文設計。

Structure:
- 全体 **1500〜3000 字**（日本語）
- **タイトル** ≤ 30 字、クリックされる強さ（数字 / 意外性 / 問い）
- **リード文** ≤ 150 字、結論を匂わせるが言い切らない
- **見出し (H2) を 3〜5 個**、各セクション 200〜500 字
- 動画からの**引用は `---` で区切り**、誰が何と言ったかを明示
- **まとめセクション**で「動画から得られる行動指針」を箇条書き 3 点
- 動画にない情報を**絶対に捏造しない**
- voice.yaml の `signature` があれば末尾に追加

Output format:

```markdown
# （タイトル）

（リード文）

## （見出し1）

（本文）

## （見出し2）

（本文）

## まとめ

- 行動指針 1
- 行動指針 2
- 行動指針 3
```

## Brand voice config (`voice.yaml`)

If the user's output dir contains `voice.yaml`, every generation must obey it:

```yaml
tone: "落ち着いた解説調、専門用語の濫用を避ける"
forbidden_words: ["絶対", "必ず", "100%"]
required_hashtags: ["#YouTube"]
signature: "── あなたのチャンネル名"
target_audience: "あなたのターゲット読者層を一言で"
```

Application:
- `tone` → 文体・敬語レベルを合わせる
- `forbidden_words` → 出力に含まれていないか自己 grep して確認
- `required_hashtags` → X スレ最終ツイートに必ず含める
- `signature` → note 記事末尾に追加
- `target_audience` → 用語選択・前提知識レベルを調整

If the user mentions tone preferences in chat ("もっとカジュアルに" / "硬めの口調で") and there's no voice.yaml, **offer to create one** so the next run picks it up automatically.

## Common pitfalls

- **First run downloads the Whisper model (~3GB)** — warn the user before kicking off, especially on metered connections.
- **CUDA OOM on small GPUs** — set `WHISPER_COMPUTE_TYPE=int8` in `.env` to halve VRAM.
- **Long videos (>30 min)** — `<id>.packed.md` grows large; consider passing `--block-chars 600` to `yt-kotoba pack` to make blocks bigger.
- **Non-Japanese videos** — pass `--lang en` (or other ISO code). The default generation rules above target Japanese output; for non-Japanese final output, adapt the rules in this SKILL.md to the target language.
- **Tweet character counting** — Japanese characters count 1 each in X's display, but the safer rule is **140 文字** (not 280). Count zenkaku and hankaku both as 1.

## Worked example

```
User: "この動画から X スレと note 記事作って https://www.youtube.com/watch?v=XXXXXXXXXXX"

You: "了解です。次の処理を行います:
       1. 音声 DL → ローカル Whisper で文字起こし
       2. 構造化（章ブロック化）
       3. 私（Claude Code）が packed.md を読んで X スレと note 記事を生成
     出力先は ./output/ になります。
     voice.yaml は見つかりませんでした。ブランドボイス指定なしで進めて良いですか？"

User: "OK"

You: [Bash: yt-kotoba run https://www.youtube.com/watch?v=XXXX --out ./output]
     → ./output/XXXX.audio.m4a, .transcript.json, .packed.md が生成される

[Read: ./output/XXXX.packed.md]
[このスキルの「Generation rules」に従って X スレと note 記事を構成]
[Write: ./output/XXXX.x_thread.md]
[Write: ./output/XXXX.note.md]
[Verify: 各 tweet が 140 字以内 / fact が packed.md にある / 捏造なし]

You: "完了しました。
     - ./output/XXXX.x_thread.md (6 ツイート)
     - ./output/XXXX.note.md (約 2100 字)
     X スレ 1〜2 ツイート目のプレビュー:
     1/ ...
     2/ ..."
```
