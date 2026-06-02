<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

#### 我自己每天在用的一些 AI Skill，都开源在这里

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-5-10B981?style=for-the-badge)](#-skills)

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

| 名字 | 一句话 |
|---|---|
| 🎬 [**douyin-transcribe（抖音转录）**](#-douyin-transcribe抖音转录) | 抖音视频 → 下载 → 转录 → Markdown，无需 cookie/登录 |
| 🎙️ [**podcast-transcribe（播客转录）**](#-podcast-transcribe播客转录) | 播客/小宇宙 → 下载 → 转录 → Markdown，支持 RSS 批量 |
| 📺 [**bilibili-transcribe（B 站转录）**](#-bilibili-transcribeb-站转录) | B 站视频 → 下载 → 转录 → Markdown，无需登录 |
| 📰 [**wechat-article-ingest（公众号处理）**](#-wechat-article-ingest公众号处理) | 公众号链接 → Markdown + A层观点提取 + B层问题链 |
| 🌍 [**youtube-transcribe（YouTube 转录+翻译）**](#-youtube-trans录youtube-转录翻译) | YouTube → 下载 → 转录 → 英文翻译 → 中英对照 Markdown |

---

## 📦 安装方式

在 Claude Code、Codex、OpenClaw、Hermes 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/chubbyxiaopangdun/chubbyskills/tree/main/<skill-name>
```

---

## ✨ Skills

<a id="-skills"></a>

<table>
<tr><td>

### 🎬 douyin-transcribe（抖音转录）

> *"想把抖音视频转成文字，以前得折腾半天 cookie 和 yt-dlp，现在一句话搞定。"*

抖音视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。支持短链接和完整链接，无需 cookie、无需登录、无需 yt-dlp。

**为什么用 SenseVoice 而不是 Whisper**

| | faster-whisper | SenseVoice-Small |
|------|------|------|
| 中文准确率 | 一般 | **超过 Whisper** |
| 速度 (CPU) | tiny: 149s/1h, small: 10-15min | **RTF ~0.04, 1h 音频约 2-3 分钟** |
| VAD | 需额外配置 | **内置 fsmn-vad** |

**致谢**

- [vangie/douyin-transcriber](https://github.com/vangie/douyin-transcriber) — 抖音下载方案的灵感来源
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型
- [FunASR](https://github.com/modelscope/FunASR) — 语音识别框架

→ [SKILL.md](./douyin-transcribe/SKILL.md) · [脚本](./douyin-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 🎙️ podcast-transcribe（播客转录）

> *"播客听不完？让它变成文字，想看就看。"*

播客音频 → 下载 → faster-whisper 转录 → 存为 Markdown。支持小宇宙、喜马拉雅等平台，支持 RSS 批量下载。

**致谢**

- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper 的 CTranslate2 实现
- [OpenAI Whisper](https://github.com/openai/whisper) — 原始语音识别模型

→ [SKILL.md](./podcast-transcribe/SKILL.md) · [脚本](./podcast-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 📺 bilibili-transcribe（B 站转录）

> *"B 站那么多干货视频，终于可以转成文字慢慢看了。"*

B 站视频 → yt-dlp 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。支持 BV 号和完整链接，无需登录。

**致谢**

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 强大的视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型

→ [SKILL.md](./bilibili-transcribe/SKILL.md) · [脚本](./bilibili-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 📰 wechat-article-ingest（公众号处理）

> *"公众号文章直接变成结构化知识。"*

微信公众号文章 → Markdown 提取 → A层观点提取 + B层问题链生成。支持直接链接抓取，无需登录。

**A+B 双轨处理**

| 层级 | 输出 | 内容 |
|------|------|------|
| A层 | 观点提取.md | 核心观点矩阵（P1-P6, S1-S8, E1-E4）+ Takeaway |
| B层 | 问题链.md | 3-5 条问题链，每条 L1→L2→L3 递进 |

**致谢**

- [microsoft/markitdown](https://github.com/microsoft/markitdown) — 文档转 Markdown 工具
- [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) — PDF 处理库
- [dontbesilent](https://github.com/dontbesilent) — A+B 双轨处理方法论

→ [SKILL.md](./wechat-article-ingest/SKILL.md) · [脚本](./wechat-article-ingest/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 🌍 youtube-transcribe（YouTube 转录+翻译）

> *"英文 YouTube 终于能轻松看懂了。"*

YouTube 视频 → yt-dlp 下载 → SenseVoice-Small 转录 → 英文自动翻译成中文 → 输出中英对照 Markdown。

**它能做什么**

- 📺 支持所有 YouTube 视频
- 🎙️ SenseVoice-Small 转录，中英文都支持
- 🌐 英文内容自动翻译成高质量中文
- 📝 输出中英对照 Markdown，方便学习
- 🔒 无需登录、无需 cookie

**怎么触发**

```
把这个 YouTube 视频转成文字：https://www.youtube.com/watch?v=xxxxx
帮我转录这个 YouTube
YouTube 翻译
```

**输出效果**

```markdown
# 视频标题

## 中文翻译
这是一个3。它写得潦草，分辨率极低...

---

## English Original
This is a three. It is sloppily written...
```

**性能数据**

| 视频时长 | 下载 | 转录 | 翻译 | 总耗时 |
|------|------|------|------|------|
| 5 min | ~10s | ~5s | ~10s | ~30s |
| 10 min | ~15s | ~10s | ~20s | ~50s |
| 30 min | ~30s | ~30s | ~60s | ~2min |

**致谢**

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型
- [DeepSeek](https://platform.deepseek.com/) — 翻译用 LLM

**🌐 跨平台**：Claude Code · Codex · OpenCode · OpenClaw · Hermes

→ [SKILL.md](./youtube-transcribe/SKILL.md) · [脚本](./youtube-transcribe/scripts/)

</td></tr>
</table>

---

## 🔧 环境要求

### douyin-transcribe / bilibili-transcribe / youtube-transcribe

```bash
pip install funasr modelscope torch torchaudio
brew install ffmpeg yt-dlp  # macOS

# YouTube 翻译功能（可选）
export DEEPSEEK_API_KEY="your...
### podcast-transcribe

```bash
pip install faster-whisper
brew install ffmpeg  # macOS
```

### wechat-article-ingest

```bash
pip install beautifulsoup4 markitdown pymupdf
```

---

## 🙏 致谢

这个仓库的诞生离不开以下开源项目和创作者：

### 仓库结构灵感

- [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills) — 仓库结构和 README 风格参考

### 语音识别

- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 阿里开源的中文语音识别模型
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper 的 CTranslate2 实现
- [OpenAI Whisper](https://github.com/openai/whisper) — 开创性的语音识别模型

### 视频下载

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 强大的视频下载工具
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

这些 skill 都是我自己每天在用的，开源出来如果对你有帮助，给个 ⭐ 就行。有问题或建议，欢迎在 Issues / Discussions 里说一声。

- 🐦 [X/Twitter](https://x.com/Chubbyguan)
- 💬 [即刻](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5)

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@chubbyxiaopangdun](https://github.com/chubbyxiaopangdun)

</div>
