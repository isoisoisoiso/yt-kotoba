# yt-kotoba *(working title — name may change before v1.0)*

> YouTube 動画を **X スレ・Threads・note 記事・ブログ**へ展開する OSS。日本語ファースト。**外部 API キー一切不要**（Whisper はローカル / 生成は Claude Code 等のエージェントに委譲）。

> ⚠️ **Status: v0.1 (early preview)** — まだフィードバック受付中。名前・スコープが変わる可能性あり。本番運用前に [ROADMAP.md](./ROADMAP.md) を確認してください。

`yt-dlp` で音声を取り、`faster-whisper` (NVIDIA) または `mlx-whisper` (Apple Silicon) でローカル文字起こしし、**Claude Code / Cursor / その他のエージェントが SKILL.md を読んでその場で記事を生成**する設計。OpenAI Whisper API も Anthropic API も叩きません。

```
YouTube URL ──> 音声DL ──> 文字起こし ──> 構造化 ──> [agent reads packed.md]
                  yt-dlp     Whisper       packed.md   ↓
                                                       X スレ / Threads / note 記事
```

---

## 何ができるか

- **動画 → 構造化された LLM 用転写** (`packed.md`) を 1 コマンドで
- **agent-driven 生成**: Claude Code・Cursor 等が SKILL.md を読んで X スレ・Threads・note 記事を直接書く
- **完全ローカル文字起こし**: faster-whisper (CUDA) / mlx-whisper (M1/M2/M3) 自動選択
- **ブランドボイス**: `voice.yaml` で口調・禁則語・ハッシュタグをカスタム
- **キャッシュ**: 同じ動画は 1 度しか処理しない

## なぜ API キー不要なのか

「LLM を呼び出す側」ではなく、**「エージェントに読ませる skill」**として設計しているから。

- video-use (browser-use チーム) と同じ哲学
- ユーザーは Claude Code 等の上で skill を起動 → エージェント自身が packed.md を読んで生成
- これにより: ① API 課金ゼロ ② 任意の LLM で動く ③ プロンプト改造が SKILL.md 編集だけで済む

スタンドアロンの CLI で生成まで自動化したい場合は、`packed.md` を Ollama 等に流し込むラッパを自作してください（README 末尾参照）。

## インストール

```bash
# yt-dlp + ffmpeg
brew install yt-dlp ffmpeg            # macOS
scoop install yt-dlp ffmpeg           # Windows
sudo apt install yt-dlp ffmpeg         # Linux

# クローン
git clone https://github.com/<your-org>/yt-kotoba
cd yt-kotoba

# プラットフォーム別に依存をインストール
pip install -e ".[cuda]"   # NVIDIA GPU (Windows / Linux)
pip install -e ".[mlx]"    # Apple Silicon (macOS)
```

`.env` は**作らなくて OK**（オプション設定のみ。`.env.example` 参照）。

## 使い方

### 1. Claude Code skill として（推奨）

```bash
# シンボリックリンクで skill 化
ln -s "$(pwd)" ~/.claude/skills/yt-kotoba         # macOS / Linux
# Windows (管理者 PowerShell):
# New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\yt-kotoba" -Target "$(pwd)"
```

その後、任意の作業ディレクトリで Claude Code を起動して:

> この URL から X スレと note 記事作って: https://www.youtube.com/watch?v=XXXX

Claude Code が自動的に:
1. `yt-kotoba run <URL>` を叩いて `./output/XXXX.packed.md` を生成
2. SKILL.md を読んで生成ルールを把握
3. `./output/XXXX.x_thread.md` と `./output/XXXX.note.md` を直接書き出す

### 2. CLI 単体で

```bash
# packed.md まで自動生成（ここで CLI は止まる）
yt-kotoba run "https://www.youtube.com/watch?v=XXXX" --out ./output

# その後、お好みの LLM に packed.md を流し込む（例: Ollama）:
cat ./output/XXXX.packed.md | ollama run llama3 \
  "この動画の文字起こしから X スレを 5〜8 ツイートで作って" \
  > ./output/XXXX.x_thread.md
```

### サブコマンド（部分実行）

```bash
yt-kotoba download "URL" --out ./output           # 音声 DL のみ
yt-kotoba transcribe ./output/XXXX.audio.m4a      # 既存音声 → JSON
yt-kotoba pack ./output/XXXX.transcript.json      # 既存 JSON → packed.md
```

## 出力ファイル

```
output/
├── XXXX.audio.m4a        # ダウンロードした音声 (キャッシュ)
├── XXXX.transcript.json  # Whisper 出力 (キャッシュ)
└── XXXX.packed.md        # LLM 用の構造化済み転写 (← ここまで CLI が生成)

# 以下はエージェント（Claude Code 等）が SKILL.md を読んで書き出す
├── XXXX.x_thread.md      # X スレ
├── XXXX.threads.md       # Threads (Meta) 投稿
└── XXXX.note.md          # note 記事
```

## ブランドボイス設定

`<output_dir>/voice.yaml` を置くと、エージェントが SKILL.md のルールに従ってこれを適用:

```yaml
tone: "落ち着いた解説調、専門用語の濫用を避ける"
forbidden_words: ["絶対", "必ず", "100%"]
required_hashtags: ["#YouTube"]
signature: "── あなたのチャンネル名"
target_audience: "あなたのターゲット読者層を一言で"
```

`examples/voice.example.yaml` を出力ディレクトリにコピーして編集してください。

## なぜローカル Whisper か

- **OpenAI Whisper API は 1 分あたり $0.006**。100 本処理すると数千円
- **faster-whisper (CUDA)** は同精度・4 倍速・無料
- **mlx-whisper (Apple Silicon)** は Mac 上で完全オフライン動作
- 機密性の高い動画も外部 API に流さずに処理できる

## ライセンス

MIT — 自由に商用利用可。
