<div align="center">

[中文](./README.md) · **English**

# 🧰 Chubby Skills

#### AI Skills I use daily, all open-sourced

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-2-10B981?style=for-the-badge)](#-skills)

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

---

## 📦 Installation

In any Agent that supports Skills (Claude Code, Codex, OpenClaw, Hermes, etc.), just say:

```
Install this skill: https://github.com/chubbyxiaopangdun/chubbyskills/tree/main/<skill-name>
```

Replace `<skill-name>` with the one you want, like `douyin-transcribe` or `podcast-transcribe`. The Agent will clone it to the right directory automatically.

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

**Triggers**

```
Transcribe this podcast: https://www.xiaoyuzhoufm.com/episode/xxxxx
Batch transcribe: http://www.ximalaya.com/album/xxxxx.xml
```

**Performance**

| Model | Speed (CPU) | Chinese Accuracy |
|------|------|------|
| faster-whisper tiny | ~149s/1h | Average |
| faster-whisper small | ~10min/h | Good (~85-90%) |
| faster-whisper large-v3 | ~30-60min/h | Best |

**🌐 Cross-platform**: Claude Code · Codex · OpenCode · OpenClaw · Hermes

→ [SKILL.md](./podcast-transcribe/SKILL.md) · [Scripts](./podcast-transcribe/scripts/)

</td></tr>
</table>

---

## 🔧 Requirements

### douyin-transcribe

```bash
# Python 3.9+
python -m venv .venv
source .venv/bin/activate

# Dependencies
pip install funasr modelscope torch torchaudio

# System dependencies
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
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
