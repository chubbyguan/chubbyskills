---
name: zhihu-transcribe
description: >
  知乎视频 → 下载 → 转录 → 存为 Markdown。
  支持知乎视频链接，无需登录。
category: media
triggers:
  - 用户发送知乎视频链接
  - "把这个知乎视频转成文字"
  - "帮我转录这个知乎"
version: 1.0.0
tags: [media, video, transcription, zhihu]
---

# 知乎视频转录 Skill

将知乎视频下载音频，用 SenseVoice-Small 转录为文字，存为 Markdown 文件。

## 环境要求

```bash
pip install funasr modelscope torch torchaudio
brew install ffmpeg yt-dlp  # macOS
```

## 使用方法

```bash
python scripts/transcribe.py "https://www.zhihu.com/xxxxx"
python scripts/transcribe.py "https://www.zhihu.com/video/xxxxx"
```

## 流程

1. yt-dlp 下载知乎视频音频
2. SenseVoice-Small 转录
3. 生成带 frontmatter 的 Markdown

## 已知限制

- 部分知乎视频可能需要登录才能访问
- SenseVoice-Small 主要针对中文优化

## 致谢

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型
