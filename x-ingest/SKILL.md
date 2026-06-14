---
name: x-ingest
description: >
  X(Twitter) 推文采集 → 统一 frontmatter Markdown。自动区分图文与视频：
  图文下载图片本地嵌入，视频提取直链转成文字稿。无需登录（走官方嵌入端点）。
category: content
triggers:
  - 用户发送 X / Twitter 推文链接
  - "采集这条推文"
  - "把这条 X 转成 Markdown"
  - "这条推特视频转文字"
version: 1.0.0
tags: [content, x, twitter, ingest, transcription]
---

# X(Twitter) 推文采集 Skill

把 X 推文抓成结构化 Markdown 入库。**自动区分图文与视频笔记**：图文 → 下载图片本地嵌入；
视频 → 像抖音那样转成文字稿。通过 X 官方嵌入用的 syndication 端点采集，**无需登录、无需 API Key**。

## 环境要求

```bash
# 图文采集零依赖（仅 Python 标准库）

# 视频推文转录需要（与抖音/B站/小红书同一套依赖）：
pip install funasr modelscope torch torchaudio
# macOS: brew install ffmpeg   |   Ubuntu: sudo apt install ffmpeg
```

## 使用方法

```bash
# 采集推文 → 统一 frontmatter Markdown
python scripts/fetch_tweet.py "https://x.com/user/status/1234567890" -o ./out
python scripts/fetch_tweet.py "https://twitter.com/user/status/1234567890" -o ./out

python scripts/fetch_tweet.py "链接" -o ./out --no-images   # 图文：只留图片链接不下载
python scripts/fetch_tweet.py "链接" -o ./out --no-video    # 视频：不转录，只留视频链接
```

## 产出

`fetch_tweet.py` → 统一 frontmatter Markdown（`platform: x`，含 `note_type: image|video|text|article`），含作者(`name @handle`)、互动数据（赞/回复）、话题标签。**按内容类型分流**：

- **图文 / 纯文字推文**：正文 + 图片下载到本地 `<标题>.assets/` 并以 `![]()` 嵌入；`--no-images` 只留链接，单张失败自动回退为链接
- **视频推文**：提取最高码率 mp4 直链 → ffmpeg 抽音频 → SenseVoice 转录（`language=auto`，X 中英混杂）写入 `## 视频文字稿`；`--no-video` 只留视频链接；缺 funasr/ffmpeg 时自动降级为存链接
- **X 长文章（Article）**：取文章标题、预览正文、封面图（封面本地化嵌入）。⚠️ syndication 不返回长文章全文，全文需登录另抓——Markdown 会标注「预览，全文见原文链接」

## ⚠️ 关于可用性

采集走 `cdn.syndication.twimg.com/tweet-result`——X 官方嵌入推文用的公开端点，**无需登录**，但它是非官方契约：

- 受保护账号、已删除、成人/受限内容可能取不到
- 端点或 token 算法（`fetch_tweet.py` 里的 `make_token`）若被 X 调整，需相应更新
- 目前仅支持**单条推文**；thread（连串推文）是未来增强方向

## 合规声明

仅供**个人学习与研究**使用。请遵守 X 服务条款，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。

## 衔接工作流

- 采集产物 → `knowledge-base-management` 入库（统一 frontmatter，按 `platform` 聚合）
- 海外信息源 → 配合 `industry-intelligence-radar` 的 X 信号扫描，沉淀情报
- 视频文字稿 → `learning-notes-automation` 提取知识点 + 闪卡

## 参考

- X 官方嵌入（syndication）端点
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 语音识别模型
