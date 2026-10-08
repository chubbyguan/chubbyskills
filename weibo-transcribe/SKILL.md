---
name: weibo-transcribe
description: >
  微博视频 → 下载 → 转录 → 存为 Markdown。
  支持 weibo.com 和 m.weibo.cn 链接，无需登录。
metadata:
  category: "media"
  triggers: "[\"用户发送微博视频链接\", \"把这个微博视频转成文字\", \"帮我转录这个微博\"]"
  version: "1.0.0"
  tags: "[media, video, transcription, weibo]"
---

# 微博视频转录 Skill

将微博视频下载音频，用 SenseVoice-Small 转录为文字，存为带 frontmatter 的 Markdown 文件。

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
# 桌面端链接
python scripts/transcribe.py "https://weibo.com/xxxxx"

# 移动端链接（更稳定）
python scripts/transcribe.py "https://m.weibo.cn/xxxxx"

# 指定输出目录
python scripts/transcribe.py "https://m.weibo.cn/xxxxx" -o ./output
```

## 流程

### Step 1: yt-dlp 下载音频

微博对桌面端 UA 拦截较严，脚本自动使用移动端 UA + Referer 伪装。优先用 `m.weibo.cn` 链接，成功率更高。

```bash
yt-dlp --extract-audio --audio-format mp3 --audio-quality 128K \
  --user-agent "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) ..." \
  --referer "https://m.weibo.cn/" \
  "https://m.weibo.cn/status/example"
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

脚本自动创建带 frontmatter 的 Markdown 文件，包含来源链接、作者、语言和转录文本。下载失败会自动重试。

## 已知限制

- **链接形态**：桌面端 `weibo.com` 链接常被反爬拦截，优先使用 `m.weibo.cn` 移动端链接
- **反爬**：微博对非移动端 UA 和缺失 Referer 的请求拦截较严；脚本已内置移动端 UA，但频繁请求仍可能触发限流
- **登录态**：私密博文、仅粉丝可见内容需要登录，当前脚本不携带登录态
- **语言**：微博以中文为主，脚本默认 `language=zh`；英文内容建议改用 youtube-transcribe
- **模型大小**：SenseVoice-Small 首次下载约 893MB

## 致谢

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载工具
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型

## ⚖️ 合规声明

仅供**个人学习与研究**使用。请遵守目标平台的服务条款（ToS）与 robots 规则，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。下载内容的版权归原作者所有。
