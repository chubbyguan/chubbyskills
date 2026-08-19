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
version: 1.0.0
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
```

默认继续使用本地 `faster-whisper`。如果不想安装本地模型，也可以选择 Atlas Cloud 远程转录：

```bash
export ATLASCLOUD_API_KEY="your-api-key"
python scripts/transcribe.py "path/to/audio.m4a" --provider atlas
```

远程模式使用 `bytedance/seed-asr-2.0` 的固定请求 schema；提交请求只发送
一次，随后仅轮询 prediction 状态。

## 使用方法

### 单集转录

```bash
python scripts/transcribe.py "https://www.xiaoyuzhoufm.com/episode/xxxxx"
python scripts/transcribe.py "path/to/audio.m4a" --provider atlas
```

### 批量转录（RSS）

```bash
python scripts/batch_transcribe.py --rss-url "http://www.ximalaya.com/album/xxxxx.xml" --count 10
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

默认在本地使用 `faster-whisper`：

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

使用 `--provider atlas` 时，脚本会把不受 API 直接支持的容器先转成 MP3，
再通过 Atlas Cloud `generateAudio` 接口提交一次任务，并有界轮询结果。Atlas
Cloud 是可选路径，不改变本地默认行为。

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
- Atlas Cloud 模式需要 API key，远程转录可能产生费用

## 参考项目

- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Whisper 的 CTranslate2 实现
- [OpenAI Whisper](https://github.com/openai/whisper) - 原始 Whisper 模型

## ⚖️ 合规声明

仅供**个人学习与研究**使用。请遵守目标平台的服务条款（ToS）与 robots 规则，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。下载内容的版权归原作者所有。
