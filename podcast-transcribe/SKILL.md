---
name: podcast-transcribe
description: >
  播客/小宇宙 → 下载 → 转录 → 存为 Markdown 的完整工作流。
  支持 RSS 批量下载、单集链接转录。
category: media
triggers:
  - 用户发送小宇宙/播客链接
  - "帮我转录这个播客"
  - "下载播客"
  - "批量转录播客"
version: 1.1.0
tags: [media, audio, podcast, transcription, xiaoyuzhou]
---

# 播客转录 Skill

将播客音频下载并转录为文字，存为 Markdown 文件。支持小宇宙、喜马拉雅等平台。

## 环境要求

```bash
# Python 3.9+
python -m venv .venv
source .venv/bin/activate

# 依赖
pip install faster-whisper

# 系统依赖
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg

# 可选：使用 MuAPI 托管转录后端时设置
export MUAPI_API_KEY="your-api-key"
```

## 使用方法

### 单集转录

```bash
python scripts/transcribe.py "https://www.xiaoyuzhoufm.com/episode/xxxxx"
```

默认使用本地 `faster-whisper`。如需使用 MuAPI 托管的 `openai-whisper`，设置
`MUAPI_API_KEY`（也支持 `MU_API_KEY`）后运行：

```bash
python scripts/transcribe.py "path/to/audio.m4a" ./output --provider muapi
```

MuAPI 后端会执行上传、提交、轮询和 Markdown 输出的完整流程；返回的媒体地址只接受
HTTPS，API key 不会发送到结果下载地址。音频文件需小于 25 MB；更长或更大的音频请继续使用本地后端。

### 批量转录（RSS）

```bash
python scripts/batch_transcribe.py --rss-url "http://www.ximalaya.com/album/xxxxx.xml" --count 10
```

批量流程也支持 MuAPI 后端：

```bash
python scripts/batch_transcribe.py --rss-url "http://www.ximalaya.com/album/xxxxx.xml" \
  --count 10 --provider muapi
```

## 流程

### Step 1: 下载音频

支持多种来源：
- 小宇宙单集链接（自动从页面提取音频 URL）
- 喜马拉雅链接
- 直接音频 URL（.mp3/.m4a/.wav）
- RSS feed 中的音频链接

**注意**：小宇宙/喜马拉雅等平台会从页面 HTML 中自动解析 `og:audio`、`<audio>` 标签或内嵌 JSON 获取真实音频地址，无需手动提取。

### Step 2: faster-whisper 转录

```python
from faster_whisper import WhisperModel

model = WhisperModel('small', device='cpu', compute_type='int8')
segments, info = model.transcribe(
    audio_path,
    language='zh',
    beam_size=5,
    vad_filter=True,
)
```

### 可选：MuAPI 托管转录

MuAPI 后端通过 `openai-whisper` 提供异步转录，支持 `--language` 指定语言代码，省去本地模型下载和推理环境配置：

```bash
python scripts/transcribe.py "path/to/audio.m4a" ./output \
  --provider muapi --language zh
```

API key 与访问地址见 [MuAPI access keys](https://muapi.ai/access-keys)；能力说明见
[MuAPI speech-to-text API](https://muapi.ai/speech-to-text)。默认本地流程和原有参数保持不变。

### Step 3: 生成 Markdown

自动创建带 frontmatter 的 Markdown 文件。

## 性能数据

| 模型 | 速度 (CPU) | 中文准确率 |
|------|------|------|
| faster-whisper tiny | ~149s/1h | 一般 |
| faster-whisper small | ~10min/h | 良好 (~85-90%) |
| faster-whisper large-v3 | ~30-60min/h | 最佳 |

## 已知限制

- CPU 推理较慢，长播客需要较长时间
- 中文准确率约 85-90%，需要人工校对
- 首次运行会下载模型（small: ~461MB）
- 不支持说话人分离
- MuAPI 后端需要网络连接和 API key，单个上传音频需小于 25 MB
- MuAPI 后端按异步任务轮询，长音频可能需要等待更久并产生 API 用量

## 参考项目

- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Whisper 的 CTranslate2 实现
- [OpenAI Whisper](https://github.com/openai/whisper) - 原始 Whisper 模型

## ⚖️ 合规声明

仅供**个人学习与研究**使用。请遵守目标平台的服务条款（ToS）与 robots 规则，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。下载内容的版权归原作者所有。
