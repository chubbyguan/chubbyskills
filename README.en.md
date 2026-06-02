<div align="center">

[中文](./README.md) · **English**

# 🧰 Chubby Skills

#### AI Skills I use daily, all open-sourced

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-3-10B981?style=for-the-badge)](#-skills)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-8B5CF6?style=flat-square)
![Hermes](https://img.shields.io/badge/Hermes-Skill-EC4899?style=flat-square)

</div>

These are AI Skills I've been using in my own projects. They've proven useful, so I'm open-sourcing them.

Each Skill here is a structured instruction set that Agents can load directly, following the [Agent Skills](https://agentskills.io) open standard. Works with Claude Code, Codex, OpenCode, OpenClaw, and Hermes.

---

## 📋 Table of Contents

| Name | Description |
|---|---|
| 🎬 [**douyin-transcribe**](#-douyin-transcribe) | Douyin video → download → transcribe → Markdown, no cookie/login needed, Chinese accuracy exceeds Whisper |
| 🎙️ [**podcast-transcribe**](#-podcast-transcribe) | Podcast/Xiaoyuzhou → download → transcribe → Markdown, supports RSS batch download |
| 📺 [**bilibili-transcribe**](#-bilibili-transcribe) | Bilibili video → download → transcribe → Markdown, no login needed |

---

## 📦 Installation

In any Agent that supports Skills (Claude Code, Codex, OpenClaw, Hermes, etc.), just say:

```
Install this skill: https://github.com/chubbyxiaopangdun/chubbyskills/tree/main/<skill-name>
```

Replace `<skill-name>` with the one you want, like `douyin-transcribe`, `podcast-transcribe`, or `bilibili-transcribe`. The Agent will clone it to the right directory automatically.

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

### douyin-transcribe / bilibili-transcribe

```bash
# Python 3.9+
python -m venv .venv
source .venv/bin/activate

# Dependencies
pip install funasr modelscope torch torchaudio

# System dependencies
# macOS: brew install ffmpeg yt-dlp
# Ubuntu: sudo apt install ffmpeg && pip install yt-dlp
```

### podcast-transcribe

```bash
# Python 3.9+
python -m venv .venv
source .venv/bin/activate

# Dependencies
pip install faster-whisper

# System dependencies
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
```

---

## 🌟 About

I'm Chubby, an ordinary person折腾 in AI and content creation. These are skills I use daily. If they help you, give it a ⭐. Issues and discussions welcome.

---

<div align="center">

[MIT License](./LICENSE) · Free to use / modify / redistribute

Made by [@chubbyxiaopangdun](https://github.com/chubbyxiaopangdun)

</div>
