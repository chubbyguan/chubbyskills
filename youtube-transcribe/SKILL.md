---
name: youtube-transcribe
description: >
  YouTube 视频 → 下载 → 转录 → 翻译 → 存为 Markdown。
  支持中英文，英文内容自动翻译成中文，输出中英对照。
category: media
triggers:
  - 用户发送 YouTube 视频链接
  - "把这个 YouTube 视频转成文字"
  - "帮我转录这个 YouTube"
  - "YouTube 翻译"
version: 1.0.0
tags: [media, audio, video, transcription, youtube, translation]
---

# YouTube 视频转录 + 翻译 Skill

将 YouTube 视频下载音频，用 SenseVoice-Small 转录，英文内容自动翻译成中文，输出中英对照 Markdown。

## 为什么需要这个

YouTube 有大量优质英文内容，但很多人没时间看完或语言不通。这个 skill：

- 转录视频为文字（支持中英文）
- 英文内容自动翻译成高质量中文
- 输出中英对照，方便学习

## 环境要求

```bash
# Python 3.9+
python -m venv .venv
source .venv/bin/activate

# 依赖
pip install funasr modelscope torch torchaudio

# 系统依赖
# macOS: brew install ffmpeg yt-dlp
# Ubuntu: sudo apt install ffmpeg && pip install yt-dlp

# 翻译功能（可选，英文视频需要）
export DEEPSEEK_API_KEY="your-api-key"
```

## 使用方法

```bash
python scripts/transcribe.py "https://www.youtube.com/watch?v=xxxxx"
python scripts/transcribe.py "https://www.youtube.com/watch?v=xxxxx" --output ./output
python scripts/transcribe.py "https://www.youtube.com/watch?v=xxxxx" --no-translate  # 不翻译
```

## 流程

### Step 1: yt-dlp 下载音频

```bash
yt-dlp --extract-audio --audio-format mp3 --audio-quality 128K \
  "https://www.youtube.com/watch?v=xxxxx"
```

### Step 2: SenseVoice-Small 转录

```python
from funasr import AutoModel
model = AutoModel(model="iic/SenseVoiceSmall", ...)
result = model.generate(input=audio_path, language="auto", use_itn=True)
```

### Step 3: 语言检测 + 翻译

- 中文内容 → 直接输出
- 英文内容 → LLM 翻译成中文，输出中英对照

### Step 4: 生成 Markdown

```markdown
---
title: 视频标题
type: note
tags: [YouTube]
language: en
translated: true
---

# 视频标题

> 转录引擎：SenseVoice-Small | 翻译：DeepSeek

## 中文翻译

翻译内容...

---

## English Original

原文内容...
```

## 翻译配置

默认使用 DeepSeek API 翻译。需要设置环境变量：

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

支持的 LLM：
- DeepSeek（推荐，性价比高）
- OpenAI
- 任何兼容 OpenAI API 格式的服务

## 性能数据

| 视频时长 | 下载 | 转录 | 翻译 | 总耗时 |
|------|------|------|------|------|
| 5 min | ~10s | ~5s | ~10s | ~30s |
| 10 min | ~15s | ~10s | ~20s | ~50s |
| 30 min | ~30s | ~30s | ~60s | ~2min |

## 已知限制

- SenseVoice-Small 对英文转录准确率不如中文
- 翻译质量取决于 LLM 能力
- 长视频翻译可能需要较长时间
- 部分 YouTube 视频有地区限制

## 参考项目

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) - 语音识别模型
- [DeepSeek](https://platform.deepseek.com/) - 翻译用 LLM
