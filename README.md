<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

#### 信息流会忘，知识库会记 —— 把全渠道好内容采集进你的第二大脑

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-14-10B981?style=for-the-badge)](#-skills)
[![Stars](https://img.shields.io/github/stars/chubbyguan/chubbyskills?style=for-the-badge&color=F59E0B)](https://github.com/chubbyguan/chubbyskills/stargazers)
[![Hype 周榜](https://img.shields.io/badge/🔥_Hype_ML%2FAI_周榜-已上榜-FF6B35?style=for-the-badge)](https://github.com/chubbyguan/chubbyskills)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-8B5CF6?style=flat-square)
![Hermes](https://img.shields.io/badge/Hermes-Skill-EC4899?style=flat-square)

</div>

**我是 Chubby**，Ai+电商的探索者

平时做内容、搭个人知识库，也写一些 AI Agent / Skill 的实践。我习惯把每天刷到的好东西——视频、播客、公众号、小红书、推特——自动收进自己的知识库，让信息真正沉淀下来，而不是看完就忘。这个仓库里的工具，就是这套工作流里我自己每天在用的那几件。

同好的话，欢迎来唠：

- 🐦 [X / Twitter](https://x.com/Chubbyguan)
- 💬 [即刻](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5)
- 📕 [小红书](https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8)
- 📰 微信公众号：**关关不过**

---

都是在自己项目里跑通了一段时间，确实省事，才搬出来开源的。没什么花活，就是几个挺实用的东西。

这里的每个 Skill 都是 Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex、OpenCode、OpenClaw、Hermes 都能装。

## ✨ 能帮你做什么

- 📥 **全渠道采集** —— 抖音 / B站 / 小红书 / 公众号 / X / 播客 / YouTube，把链接丢进来就行
- 🎬 **图文 / 视频自动分流** —— 图文笔记存图、视频笔记转成文字稿，不用你操心
- ⚡ **字幕优先，免 GPU** —— YouTube / B站 有字幕时秒出文字，不必先装一堆模型
- 🧠 **沉淀进知识库** —— 统一格式入 Obsidian，还带一个 MCP server，让任何 Agent 都能查你的库
- 🧩 **每个 skill 独立可装** —— 只装你需要的那一个，纯图文 / 文字采集零依赖

> 一句话：**把中文全渠道的内容，变成你自己的、可检索的第二大脑。**

---

## 📋 目录

### 视频转录

| 名字 | 平台 | 一句话 |
|---|---|---|
| 🎬 [**douyin-transcribe**](#-douyin-transcribe抖音转录) | 抖音 | 抖音视频 → 转录 → Markdown |
| 📺 [**bilibili-transcribe**](#-bilibili-transcribeb-站转录) | B站 | B站视频 → 转录 → Markdown |
| 🎵 [**tiktok-transcribe**](#-tiktok-transcribetiktok-转录) | TikTok | TikTok 视频 → 转录 → Markdown |
| 📱 [**weibo-transcribe**](#-weibo-transcribe微博视频转录) | 微博 | 微博视频 → 转录 → Markdown |
| 💡 [**zhihu-transcribe**](#-zhihu-transcribe知乎视频转录) | 知乎 | 知乎视频 → 转录 → Markdown |
| 🌍 [**youtube-transcribe**](#-youtube-transcribeyoutube-转录翻译) | YouTube | YouTube → 转录 → 英文翻译 → 中英对照 |

### 播客转录

| 名字 | 平台 | 一句话 |
|---|---|---|
| 🎙️ [**podcast-transcribe**](#-podcast-transcribe播客转录) | 小宇宙/喜马拉雅 | 播客 → 下载 → 转录 → Markdown |

### 内容处理

| 名字 | 平台 | 一句话 |
|---|---|---|
| 📰 [**wechat-article-ingest**](#-wechat-article-ingest公众号处理) | 微信公众号 | 公众号链接 → Markdown + A层观点提取 + B层问题链 |
| 📕 [**xiaohongshu-ingest**](#-xiaohongshu-ingest小红书采集) | 小红书 | 图文存图/视频转文字稿 + 爆款拆解 + 衍生选题 |
| 🐦 [**x-ingest**](#-x-ingestxtwitter采集) | X / Twitter | 推文采集 → 图文存图 / 视频转文字稿（免登录）|

### 内容加工

| 名字 | 一句话 |
|---|---|
| ✨ [**content-enrich**](#-content-enrich内容加工) | 给任意采集产物自动补「摘要 + 要点 + 标签 + 价值判断」，惠及全部采集 skill |

### 知识库管理

| 名字 | 一句话 |
|---|---|
| 🧠 [**knowledge-base-management**](#-knowledge-base-management知识库管理) | 知识库全生命周期管理：三层架构、素材入库、健康检查、三件套集成 |

### 工作流

| 名字 | 一句话 |
|---|---|
| 📡 [**industry-intelligence-radar**](#-industry-intelligence-radar行业情报雷达) | 多源扫描(X/即刻/V2EX/HN) → 关键词过滤 → 趋势检测 → 每日情报简报 |
| 📚 [**learning-notes-automation**](#-learning-notes-automation学习笔记自动化) | 视频/播客转录 → 知识点提取 → 闪卡生成 → 知识图谱更新 |

---

## 📦 安装方式

### 方式 1：一键安装（推荐）

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
bash setup.sh          # 安装全部依赖
bash setup.sh podcast   # 只装指定 skill
```

### 方式 2：手动安装

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
pip install -r requirements.txt            # 全部
pip install -r podcast-transcribe/requirements.txt   # 单个 skill
```

### 方式 3：Agent 安装

在 Claude Code、Codex、OpenClaw、Hermes 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/chubbyguan/chubbyskills/tree/main/<skill-name>
```

> Gitee 镜像：https://gitee.com/chubbyguan/chubbyskills

---

## ✨ Skills

<a id="-skills"></a>

### 🎬 douyin-transcribe（抖音转录）

> *"想把抖音视频转成文字，以前得折腾半天 cookie 和 yt-dlp，现在一句话搞定。"*

抖音视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。

**致谢**：[vangie/douyin-transcriber](https://github.com/vangie/douyin-transcriber) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./douyin-transcribe/SKILL.md) · [脚本](./douyin-transcribe/scripts/)

---

### 📺 bilibili-transcribe（B 站转录）

> *"B 站那么多干货视频，终于可以转成文字慢慢看了。"*

B 站视频 → yt-dlp 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./bilibili-transcribe/SKILL.md) · [脚本](./bilibili-transcribe/scripts/)

---

### 🎵 tiktok-transcribe（TikTok 转录）

> *"TikTok 上的好内容，也能存下来慢慢看了。"*

TikTok 视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。支持 vm.tiktok.com 短链接。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./tiktok-transcribe/SKILL.md) · [脚本](./tiktok-transcribe/scripts/)

---

### 📱 weibo-transcribe（微博视频转录）

> *"微博上的视频内容，终于能转成文字了。"*

微博视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。支持 weibo.com 和 m.weibo.cn。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./weibo-transcribe/SKILL.md) · [脚本](./weibo-transcribe/scripts/)

---

### 💡 zhihu-transcribe（知乎视频转录）

> *"知乎上的视频回答，也能转成文字收藏了。"*

知乎视频 → 下载音频 → SenseVoice-Small 转录 → 存为 Markdown。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)

→ [SKILL.md](./zhihu-transcribe/SKILL.md) · [脚本](./zhihu-transcribe/scripts/)

---

### 🌍 youtube-transcribe（YouTube 转录+翻译）

> *"英文 YouTube 终于能轻松看懂了。"*

YouTube 视频 → yt-dlp 下载 → SenseVoice-Small 转录 → 英文自动翻译成中文 → 输出中英对照 Markdown。

**致谢**：[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) · [DeepSeek](https://platform.deepseek.com/)

→ [SKILL.md](./youtube-transcribe/SKILL.md) · [脚本](./youtube-transcribe/scripts/)

---

### 🎙️ podcast-transcribe（播客转录）

> *"播客听不完？让它变成文字，想看就看。"*

播客音频 → 下载 → faster-whisper 转录 → 存为 Markdown。支持小宇宙、喜马拉雅，支持 RSS 批量下载。

**致谢**：[SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) · [OpenAI Whisper](https://github.com/openai/whisper)

→ [SKILL.md](./podcast-transcribe/SKILL.md) · [脚本](./podcast-transcribe/scripts/)

---

### 📰 wechat-article-ingest（公众号处理）

> *"公众号文章直接变成结构化知识。"*

微信公众号文章 → Markdown 提取 → A层观点提取 + B层问题链生成。支持直接链接抓取。

**致谢**：[microsoft/markitdown](https://github.com/microsoft/markitdown) · [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) · [dontbesilent](https://github.com/dontbesilent)

→ [SKILL.md](./wechat-article-ingest/SKILL.md) · [脚本](./wechat-article-ingest/scripts/)

---

### 📕 xiaohongshu-ingest（小红书采集）

> *"采集爆款笔记，顺手拆出能直接写的选题。"*

小红书笔记 → 统一 frontmatter Markdown（标题/正文/标签/作者/赞藏评）→ DeepSeek 爆款拆解（人群×场景×痛点×情绪×钩子）→ 5 条衍生选题。**自动区分图文/视频**：图文下载图片本地嵌入，视频提取直链转成文字稿（同抖音）。支持 xhslink 短链；建议配 `XHS_COOKIE` 规避风控。

**致谢**：[DeepSeek](https://platform.deepseek.com/) · 小红书爆款方法论

→ [SKILL.md](./xiaohongshu-ingest/SKILL.md) · [脚本](./xiaohongshu-ingest/scripts/)

---

### 🐦 x-ingest（X/Twitter 采集）

> *"一条推文，图存下来、视频转成字。"*

X 推文 → 统一 frontmatter Markdown（正文/作者/赞回复/话题）。**自动区分图文/视频**：图文下载图片本地嵌入，视频提取最高码率 mp4 直链转成文字稿。走 X 官方嵌入端点，**免登录、免 API Key**；目前支持单条推文。

**致谢**：[FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) · X 官方嵌入端点

→ [SKILL.md](./x-ingest/SKILL.md) · [脚本](./x-ingest/scripts/)

---

### ✨ content-enrich（内容加工）

> *"采集进来的原始文本，一键变成带摘要、要点、标签的可用知识。"*

给**任意采集产物**（转录稿 / 文章 / 笔记）自动补元信息：用 DeepSeek 提炼一句话总结、3-5 条要点、领域、标签、「值得深读？」判断，写进 frontmatter 并在正文顶部插入 `## 📝 摘要` 区块，原内容完整保留。支持单篇就地增强、整目录批量；幂等可重做。是连接「采集」与「知识库」的加工层通用能力。

**致谢**：[DeepSeek](https://platform.deepseek.com/)

→ [SKILL.md](./content-enrich/SKILL.md) · [脚本](./content-enrich/scripts/)

---

### 🧠 knowledge-base-management（知识库管理）

> *"知识库从素材入库到健康检查，一套流程全搞定。"*

Obsidian 知识库全生命周期管理：三层架构（素材库/Wiki/产出）、素材 ABC 分级入库、健康检查与清理、GBrain/GraphRAG/LLM Wiki 三件套集成、目录整理与归档。**附带 MCP Server**（`mcp_server.py`）——把知识库检索暴露给任何 MCP Agent，「采集写入 + MCP 查询」闭环。

**核心能力**：
- 📥 素材入库：ABC 分级 + 公众号/群聊自动同步
- 🔍 健康检查：断链修复、frontmatter 补全、去重归档
- 🛠️ 工具集成：GBrain 搜索 + GraphRAG 发现 + LLM Wiki 写作
- 📂 目录整理：全库审计、批量归档、文件命名规范

**致谢**：[Obsidian](https://obsidian.md/) · [GBrain](https://github.com/) · [GraphRAG](https://github.com/microsoft/graphrag)

→ [SKILL.md](./knowledge-base-management/SKILL.md) · [脚本](./knowledge-base-management/scripts/)

---

### 📡 industry-intelligence-radar（行业情报雷达）

> *"早知道 = 早行动 = 早收益"*

多源情报扫描系统：X/Twitter + 即刻 + V2EX + Hacker News + 36kr → 关键词过滤 → 趋势检测 → 每日情报简报。

**核心能力**：
- 🔍 多源并行扫描：X、即刻、V2EX、HN、36kr
- 🏷️ 智能过滤：去重、时效、信号强度分级
- 📈 趋势检测：突发/持续/新兴趋势识别
- 📋 情报简报：高信号事件 + 趋势观察 + 机会洞察

**覆盖领域**：AI/Agent、半导体、航天、新能源、游戏、跨境电商、创业/投资

→ [SKILL.md](./industry-intelligence-radar/SKILL.md) · [脚本](./industry-intelligence-radar/scripts/)

---

### 📚 learning-notes-automation（学习笔记自动化）

> *"看视频 ≠ 学会，生成闪卡 = 记住"*

学习内容自动化处理：视频/播客转录 → 知识点提取 → 闪卡生成 → 知识图谱更新。

**核心能力**：
- 🎬 多源输入：YouTube、B站、播客、抖音、公众号
- 📝 知识点提取：概念、事实、方法论、金句
- 🃏 闪卡生成：概念卡、问答卡、对比卡、步骤卡（Anki 兼容）
- 🕸️ 知识图谱：实体提取 + 关系映射 + 自动入库

**输出格式**：
- Anki 闪卡文件（可直接导入）
- 学习笔记 Markdown
- 知识库条目

→ [SKILL.md](./learning-notes-automation/SKILL.md) · [脚本](./learning-notes-automation/scripts/)

---

## 🔧 环境要求

> 💡 不确定要装什么？先跑 `python3 tools/check_env.py` 体检——它会告诉你缺哪些依赖、以及哪些功能**零依赖**就能用（轻量模式）。

### 一键安装

```bash
bash setup.sh          # 全部依赖
bash setup.sh podcast  # 只装指定 skill
```

或手动安装每个 skill 目录下的 `requirements.txt`。

### 视频转录（抖音/B站/TikTok/微博/知乎/YouTube）

```bash
pip install -r douyin-transcribe/requirements.txt
# 系统依赖
brew install ffmpeg yt-dlp  # macOS
# Ubuntu: sudo apt install ffmpeg && pip install yt-dlp

# YouTube 翻译功能（可选）
export DEEPSEEK_API_KEY=your-key
```

### 播客转录

```bash
pip install -r podcast-transcribe/requirements.txt
brew install ffmpeg  # macOS
```

### 公众号处理

```bash
pip install -r wechat-article-ingest/requirements.txt
```

### 小红书采集

```bash
# 采集与拆解均零 pip 依赖（仅标准库）
export XHS_COOKIE="你的小红书 cookie"   # 可选，提高采集成功率
export DEEPSEEK_API_KEY="your-key"       # 爆款拆解必需
```

### X/Twitter 采集

```bash
# 图文/文字采集零依赖、免登录；视频转录才需要 funasr + ffmpeg
pip install funasr modelscope torch torchaudio   # 仅视频推文需要
```

### 内容加工

```bash
# 零 pip 依赖（仅标准库）
export DEEPSEEK_API_KEY="your-key"   # 用于提炼摘要/要点/标签
```

### 知识库管理

```bash
# 健康检查脚本 vault_health_check.py 零依赖，纯标准库，无需安装

# 以下为可选的第三方工具（不随本仓库提供）：
# GBrain（知识库搜索）— pip install gbrain
# GraphRAG（知识图谱发现）— 独立项目，见 SKILL.md
# LLM Wiki — 集成到 Obsidian vault
```

### 行业情报雷达

```bash
# scan.py 零依赖，纯标准库（HN + V2EX + RSS），无需安装、无需 API Key
# X/即刻信号由 Agent 联网搜索补充（可选）
```

### 学习笔记自动化

```bash
# make_notes.py 需要 DeepSeek API Key 做知识点提取 + 闪卡生成
export DEEPSEEK_API_KEY=your-key
# 转录环节复用本仓库的 *-transcribe skill（见上方「视频转录」依赖）
```

---

## 📐 统一 frontmatter 约定

所有采集类 skill 产出的 Markdown 使用统一的 frontmatter，便于知识库按来源/平台聚合与检索：

| 字段 | 含义 | 示例 |
|------|------|------|
| `title` | 标题 | 某视频标题 |
| `type` | 类型 | `note` |
| `platform` | 机器可读来源（聚合用） | `bilibili` / `youtube` / `douyin` / `tiktok` / `weibo` / `zhihu` / `podcast` / `wechat` / `xiaohongshu` |
| `source` | 原始链接（本地文件则为路径） | `https://...` |
| `author` | 作者 / UP主 / 公众号（可空） | 某某 |
| `created` | 入库日期 | `2026-06-14` |
| `tags` | 中文平台标签 | `[B站]` |
| `transcriber` | 转录引擎（仅转录类） | `字幕` / `SenseVoice-Small` / `faster-whisper-small` |

视频/音频类还可能带 `language`、`translated` 字段。`platform` 字段是机器可读的，建议在 Obsidian/Dataview 里用它做按平台聚合的视图。

---

## ⚖️ 合规与免责

本仓库所有采集类 skill（视频 / 播客 / 公众号 / 小红书 / X 等）**仅供个人学习与研究使用**：

- 请遵守各目标平台的服务条款（ToS）、`robots.txt` 与相关法律法规
- 控制请求频率，**不要用于批量抓取、商用爬取、二次分发或任何侵犯他人权益的场景**
- 抓取 / 转录所得内容的**版权归原作者所有**；引用、转载请获得授权并注明出处
- 涉及登录态（如 cookie）时，仅在你自己的账号、自己授权的范围内使用
- 本项目按「现状」（AS IS）提供，作者不对使用本工具产生的任何后果负责

如平台方或权利人认为某 skill 不当，欢迎提 issue，我会及时处理。

---

## 🙏 致谢

### 仓库结构灵感

- [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills) — 仓库结构和 README 风格参考

### 语音识别

- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 阿里开源的中文语音识别模型
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper 的 CTranslate2 实现
- [OpenAI Whisper](https://github.com/openai/whisper) — 开创性的语音识别模型

### 视频下载

- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — 强大的视频下载工具，支持上千个平台
- [vangie/douyin-transcriber](https://github.com/vangie/douyin-transcriber) — 抖音下载方案灵感

### 文档处理

- [microsoft/markitdown](https://github.com/microsoft/markitdown) — 文档转 Markdown 工具
- [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) — PDF 处理库

### 知识库管理

- [Obsidian](https://obsidian.md/) — 知识库载体
- [GBrain](https://github.com/) — 知识库搜索工具
- [GraphRAG](https://github.com/microsoft/graphrag) — 知识图谱发现
- [Karpathy LLM Wiki](https://github.com/karpathy/llm-wiki) — LLM Wiki 写作模式

### AI Agent & 翻译

- [Agent Skills](https://agentskills.io) — Agent Skill 开放标准
- [DeepSeek](https://platform.deepseek.com/) — 翻译用 LLM
- [dontbesilent](https://github.com/dontbesilent) — A+B 双轨处理方法论
- [Hermes Agent](https://github.com/nousresearch/hermes-agent) — 这些 skill 的运行环境

感谢所有开源贡献者！🙏

---

## 🌟 关于

这些 skill 都是我自己每天在用的，开源出来如果对你有帮助，给个 ⭐ 就行。

- 🐦 [X / Twitter](https://x.com/Chubbyguan)
- 💬 [即刻](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5)
- 📕 [小红书](https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8)
- 📰 微信公众号：**关关不过**

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@chubbyguan](https://github.com/chubbyguan)

</div>
