<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

#### 我自己每天在用的一些 AI Skill，都开源在这里

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-8-10B981?style=for-the-badge)](#-skills)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-8B5CF6?style=flat-square)
![Hermes](https://img.shields.io/badge/Hermes-Skill-EC4899?style=flat-square)

</div>

**我是 Chubby**，一个在 AI 和内容创作领域折腾的普通人。

- 🐦 [X/Twitter](https://x.com/Chubbyguan)
- 💬 [即刻](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5)

---

都是在自己项目里跑通了一段时间，确实省事，才搬出来开源的。没什么花活，就是几个挺实用的东西。

这里的每个 Skill 都是 Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex、OpenCode、OpenClaw、Hermes 都能装。

---

## 📋 目录

### 视频转录

| 名字 | 平台 | 一句话 |
|---|---|---|
| 🎬 [**douyin-transcribe**](#-douyin-transcribe抖音转录) | 抖音 | 抖音视频 → 转录 → Markdown |
| 📺 [**bilibili-transcribe**](#-bilibili-transcribeb-站转录) | B站 | B站视频 → 转录 → Markdown |
| 🎵 [**tiktok-transcribe**](#-tiktok-transcribetiktok-转录) | TikTok | TikTok 视频 → 转录 → Markdown |
| 📱 [**weibo-transcribe**](#-weibo-transcribe微博视频转录) | 微博 | 微博视频 → 转录 → Markdown |
| 💡 [**zhihu-transcribe**](#-zhihu-transcribe知乎视频转录) | 知乎 | 知乎视频 → 转录 → Markdown |
| 🌍 [**youtube-transcribe**](#-youtube-transcribeyoutube-转录翻译) | YouTube | YouTube → 转录 → 英文翻译 → 中英对照 |

### 播客转录

| 名字 | 平台 | 一句话 |
|---|---|---|
| 🎙️ [**podcast-transcribe**](#-podcast-transcribe播客转录) | 小宇宙/喜马拉雅 | 播客 → 下载 → 转录 → Markdown |

### 内容处理

| 名字 | 平台 | 一句话 |
|---|---|---|
| 📰 [**wechat-article-ingest**](#-wechat-article-ingest公众号处理) | 微信公众号 | 公众号链接 → Markdown + A层观点提取 + B层问题链 |

---

## 📦 安装方式

在 Claude Code、Codex、OpenClaw、Hermes 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/chubbyxiaopangdun/chubbyskills/tree/main/<skill-name>
```

---

## ✨ Skills

<a id="-skills"></a>

### 🎬 douyin-transcribe（抖音转录）

> *"想把抖音视频转成文字，以前得折腾半天 cookie 和 yt-dlp，现在一句话搞定。"*

抖音视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。

**致谢**：[vangie/douyin-transcriber](https://github.com/vangie/douyin-transcriber) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./douyin-transcribe/SKILL.md) · [脚本](./douyin-transcribe/scripts/)

---

### 📺 bilibili-transcribe（B 站转录）

> *"B 站那么多干货视频，终于可以转成文字慢慢看了。"*

B 站视频 → yt-dlp 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./bilibili-transcribe/SKILL.md) · [脚本](./bilibili-transcribe/scripts/)

---

### 🎵 tiktok-transcribe（TikTok 转录）

> *"TikTok 上的好内容，也能存下来慢慢看了。"*

TikTok 视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。支持 vm.tiktok.com 短链接。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./tiktok-transcribe/SKILL.md) · [脚本](./tiktok-transcribe/scripts/)

---

### 📱 weibo-transcribe（微博视频转录）

> *"微博上的视频内容，终于能转成文字了。"*

微博视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。支持 weibo.com 和 m.weibo.cn。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./weibo-transcribe/SKILL.md) · [脚本](./weibo-transcribe/scripts/)

---

### 💡 zhihu-transcribe（知乎视频转录）

> *"知乎上的视频回答，也能转成文字收藏了。"*

知乎视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./zhihu-transcribe/SKILL.md) · [脚本](./zhihu-transcribe/scripts/)

---

### 🌍 youtube-transcribe（YouTube 转录+翻译）

> *"英文 YouTube 终于能轻松看懂了。"*

YouTube 视频 → yt-dlp 下载 → SenseVoice-Small 转录 → 英文自动翻译成中文 → 输出中英对照 Markdown。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) · [DeepSeek](https://platform.deepseek.com/)

→ [SKILL.md](./youtube-transcribe/SKILL.md) · [脚本](./youtube-transcribe/scripts/)

---

### 🎙️ podcast-transcribe（播客转录）

> *"播客听不完？让它变成文字，想看就看。"*

播客音频 → 下载 → faster-whisper 转录 → 存为 Markdown。支持小宇宙、喜马拉雅，支持 RSS 批量下载。

**致谢**：[SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) · [OpenAI Whisper](https://github.com/openai/whisper)

→ [SKILL.md](./podcast-transcribe/SKILL.md) · [脚本](./podcast-transcribe/scripts/)

---

### 📰 wechat-article-ingest（公众号处理）

> *"公众号文章直接变成结构化知识。"*

微信公众号文章 → Markdown 提取 → A层观点提取 + B层问题链生成。支持直接链接抓取。

**致谢**：[microsoft/markitdown](https://github.com/microsoft/markitdown) · [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) · [dontbesilent](https://github.com/dontbesilent)

→ [SKILL.md](./wechat-article-ingest/SKILL.md) · [脚本](./wechat-article-ingest/scripts/)

---

## 🔧 环境要求

### 视频转录（抖音/B站/TikTok/微博/知乎/YouTube）

```bash
pip install funasr modelscope torch torchaudio
brew install ffmpeg yt-dlp  # macOS

# YouTube 翻译功能（可选）
export DEEPSEEK_API_KEY=*** 播客转录

```bash
pip install faster-whisper
brew install ffmpeg  # macOS
```

### 公众号处理

```bash
pip install beautifulsoup4 markitdown pymupdf
```

---

## 🙏 致谢

### 仓库结构灵感

- [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills) — 仓库结构和 README 风格参考

### 语音识别

- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 阿里开源的中文语音识别模型
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper 的 CTranslate2 实现
- [OpenAI Whisper](https://github.com/openai/whisper) — 开创性的语音识别模型

### 视频下载

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 强大的视频下载工具，支持上千个平台
- [vangie/douyin-transcriber](https://github.com/vangie/douyin-transcriber) — 抖音下载方案灵感

### 文档处理

- [microsoft/markitdown](https://github.com/microsoft/markitdown) — 文档转 Markdown 工具
- [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) — PDF 处理库

### AI Agent & 翻译

- [Agent Skills](https://agentskills.io) — Agent Skill 开放标准
- [DeepSeek](https://platform.deepseek.com/) — 翻译用 LLM
- [dontbesilent](https://github.com/dontbesilent) — A+B 双轨处理方法论
- [Hermes Agent](https://github.com/nousresearch/hermes-agent) — 这些 skill 的运行环境

感谢所有开源贡献者！🙏

---

## 🌟 关于

这些 skill 都是我自己每天在用的，开源出来如果对你有帮助，给个 ⭐ 就行。

- 🐦 [X/Twitter](https://x.com/Chubbyguan)
- 💬 [即刻](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5)

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@chubbyxiaopangdun](https://github.com/chubbyxiaopangdun)

</div>
