<div align="center">

[中文](./README.md) · **English**

# 🧰 Chubby Skills

#### Your feed forgets. Your knowledge base doesn't. — pull content from everywhere into your second brain

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-14-10B981?style=for-the-badge)](#-skills)
[![Stars](https://img.shields.io/github/stars/chubbyguan/chubbyskills?style=for-the-badge&color=F59E0B)](https://github.com/chubbyguan/chubbyskills/stargazers)
[![Hype Weekly](https://img.shields.io/badge/🔥_Featured_on-Hype_ML%2FAI-FF6B35?style=for-the-badge)](https://github.com/chubbyguan/chubbyskills)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-8B5CF6?style=flat-square)
![Hermes](https://img.shields.io/badge/Hermes-Skill-EC4899?style=flat-square)

</div>

These are AI Skills I've been using in my own projects. They've proven useful, so I'm open-sourcing them.

Each Skill here is a structured instruction set that Agents can load directly, following the [Agent Skills](https://agentskills.io) open standard. Works with Claude Code, Codex, OpenCode, OpenClaw, and Hermes.

## ✨ What it does for you

- 📥 **Multi-platform ingest** — Douyin, Bilibili, Xiaohongshu, WeChat, X, podcasts, YouTube; just drop a link
- 🎬 **Auto image/video routing** — image notes keep their images, video notes get transcribed
- ⚡ **Subtitle-first, no GPU** — instant text when YouTube/Bilibili captions exist
- 🧠 **Into your knowledge base** — unified Markdown for Obsidian, plus an MCP server so any agent can query your vault
- 🧩 **Each skill installs independently** — grab only what you need; image/text ingest is zero-dependency

> In one line: **turn Chinese content from everywhere into your own searchable second brain.**

---

## 🚀 Quick Start

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/check_env.py
```

Install only what you need:

```bash
bash setup.sh          # light mode: text/image ingest + knowledge tools
bash setup.sh video    # ffmpeg + yt-dlp + funasr/torch stack
bash setup.sh podcast  # faster-whisper stack
bash setup.sh wechat   # WeChat/PDF extraction stack
bash setup.sh all      # everything
```

Run the one-command workflow:

```bash
python3 tools/chubby_ingest.py "https://www.bilibili.com/video/BVxxxx" -o output/
python3 tools/chubby_ingest.py "https://x.com/user/status/123" -o output/ --enrich
python3 tools/chubby_ingest.py "https://mp.weixin.qq.com/s/xxx" --vault ~/Documents/Obsidian/Inbox
```

Validate generated Markdown:

```bash
python3 tools/validate_outputs.py examples/outputs
python3 tools/validate_outputs.py output/
```

## 🧭 Capability Matrix

| Capability | Scope | Dependencies | Notes |
|---|---|---|---|
| Subtitle-first transcription | Bilibili / YouTube | `yt-dlp` | Falls back to audio transcription when no captions exist |
| Video transcription | Douyin / Bilibili / TikTok / Weibo / Zhihu / YouTube / XHS video / X video | `ffmpeg` + `funasr` + `torch` | Heavy first install; platform anti-bot rules may affect downloads |
| Podcast transcription | Xiaoyuzhou / Ximalaya / RSS / local audio | `ffmpeg` + `faster-whisper` | Long episodes can take time |
| Image/text ingest | Xiaohongshu / X / WeChat | light or zero pip deps | XHS works better with `XHS_COOKIE` |
| Enrichment | Any Markdown output | `DEEPSEEK_API_KEY` | Adds summary, key points, tags |
| Knowledge base | Obsidian vault | health check is zero-dep; MCP needs `mcp` | Set `VAULT_DIR` for MCP |
| One-command workflow | common links and local audio/PDF | uses matching skill deps | Override with `--skill` when detection is ambiguous |

---

## 📋 Table of Contents

### Video transcription
| Skill | Platform | One-liner |
|---|---|---|
| 🎬 **douyin-transcribe** | Douyin | Video → transcribe → Markdown |
| 📺 **bilibili-transcribe** | Bilibili | Video → subtitle-first transcribe → Markdown |
| 🎵 **tiktok-transcribe** | TikTok | Video → transcribe → Markdown |
| 📱 **weibo-transcribe** | Weibo | Video → transcribe → Markdown |
| 💡 **zhihu-transcribe** | Zhihu | Video → transcribe → Markdown |
| 🌍 **youtube-transcribe** | YouTube | Subtitle-first → transcribe → CN translation |

### Podcast
| Skill | Platform | One-liner |
|---|---|---|
| 🎙️ **podcast-transcribe** | Xiaoyuzhou / Ximalaya | Podcast → transcribe → Markdown (RSS batch) |

### Content ingest
| Skill | Platform | One-liner |
|---|---|---|
| 📰 **wechat-article-ingest** | WeChat | Article → Markdown + A/B insight extraction |
| 📕 **xiaohongshu-ingest** | Xiaohongshu | Image saved / video transcribed + hook analysis |
| 🐦 **x-ingest** | X / Twitter | Tweet → image saved / video transcribed (no login) |

### Enrich & knowledge base
| Skill | One-liner |
|---|---|
| ✨ **content-enrich** | Auto-add summary + key points + tags to any ingested note |
| 🧠 **knowledge-base-management** | Vault lifecycle + health check + **MCP server** |
| 📡 **industry-intelligence-radar** | Multi-source scan → daily intel brief |
| 📚 **learning-notes-automation** | Transcript → key points → Anki flashcards |

---

## 📦 Installation

### Option 1: Staged install (Recommended)

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
bash setup.sh          # light mode
bash setup.sh video    # video transcription stack
bash setup.sh podcast  # podcast transcription stack
bash setup.sh wechat   # WeChat/PDF extraction stack
bash setup.sh all      # everything
```

### Option 2: Manual install

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
pip install -r requirements.txt            # All skills
pip install -r podcast-transcribe/requirements.txt   # Single skill
```

### Option 3: Agent install

In any Agent that supports Skills (Claude Code, Codex, OpenClaw, Hermes, etc.), just say:

```
Install this skill: https://github.com/chubbyguan/chubbyskills/tree/main/<skill-name>
```

---

## ✨ Skills

<a id="-skills"></a>

<table>
<tr><td>

### 🎬 douyin-transcribe

> *"Transcribing Douyin videos used to be a hassle with cookies and yt-dlp. Now it's one command."*

Douyin video → download audio → SenseVoice-Small transcribe → save as Markdown. Supports short links and full links. No cookies, no login, no yt-dlp needed.

**Why SenseVoice over Whisper**

| | faster-whisper | SenseVoice-Small |
|------|------|------|
| Chinese accuracy | Average | **Exceeds Whisper** |
| Speed (CPU) | tiny: 149s/1h, small: 10-15min | **RTF ~0.04, 1h audio ≈ 2-3 min** |
| VAD | Extra setup needed | **Built-in fsmn-vad** |

**What it does**

- 🔗 Supports Douyin short links (`v.douyin.com/xxx`) and full links
- ⚡ Fast transcription: 11-minute video in just 22 seconds
- 📝 Auto-generates Markdown with frontmatter
- 🎯 Chinese accuracy exceeds Whisper, simplified Chinese output
- 🔒 No login, no cookies, no API Key needed

→ [SKILL.md](./douyin-transcribe/SKILL.md) · [Scripts](./douyin-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 🎙️ podcast-transcribe

> *"Can't finish listening to podcasts? Turn them into text."*

Podcast audio → download → faster-whisper transcribe → save as Markdown. Supports Xiaoyuzhou, Ximalaya, and other platforms. RSS batch download supported.

**What it does**

- 🎧 Supports Xiaoyuzhou, Ximalaya, and other podcast platforms
- 📡 RSS batch download for entire podcast seasons
- 📝 Auto-generates Markdown with timestamps
- ⏱️ Resume support, skips already transcribed episodes
- 📁 Auto-naming by episode number

**Performance**

| Model | Speed (CPU) | Chinese Accuracy |
|------|------|------|
| faster-whisper tiny | ~149s/1h | Average |
| faster-whisper small | ~10min/h | Good (~85-90%) |
| faster-whisper large-v3 | ~30-60min/h | Best |

→ [SKILL.md](./podcast-transcribe/SKILL.md) · [Scripts](./podcast-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 📺 bilibili-transcribe

> *"So many great videos on Bilibili, now I can read them as text."*

Bilibili video → yt-dlp download audio → SenseVoice-Small transcribe → save as Markdown. Supports BV IDs and full links. No login needed.

**What it does**

- 📺 Supports Bilibili BV IDs and full links
- ⚡ Fast transcription: 7-minute video in just 15 seconds
- 📝 Auto-generates Markdown with frontmatter
- 🎯 High Chinese accuracy, simplified Chinese output
- 🔒 No login, no cookies needed

**Triggers**

```
Transcribe this Bilibili video: https://www.bilibili.com/video/BV1rrQGBeEen/
Help me transcribe this bilibili
```

**Performance**

| Video Duration | Transcription Time |
|------|------|
| 5 min | ~10s |
| 10 min | ~20s |
| 30 min | ~60s |

**🌐 Cross-platform**: Claude Code · Codex · OpenCode · OpenClaw · Hermes

→ [SKILL.md](./bilibili-transcribe/SKILL.md) · [Scripts](./bilibili-transcribe/scripts/)

</td></tr>
</table>

---

## 🔧 Requirements

### Quick install

```bash
bash setup.sh          # All dependencies
bash setup.sh podcast  # Specific skill only
```

### douyin-transcribe / bilibili-transcribe / youtube-transcribe

```bash
pip install -r douyin-transcribe/requirements.txt
# System: brew install ffmpeg yt-dlp  # macOS
```

### podcast-transcribe

```bash
pip install -r podcast-transcribe/requirements.txt
# System: brew install ffmpeg  # macOS
```

---

## 🌟 About

I'm Chubby, an indie creator tinkering with AI and content. I like to auto-collect everything I come across — videos, podcasts, articles, Xiaohongshu, tweets — into my own knowledge base so it actually sticks instead of being forgotten. These skills are what I use daily for exactly that. If they help, give it a ⭐. Issues and discussions welcome.

- 🐦 [X / Twitter](https://x.com/Chubbyguan)
- 💬 [Jike (即刻)](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5)
- 📕 [Xiaohongshu](https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8)
- 📰 WeChat Official Account: **关关不过**

---

<div align="center">

[MIT License](./LICENSE) · Free to use / modify / redistribute

Made by [@chubbyguan](https://github.com/chubbyguan)

</div>
