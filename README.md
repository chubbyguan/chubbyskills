<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

#### 我自己每天在用的一些 AI Skill，都开源在这里

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-2-10B981?style=for-the-badge)](#-skills)

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
| 🎬 [**douyin-transcribe（抖音转录）**](#-douyin-transcribe抖音转录) | 抖音视频 → 下载 → 转录 → Markdown，无需 cookie/登录，中文准确率超过 Whisper |
| 🎙️ [**podcast-transcribe（播客转录）**](#-podcast-transcribe播客转录) | 播客/小宇宙 → 下载 → 转录 → Markdown，支持 RSS 批量下载 |

---

## 📦 安装方式

在 Claude Code、Codex、OpenClaw、Hermes 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/chubbyxiaopangdun/chubbyskills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想装的那个，比如 `douyin-transcribe`、`podcast-transcribe`。Agent 会自己 clone 到对应目录，不用你操心路径。

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

- 🔗 支持抖音短链接（`v.douyin.com/xxx`）和完整链接
- ⚡ 极速转录：11 分钟视频仅需 22 秒
- 📝 自动生成带 frontmatter 的 Markdown 文件
- 🎯 中文准确率超过 Whisper，简体输出
- 🔒 无需登录、无需 cookie、无需 API Key

**怎么触发**

```
把这个抖音视频转成文字：https://v.douyin.com/xxxxx
帮我转录这个抖音
```

**性能数据**

| 视频时长 | 模型加载 | 转录耗时 | 总耗时 |
|------|------|------|------|
| 10 min | ~30s | ~25s | ~1 min |
| 30 min | ~30s | ~75s | ~2 min |
| 1h 22min | ~40s | ~180s | ~4 min |

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
- 📁 按集数自动命名，方便整理

**怎么触发**

```
帮我转录这个播客：https://www.xiaoyuzhoufm.com/episode/xxxxx
批量转录这个播客：http://www.ximalaya.com/album/xxxxx.xml
```

**适合**

- 内容创作者需要把播客转成文字稿
- 知识管理需要把音频内容沉淀到笔记系统
- 学习笔记整理
- 播客内容检索

**性能数据**

| 模型 | 速度 (CPU) | 中文准确率 |
|------|------|------|
| faster-whisper tiny | ~149s/1h | 一般 |
| faster-whisper small | ~10min/h | 良好 (~85-90%) |
| faster-whisper large-v3 | ~30-60min/h | 最佳 |

**🌐 跨平台**：Claude Code · Codex · OpenCode · OpenClaw · Hermes

→ [SKILL.md](./podcast-transcribe/SKILL.md) · [脚本](./podcast-transcribe/scripts/)

</td></tr>
</table>

---

## 🔧 环境要求

### douyin-transcribe

```bash
# Python 3.9+
python -m venv .venv
source .venv/bin/activate

# 依赖
pip install funasr modelscope torch torchaudio

# 系统依赖
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
```

### podcast-transcribe

```bash
# Python 3.9+
python -m venv .venv
source .venv/bin/activate

# 依赖
pip install faster-whisper

# 系统依赖
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
```

---

## 🌟 关于

我是 Chubby，一个在 AI 和内容创作领域折腾的普通人。这些 skill 都是我自己每天在用的，开源出来如果对你有帮助，给个 ⭐ 就行。有问题或建议，欢迎在 Issues / Discussions 里说一声。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@chubbyxiaopangdun](https://github.com/chubbyxiaopangdun)

</div>
