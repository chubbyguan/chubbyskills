---
name: bilibili-transcribe
description: >
  哔哩哔哩视频 → 下载 → 转录 → 存为 Markdown 的完整工作流。
  支持 BV 号和完整链接，无需登录。
category: media
triggers:
  - 用户发送 B 站视频链接
  - "把这个 B 站视频转成文字"
  - "帮我转录这个 bilibili"
version: 1.0.0
tags: [media, audio, video, transcription, bilibili]
---

# B 站视频转录 Skill

将 B 站视频下载音频，用 SenseVoice-Small 转录为文字，存为 Markdown 文件。

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
```

## 使用方法

```bash
python scripts/transcribe.py "https://www.bilibili.com/video/BV1rrQGBeEen/"
python scripts/transcribe.py "BV1rrQGBeEen"
```

## 流程

### Step 1: yt-dlp 下载音频

B 站有反爬机制，需要加 User-Agent 和 Referer：

```bash
yt-dlp --extract-audio --audio-format mp3 --audio-quality 128K \
  --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ..." \
  --referer "https://www.bilibili.com" \
  "https://www.bilibili.com/video/BV1rrQGBeEen/"
```

### Step 2: SenseVoice-Small 转录

```python
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

model = AutoModel(
    model="iic/SenseVoiceSmall",
    trust_remote_code=True,
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 30000},
    device="cpu",
)

result = model.generate(input=audio_path, language="zh", use_itn=True, batch_size_s=60)
```

### Step 3: 生成 Markdown

自动创建带 frontmatter 的 Markdown 文件。

## 性能数据

| 视频时长 | 转录耗时 |
|------|------|
| 5 min | ~10s |
| 10 min | ~20s |
| 30 min | ~60s |

## 已知限制

- B 站 4K/1080P60 需要大会员，普通用户可下载 720P 以下
- SenseVoice-Small 模型首次下载约 893MB
- 不支持说话人分离
- 合集视频会下载第一个分 P

## 参考项目

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) - 语音识别模型
