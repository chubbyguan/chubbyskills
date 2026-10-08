---
name: tiktok-transcribe
description: >
  TikTok 视频 → 下载 → 转录 → 存为 Markdown。
  支持 vm.tiktok.com / vt.tiktok.com 短链和完整链接，无需登录。
metadata:
  category: "media"
  triggers: "[\"用户发送 TikTok 视频链接\", \"把这个 TikTok 转成文字\", \"帮我转录这个 TikTok\"]"
  version: "1.0.0"
  tags: "[media, video, transcription, tiktok]"
---

# TikTok 视频转录 Skill

将 TikTok 视频下载音频，用 SenseVoice-Small 转录为文字，存为带 frontmatter 的 Markdown 文件。内容中英混杂时自动检测语言。

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
# 完整链接
python scripts/transcribe.py "https://www.tiktok.com/@user/video/1234567890"

# 短链（自动跟随跳转）
python scripts/transcribe.py "https://vm.tiktok.com/xxxxx"
python scripts/transcribe.py "https://vt.tiktok.com/xxxxx"

# 指定输出目录
python scripts/transcribe.py "https://vm.tiktok.com/xxxxx" -o ./output
```

## 流程

### Step 1: yt-dlp 下载音频

TikTok 有地区限制，脚本默认加 `--geo-bypass`。短链由 yt-dlp 自动跟随跳转，无需手动处理。

```bash
yt-dlp --extract-audio --audio-format mp3 --audio-quality 128K \
  --geo-bypass \
  "https://vm.tiktok.com/xxxxx"
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
    language="auto",   # TikTok 中英混杂，自动检测
    use_itn=True,
    batch_size_s=60,
)
```

### Step 3: 生成 Markdown

脚本自动创建带 frontmatter 的 Markdown 文件，包含来源链接、作者、语言和转录文本。

## 已知限制

- **地区限制**：部分地区或网络环境下 TikTok 内容可能无法访问，`--geo-bypass` 可缓解但不保证解决
- **反爬**：频繁请求可能触发限流；脚本内置重试，仍建议控制频率
- **语言混合**：`language=auto` 对中英混杂内容可用，但长英文段落质量不如专用英文模型
- **登录态**：私密账号内容需要登录，当前脚本不携带登录态
- **模型大小**：SenseVoice-Small 首次下载约 893MB

## 致谢

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型

## ⚖️ 合规声明

仅供**个人学习与研究**使用。请遵守目标平台的服务条款（ToS）与 robots 规则，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。下载内容的版权归原作者所有。
