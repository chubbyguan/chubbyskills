---
name: douyin-transcribe
description: >
  抖音视频 → 下载 → 转录 → 存为 Markdown 的完整工作流。
  支持短链接和完整链接，无需 cookie/登录。
category: media
triggers:
  - 用户发送抖音分享链接或口头提到要转录抖音视频
  - "把这个抖音视频转成文字"
  - "帮我转录这个抖音"
version: 1.0.0
tags: [media, audio, video, transcription, douyin]
---

# 抖音视频转录 Skill

将抖音视频下载音频，用 SenseVoice-Small 转录为文字，存为 Markdown 文件。

## 环境要求

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

## 使用方法

```bash
python scripts/transcribe.py "https://v.douyin.com/xxxxx"
```

## 流程（3 步）

### Step 1: 从抖音下载音频

使用 `iesdouyin.com/share/video/<id>` + 移动端 UA 获取 `window._ROUTER_DATA`，提取 CDN 下载链接。

**关键点：**
- ✅ `iesdouyin.com/share/video/` 而非 `douyin.com/video/`
- ✅ 移动端 UA 必须用 iPhone
- ✅ `playwm` → `play` 去水印
- ✅ 无需 cookie、无需登录、无需 yt-dlp

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

| 视频时长 | 模型加载 | 转录耗时 | 总耗时 |
|------|------|------|------|
| 10 min | ~30s | ~25s | ~1 min |
| 30 min | ~30s | ~75s | ~2 min |
| 1h 22min | ~40s | ~180s | ~4 min |

## 已知限制

- SenseVoice-Small 模型首次下载约 893MB（从 ModelScope，国内快）
- CPU 推理质量略低于 GPU，但中文仍优于 Whisper-small
- VAD 自动切分可能把长停顿处切成两段
- 不支持说话人分离
- yt-dlp 不可用（需要 cookie），必须走 iesdouyin 路线

## 参考项目

- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) - 语音识别模型
- [FunASR](https://github.com/modelscope/FunASR) - 语音识别框架
- [vangie/douyin-transcriber](https://github.com/vangie/douyin-transcriber) - 原始灵感（Go CLI）
