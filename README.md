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

## 🚦 当前路线

这个仓库已经从「单个 skill 能跑」推进到「个人内容采集管线」：

- **v0.2 reliability**：安装分档、CI、示例输出、统一 frontmatter 校验、失败提示更清晰
- **v0.3 workflow**：把「识别链接 → 调用 skill → 可选加工 → 入库」串成一个命令
- **v0.4 platform depth**：补 B站/YouTube 批量、公众号结构保真、小红书/X 手动 fallback
- **v0.5 core pipeline**：新增 `chubby.yaml`、队列、运行状态、失败重试、每日运行报告、schema v1
- **v0.6 platform health**：新增平台定义、站点模板、状态页生成器、平台失败 issue form
- **v0.7 knowledge vault**：新增 vault 模板、SQLite 本地索引、全文检索、recent/read/stats、MCP 检索增强
- **v0.8 first-run UX**：新增 `quickstart` 首跑验收，离线打通配置、dry-run、schema 校验、平台定义、vault 索引和 MCP 前置检查
- **v0.9 knowledge automation**：新增 semantic-lite 检索、自动归档、知识卡片生成、贡献者平台 scaffold

下一阶段会继续补更完整的真实平台 smoke test、embedding provider 和 MCP 工作流。

---

## 🚀 推荐开始方式

### 1. 跑首轮验收

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/chubby.py quickstart
```

`quickstart` 不会抓真实平台内容，会离线完成配置初始化、X 链接 dry-run、示例 Markdown 校验、平台定义校验、临时 vault 索引和 MCP 前置检查。完整说明见 [docs/quickstart.md](./docs/quickstart.md)。

### 2. 轻量安装（默认推荐）

```bash
bash setup.sh
# 等同于 bash setup.sh light
```

轻量模式可直接使用：公众号文章、X 图文、小红书图文、行业情报雷达、知识库健康检查、content-enrich。只有视频/播客转录才需要装重依赖。

### 3. 按需安装重依赖

```bash
bash setup.sh video     # 抖音/B站/TikTok/微博/知乎/YouTube/小红书视频/X视频
bash setup.sh podcast   # 播客转录
bash setup.sh wechat    # 公众号/PDF 解析增强
bash setup.sh all       # 全部依赖
```

### 4. 个人知识管线（推荐）

```bash
# 初始化 chubby.yaml、队列、状态和报告目录
python3 tools/chubby.py init

# 或直接跑 v0.8 首跑验收
python3 tools/chubby.py quickstart

# 单条采集，会写入 .chubby/runs.jsonl 并生成 runs/YYYY-MM-DD.md
python3 tools/chubby.py ingest "https://x.com/user/status/123" --dry-run

# 把链接逐行放进 inbox/links.txt 后批量执行
python3 tools/chubby.py run

# 查看最近状态 / 重试失败项
python3 tools/chubby.py status --latest
python3 tools/chubby.py retry --all-failed

# 查看平台健康度和模板覆盖
python3 tools/platform_health.py --check
python3 tools/platform_health.py --local --check

# 建立本地知识库索引并检索
python3 tools/vault_index.py index ~/Documents/ObsidianVault
python3 tools/vault_index.py search "AI Agent"
```

### 5. 轻量单条采集

```bash
# 自动识别平台并调用对应 skill
python3 tools/chubby_ingest.py "https://www.bilibili.com/video/BVxxxx" -o output/

# 采集后自动加工摘要/标签（需要 DEEPSEEK_API_KEY）
python3 tools/chubby_ingest.py "https://x.com/user/status/123" -o output/ --enrich

# 采集后复制进 Obsidian vault/inbox
python3 tools/chubby_ingest.py "https://mp.weixin.qq.com/s/xxx" --vault ~/Documents/Obsidian/Inbox
```

### 6. 校验输出格式

```bash
python3 tools/validate_outputs.py examples/outputs
python3 tools/validate_outputs.py examples/outputs --schema-v1
python3 tools/validate_outputs.py output/
```

统一输出协议要求每篇 Markdown 至少带这些 frontmatter 字段：`title`、`type`、`platform`、`source`、`created`。通过 `tools/chubby.py` 进入管线的产物会自动补 `schema_version: 1`、`run_id`、`source_hash`、`captured_at`、`processed_at`、`content_type`、`status`、`assets`。

---

## 🧭 能力矩阵

| 能力 | 平台/范围 | 默认依赖 | 关键限制 |
|---|---|---|---|
| 字幕优先转录 | B站 / YouTube | `yt-dlp` | 有字幕时免模型；无字幕回退视频转录 |
| 视频转录 | 抖音 / B站 / TikTok / 微博 / 知乎 / YouTube / 小红书视频 / X视频 | `ffmpeg` + `funasr` + `torch` | 首次安装重；平台风控会影响下载 |
| 播客转录 | 小宇宙 / 喜马拉雅 / RSS / 本地音频 | `ffmpeg` + `faster-whisper` | 长音频耗时较久 |
| 图文采集 | 小红书 / X / 公众号 | 轻量或零 pip 依赖 | 小红书建议配置 `XHS_COOKIE` |
| 内容加工 | 任意 Markdown | `DEEPSEEK_API_KEY` | LLM 费用和上下文长度由用户环境决定 |
| 知识库管理 | Obsidian vault | 健康检查/SQLite 索引零依赖；MCP 需 `mcp` | MCP 读取本地 vault，需设置 `VAULT_DIR` |
| 个人知识管线 | 自动识别、队列、状态、报告、重试 | 复用对应 skill 依赖 | `tools/chubby.py` 负责编排；无法识别时用 `--skill` 指定 |
| 平台健康度 | 平台定义 / 站点模板 / 状态页 | 零 pip 依赖 | `tools/platform_health.py` 校验结构；`--local` 检查本地依赖 |
| 本地知识库索引 | Markdown vault / Obsidian | SQLite 标准库 | `tools/vault_index.py` 支持 index/search/recent/read/stats |
| 知识库自动化 | semantic-lite / 归档 / 卡片 | SQLite + 标准库 | `tools/vault_curator.py` 默认 dry-run，避免误移动 |
| 贡献者平台适配 | 新平台定义 / 模板 / skill 骨架 | 零 pip 依赖 | `tools/platform_adapter.py new ...` 生成可校验 scaffold |

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
| 🧠 [**knowledge-base-management**](#-knowledge-base-management知识库管理) | 知识库全生命周期管理：三层架构、素材入库、健康检查、本地索引、MCP 检索 |

### 工作流

| 名字 | 一句话 |
|---|---|
| 📡 [**industry-intelligence-radar**](#-industry-intelligence-radar行业情报雷达) | 多源扫描(X/即刻/V2EX/HN) → 关键词过滤 → 趋势检测 → 每日情报简报 |
| 📚 [**learning-notes-automation**](#-learning-notes-automation学习笔记自动化) | 视频/播客转录 → 知识点提取 → 闪卡生成 → 知识图谱更新 |

---

## 📦 安装方式

### 方式 1：分档安装（推荐）

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
bash setup.sh          # 默认 light：轻量能力
bash setup.sh video    # 视频转录重依赖
bash setup.sh podcast  # 播客转录
bash setup.sh wechat   # 公众号/PDF 处理
bash setup.sh all      # 全部依赖
bash setup.sh doctor   # 只做环境体检
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

## 🔁 个人知识管线（v0.5）

`tools/chubby.py` 是推荐入口，负责把单条采集升级成可长期运行的队列管线：

```bash
python3 tools/chubby.py init
python3 tools/chubby.py doctor
python3 tools/chubby.py ingest "<链接>" -o output/
python3 tools/chubby.py run --queue inbox/links.txt
python3 tools/chubby.py status --latest --limit 20
python3 tools/chubby.py retry --all-failed
```

默认配置文件是 `chubby.yaml`，可从 `chubby.example.yaml` 复制，也可以通过 `python3 tools/chubby.py init` 生成：

```yaml
output_dir: output
vault_dir:
state_file: .chubby/runs.jsonl
report_dir: runs
queue_file: inbox/links.txt
enrich: false
timeout_seconds: 1800
```

运行后会产生两类本地状态：

- `.chubby/runs.jsonl`：每条 source 的 `run_id`、平台、状态、错误、输出路径
- `runs/YYYY-MM-DD.md`：当天运行报告，适合给后续 Agent 或自己复盘

`run` 命令会按行读取 `inbox/links.txt`，空行和 `#` 注释会被忽略。单条失败不会中断整批任务，后续可以用 `status --failed` 查看，再用 `retry` 重试。

## 🧭 平台健康度与站点模板（v0.6）

v0.6 把「支持哪些平台、稳定到什么程度、需要哪些依赖、失败时怎么 fallback」变成可检查的声明文件：

- `platforms/*.yaml`：平台 ID、skill 目录、入口脚本、依赖、状态、fallback、样例链接
- `templates/sites/*.yaml`：URL 匹配、frontmatter 字段、资源保存、后处理流程
- `docs/platform-status.md`：由工具生成的平台状态页
- `.github/ISSUE_TEMPLATE/platform_failure.yml`：用户提交平台失败样例的结构化入口

常用命令：

```bash
# 校验平台定义、脚本路径和模板覆盖；CI 默认跑这个
python3 tools/platform_health.py --check
python3 tools/platform_health.py --check-output

# 生成 docs/platform-status.md
python3 tools/platform_health.py

# 额外检查本机命令、Python 包和环境变量是否就绪
python3 tools/platform_health.py --local --check

# 输出机器可读 JSON，方便后续做 dashboard 或 MCP 工具
python3 tools/platform_health.py --json
```

状态页入口：[docs/platform-status.md](./docs/platform-status.md)。

## 🧠 Knowledge Vault（v0.7）

v0.7 把「Markdown 文件」推进成可被人和 Agent 稳定使用的本地知识库：

- `vault-template/`：Obsidian 友好的 Inbox / Sources / Processed / Dashboards / Assets / Templates 结构
- `tools/vault_index.py`：SQLite 本地索引，支持全文搜索、按平台/标签过滤、最近笔记、读取笔记、统计
- `knowledge-base-management/scripts/mcp_server.py`：MCP server 复用同一套索引，支持 search/read/recent/reindex/stats

常用命令：

```bash
# 建索引，默认写入 .chubby/vault_index.sqlite
python3 tools/vault_index.py index ~/Documents/ObsidianVault

# 搜索，可按平台或标签过滤
python3 tools/vault_index.py search "AI Agent"
python3 tools/vault_index.py semantic "内容策略"
python3 tools/vault_index.py search "品牌" --platform wechat
python3 tools/vault_index.py search "选题" --tag 内容

# 最近笔记 / 读取笔记 / 统计
python3 tools/vault_index.py recent --limit 10
python3 tools/vault_index.py read "10_Sources/x/example.md" --vault ~/Documents/ObsidianVault
python3 tools/vault_index.py stats
```

自动归档和知识卡片：

```bash
python3 tools/vault_curator.py archive ~/Documents/ObsidianVault
python3 tools/vault_curator.py archive ~/Documents/ObsidianVault --apply
python3 tools/vault_curator.py card ~/Documents/ObsidianVault "10_Sources/x/example.md" --apply
```

详情见 [docs/knowledge-automation.md](./docs/knowledge-automation.md)。

MCP 使用：

```bash
pip install mcp
VAULT_DIR=~/Documents/ObsidianVault python3 knowledge-base-management/scripts/mcp_server.py
```

MCP 暴露工具：`search_vault`、`semantic_search_vault`、`read_kb_note`、`list_recent_notes`、`reindex_vault`、`vault_index_stats`。

## 🧩 贡献者平台适配（v0.9）

新增平台先用 scaffold 生成骨架：

```bash
python3 tools/platform_adapter.py new hacker-news \
  --name "Hacker News" \
  --sample-source "https://news.ycombinator.com/item?id=123" \
  --match "news.ycombinator.com"
python3 tools/platform_health.py --check
```

详情见 [docs/contributor-platform-adapter.md](./docs/contributor-platform-adapter.md)。

## 🔁 轻量一键工作流（v0.3）

`tools/chubby_ingest.py` 会自动识别输入链接并调用对应 skill：

| 输入 | 自动调用 |
|---|---|
| `BV...` / `bilibili.com` | `bilibili-transcribe` |
| `youtube.com` / `youtu.be` | `youtube-transcribe` |
| `douyin.com` | `douyin-transcribe` |
| `x.com/.../status/...` / `twitter.com` | `x-ingest` |
| `xiaohongshu.com` / `xhslink.com` | `xiaohongshu-ingest` |
| `mp.weixin.qq.com` | `wechat-article-ingest` |
| 本地音频文件 | `podcast-transcribe` |

常用参数：

```bash
python3 tools/chubby_ingest.py "<链接>" -o output/
python3 tools/chubby_ingest.py "<链接>" -o output/ --enrich
python3 tools/chubby_ingest.py "<链接>" --vault ~/Documents/Obsidian/Inbox
python3 tools/chubby_ingest.py "<链接>" --skill youtube --no-translate
```

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
支持字幕优先和 URL 列表批量处理：

```bash
python3 bilibili-transcribe/scripts/batch_transcribe.py examples/bilibili-urls.txt -o output/bilibili
```

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
支持字幕优先和 URL 列表批量处理：

```bash
python3 youtube-transcribe/scripts/batch_transcribe.py examples/youtube-urls.txt -o output/youtube --no-translate
```

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
链接抓取会尽量保留标题层级、图片和正文链接；PDF fallback 会统一补 `platform: wechat`。

**致谢**：[microsoft/markitdown](https://github.com/microsoft/markitdown) · [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) · [dontbesilent](https://github.com/dontbesilent)

→ [SKILL.md](./wechat-article-ingest/SKILL.md) · [脚本](./wechat-article-ingest/scripts/)

---

### 📕 xiaohongshu-ingest（小红书采集）

> *"采集爆款笔记，顺手拆出能直接写的选题。"*

小红书笔记 → 统一 frontmatter Markdown（标题/正文/标签/作者/赞藏评）→ DeepSeek 爆款拆解（人群×场景×痛点×情绪×钩子）→ 5 条衍生选题。**自动区分图文/视频**：图文下载图片本地嵌入，视频提取直链转成文字稿（同抖音）。支持 xhslink 短链；建议配 `XHS_COOKIE` 规避风控。
如果被风控或页面结构变化，可以用 `--fallback-text 手动正文.txt` 继续生成标准 Markdown。

**致谢**：[DeepSeek](https://platform.deepseek.com/) · 小红书爆款方法论

→ [SKILL.md](./xiaohongshu-ingest/SKILL.md) · [脚本](./xiaohongshu-ingest/scripts/)

---

### 🐦 x-ingest（X/Twitter 采集）

> *"一条推文，图存下来、视频转成字。"*

X 推文 → 统一 frontmatter Markdown（正文/作者/赞回复/话题）。**自动区分图文/视频**：图文下载图片本地嵌入，视频提取最高码率 mp4 直链转成文字稿。走 X 官方嵌入端点，**免登录、免 API Key**；目前支持单条推文。
如果 syndication 端点临时不可用，可以用 `--fallback-text 手动正文.txt` 继续生成标准 Markdown。

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

Obsidian 知识库全生命周期管理：三层架构（素材库/Wiki/产出）、素材 ABC 分级入库、健康检查与清理、SQLite 本地索引、MCP 检索、目录整理与归档。**附带 MCP Server**（`mcp_server.py`）——把知识库检索暴露给任何 MCP Agent，「采集写入 + 索引 + MCP 查询」闭环。

**核心能力**：
- 📥 素材入库：ABC 分级 + 公众号/群聊自动同步
- 🔍 健康检查：断链修复、frontmatter 补全、去重归档
- 🧠 本地索引：SQLite search / recent / read / stats，MCP 复用同一套索引
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

通过 `tools/chubby.py` 管线处理后的 Markdown 会升级到 schema v1，并补充这些机器字段：

| 字段 | 含义 | 示例 |
|------|------|------|
| `schema_version` | 管线 schema 版本 | `1` |
| `run_id` | 本次采集运行 ID | `20260630T160000-ab12cd34` |
| `source_hash` | 原始 source 的短 hash，用于去重/重试 | `0123456789abcdef` |
| `captured_at` | 开始采集时间 | `2026-06-30T16:00:00+08:00` |
| `processed_at` | 处理完成时间 | `2026-06-30T16:00:03+08:00` |
| `content_type` | 内容类型 | `video` / `audio` / `article` / `social` / `note` |
| `status` | 管线状态 | `success` / `failed` / `dry_run` |
| `assets` | 关联资源目录列表 | `[xiaohongshu-sample.assets]` |

校验 schema v1：

```bash
python3 tools/validate_outputs.py output/ --schema-v1
```

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
