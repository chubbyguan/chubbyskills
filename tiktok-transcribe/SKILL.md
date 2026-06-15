---
name: tiktok-transcribe
description: >
  TikTok 视频 → 下载 → 转录 → 存为 Markdown。
  支持 TikTok 链接，无需登录。
category: media
triggers:
  - 用户发送 TikTok 视频链接
  - "把这个 TikTok 转成文字"
  - "帮我转录这个 TikTok"
version: 1.0.0
tags: [media, video, transcription, tiktok]
---

# TikTok 视频转录 Skill

将 TikTok 视频下载音频，用 SenseVoice-Small 转录为文字，存为 Markdown 文件。

## 环境要求

```bash
pip install funasr modelscope torch torchaudio
brew install ffmpeg yt-dlp  # macOS
```

## 使用方法

```bash
python scripts/transcribe.py "https://www.tiktok.com/@user/video/xxxxx"
python scripts/transcribe.py "https://vm.tiktok.com/xxxxx"
```

## 流程

1. yt-dlp 下载 TikTok 音频
2. SenseVoice-Small 转录
3. 生成带 frontmatter 的 Markdown

## 已知限制

- TikTok 有地区限制，部分内容可能无法访问（脚本已默认 `--geo-bypass`）
- 脚本用 `language=auto` 自动识别中英文；但 SenseVoice-Small 对中文识别最佳，纯英文长视频建议改用 youtube-transcribe（含 Whisper + 翻译）

## 致谢

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型

## ⚖️ 合规声明

仅供**个人学习与研究**使用。请遵守目标平台的服务条款（ToS）与 robots 规则，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。下载内容的版权归原作者所有。
