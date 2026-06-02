<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

#### 我自己每天在用的一些 AI Skill，都开源在这里

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-4-10B981?style=for-the-badge)](#-skills)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-8B5CF6?style=flat-square)
![Hermes](https://img.shields.io/badge/Hermes-Skill-EC4899?style=flat-square)

</div>

都是在自己项目里跑通了一段时间，确实省事，才搬出来开源的。没什么花活，就是几个挺实用的东西。

这里的每个 Skill 都是 Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex、OpenCode、OpenClaw、Hermes 都能装。

---

## 📋 目录

| 名字 | 一句话 |
|---|---|
| 🎬 [**douyin-transcribe（抖音转录）**](#-douyin-transcribe抖音转录) | 抖音视频 → 下载 → 转录 → Markdown，无需 cookie/登录 |
| 🎙️ [**podcast-transcribe（播客转录）**](#-podcast-transcribe播客转录) | 播客/小宇宙 → 下载 → 转录 → Markdown，支持 RSS 批量 |
| 📺 [**bilibili-transcribe（B 站转录）**](#-bilibili-transcribeb-站转录) | B 站视频 → 下载 → 转录 → Markdown，无需登录 |
| 📰 [**wechat-article-ingest（公众号处理）**](#-wechat-article-ingest公众号处理) | 公众号 PDF → Markdown + A层观点提取 + B层问题链 |

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

**它能做什么**

- 🔗 支持抖音短链接和完整链接
- ⚡ 极速转录：11 分钟视频仅需 22 秒
- 📝 自动生成带 frontmatter 的 Markdown 文件
- 🎯 中文准确率超过 Whisper，简体输出
- 🔒 无需登录、无需 cookie、无需 API Key

→ [SKILL.md](./douyin-transcribe/SKILL.md) · [脚本](./douyin-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 🎙️ podcast-transcribe（播客转录）

> *"播客听不完？让它变成文字，想看就看。"*

播客音频 → 下载 → faster-whisper 转录 → 存为 Markdown。支持小宇宙、喜马拉雅等平台，支持 RSS 批量下载。

**它能做什么**

- 🎧 支持小宇宙、喜马拉雅等播客平台
- 📡 RSS 批量下载，一次处理整季播客
- 📝 自动生成带时间戳的 Markdown 文件
- ⏱️ 支持断点续传，已转录的自动跳过

→ [SKILL.md](./podcast-transcribe/SKILL.md) · [脚本](./podcast-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 📺 bilibili-transcribe（B 站转录）

> *"B 站那么多干货视频，终于可以转成文字慢慢看了。"*

B 站视频 → yt-dlp 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。支持 BV 号和完整链接，无需登录。

**它能做什么**

- 📺 支持 B 站 BV 号和完整链接
- ⚡ 极速转录：7 分钟视频仅需 15 秒
- 📝 自动生成带 frontmatter 的 Markdown 文件
- 🔒 无需登录、无需 cookie

→ [SKILL.md](./bilibili-transcribe/SKILL.md) · [脚本](./bilibili-transcribe/scripts/)

</td></tr>
</table>

<table>
<tr><td>

### 📰 wechat-article-ingest（公众号处理）

> *"公众号文章存了一堆 PDF，终于可以结构化了。"*

微信公众号文章 PDF → Markdown 提取 → A层观点提取 + B层问题链生成。支持批量处理、长文档子主题拆分。

**为什么需要这个**

微信公众号文章没有稳定的网页抓取方式（反爬、需要登录），但可以通过「笔记同步助手」等工具导出 PDF。这个 skill 解决：

- PDF → Markdown 结构化提取
- 观点提取（A层）：核心观点矩阵 + Takeaway
- 问题链生成（B层）：L1→L2→L3 递进式提问
- 长文档自动拆子主题

**它能做什么**

- 📄 PDF → Markdown，保留标题/列表/表格结构
- 🔴 A层观点提取：支柱观点 + 支撑观点 + 延伸观点
- 🟡 B层问题链：安全区→边缘区→核心区递进提问
- 📁 长文档自动拆子主题，并行处理
- 📦 批量处理，一次处理多篇文章

**怎么触发**

```
帮我处理这篇文章：path/to/article.pdf
提取观点 + 问题链
处理素材库里最近的公众号文章
```

**A+B 双轨处理**

| 层级 | 输出 | 内容 |
|------|------|------|
| A层 | 观点提取.md | 核心观点矩阵（P1-P6, S1-S8, E1-E4）+ Takeaway |
| B层 | 问题链.md | 3-5 条问题链，每条 L1→L2→L3 递进 |

**适合**

- 内容创作者需要提取文章核心观点
- 知识管理需要结构化沉淀
- 学习笔记整理
- 播客/长视频文字稿深度处理

**🌐 跨平台**：Claude Code · Codex · OpenCode · OpenClaw · Hermes

→ [SKILL.md](./wechat-article-ingest/SKILL.md) · [脚本](./wechat-article-ingest/scripts/)

</td></tr>
</table>

---

## 🔧 环境要求

### douyin-transcribe / bilibili-transcribe

```bash
pip install funasr modelscope torch torchaudio
brew install ffmpeg yt-dlp  # macOS
```

### podcast-transcribe

```bash
pip install faster-whisper
brew install ffmpeg  # macOS
```

### wechat-article-ingest

```bash
pip install markitdown pymupdf
```

---

## 🌟 关于

我是 Chubby，一个在 AI 和内容创作领域折腾的普通人。这些 skill 都是我自己每天在用的，开源出来如果对你有帮助，给个 ⭐ 就行。有问题或建议，欢迎在 Issues / Discussions 里说一声。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@chubbyxiaopangdun](https://github.com/chubbyxiaopangdun)

</div>
