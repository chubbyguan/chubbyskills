---
name: zhihu-transcribe
description: >
  知乎视频 → 下载 → 转录 → 存为 Markdown。
  支持知乎视频链接、问答内嵌视频和专栏文章，无需登录。
metadata:
  category: "media"
  triggers: "[\"用户发送知乎视频链接\", \"把这个知乎视频转成文字\", \"帮我转录这个知乎\"]"
  version: "1.0.0"
  tags: "[media, video, transcription, zhihu]"
---

# 知乎视频转录 Skill

将知乎视频下载音频，用 SenseVoice-Small 转录为文字，存为带 frontmatter 的 Markdown 文件。

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
# 独立视频页
python scripts/transcribe.py "https://www.zhihu.com/video/1234567890"

# 问答内嵌视频（脚本自动提取视频 ID）
python scripts/transcribe.py "https://www.zhihu.com/question/12345/answer/67890"

# 专栏文章（内嵌视频会被提取）
python scripts/transcribe.py "https://zhuanlan.zhihu.com/p/123456"

# 指定输出目录
python scripts/transcribe.py "https://www.zhihu.com/video/1234567890" -o ./output
```

## 流程

### Step 1: yt-dlp 下载音频

知乎视频页、问答页和专栏文章的链接形态不同，脚本统一交给 yt-dlp 解析。Referer + UA 伪装可规避基础反爬。

```bash
yt-dlp --extract-audio --audio-format mp3 --audio-quality 128K \
  --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ..." \
  --referer "https://www.zhihu.com/" \
  "https://www.zhihu.com/video/1234567890"
```

### Step 2: SenseVoice-Small 转录

```python
from funasr import AutoModel

model = AutoModel(
    model="iic/SenseVoiceSmall",
    trust_remote_code=True,
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 30000},
    device="cpu",
)

result = model.generate(
    input=audio_path,
    language="zh",
    use_itn=True,
    batch_size_s=60,
)
```

### Step 3: 生成 Markdown

脚本自动创建带 frontmatter 的 Markdown 文件，包含来源链接、标题、语言和转录文本。下载失败会自动重试。

## 已知限制

- **内嵌视频**：问答和专栏中的内嵌视频依赖 yt-dlp 正确提取视频 ID；若页面结构变化可能导致提取失败
- **反爬**：知乎对频繁请求有限流；脚本已内置重试，建议单次处理间隔不少于 3 秒
- **登录态**：盐选内容、仅会员可见视频需要登录，当前脚本不携带登录态
- **语言**：知乎以中文为主，脚本默认 `language=zh`；英文内容建议改用 youtube-transcribe
- **模型大小**：SenseVoice-Small 首次下载约 893MB

## 致谢

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型

## ⚖️ 合规声明

仅供**个人学习与研究**使用。请遵守目标平台的服务条款（ToS）与 robots 规则，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。下载内容的版权归原作者所有。
