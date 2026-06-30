<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

#### 信息流会忘，知识库会记 —— 把全渠道好内容采集进你的第二大脑

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Version](https://img.shields.io/badge/Version-0.10.0-10B981?style=for-the-badge)](./CHANGELOG.md)
[![Skills](https://img.shields.io/badge/Skills-14-10B981?style=for-the-badge)](#skill-目录)
[![Stars](https://img.shields.io/github/stars/chubbyguan/chubbyskills?style=for-the-badge&color=F59E0B)](https://github.com/chubbyguan/chubbyskills/stargazers)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-8B5CF6?style=flat-square)
![Hermes](https://img.shields.io/badge/Hermes-Skill-EC4899?style=flat-square)

</div>

## 这是什么

Chubby Skills 是一套面向个人知识库和 AI Agent 的内容采集、整理、检索工具。

你可以把它理解成三层：

1. **采集层**：把 B站、YouTube、抖音、小红书、公众号、X、播客等内容转成统一 Markdown。
2. **知识层**：把 Markdown 入库到 Obsidian / 本地 vault，支持索引、搜索、语义检索、归档和知识卡片。
3. **Agent 层**：通过 Agent Skills 和 MCP server，让 Claude Code、Codex、OpenCode、OpenClaw、Hermes 等 Agent 真正读取你的知识库完成任务。

一句话：**把你每天刷到、听到、读到的好内容，变成可复用、可检索、可被 Agent 调用的个人知识资产。**

## 适合谁

- 内容创作者：把爆款笔记、视频、播客、公众号文章沉淀成选题库。
- 学习者：把视频和播客转成文字，再生成笔记、闪卡和知识点。
- 研究者：搭一个能被 Agent 检索的本地资料库。
- Agent 用户：把 skill、CLI、MCP 和 vault 串成可复用工作流。
- 开源贡献者：按统一平台定义和输出协议扩展更多内容源。

## 现在有什么

当前版本：`0.10.0`

| 模块 | 能力 | 入口 |
|---|---|---|
| 平台采集 | 视频、图文、公众号、播客、X、小红书等内容转 Markdown | `tools/chubby_ingest.py` / 各 skill 脚本 |
| 管线编排 | 队列、状态、重试、日报、schema v1 元数据 | `tools/chubby.py` |
| 内容加工 | 摘要、要点、标签、价值判断 | `content-enrich` |
| 知识库 | vault 模板、SQLite 索引、全文搜索、语义检索、最近笔记、统计 | `tools/vault_index.py` |
| 知识自动化 | 自动归档、知识卡片生成 | `tools/vault_curator.py` |
| MCP | Agent 搜索、读取、重建索引、查看统计 | `knowledge-base-management/scripts/mcp_server.py` |
| 质量保障 | 平台健康度、smoke matrix、golden outputs、schema 校验 | `tools/platform_health.py` / `tools/platform_smoke.py` / `tools/golden_outputs.py` |
| 贡献者适配 | 新平台 definition / template / skill scaffold | `tools/platform_adapter.py` |

## 60 秒开始

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/chubby.py quickstart
```

`quickstart` 是离线首跑验收，不会抓真实平台内容。它会检查：

- 配置和运行目录是否可写
- X 链接 dry-run 路由是否正确
- 示例 Markdown 是否符合输出协议
- 平台定义和站点模板是否完整
- 示例 vault 是否能索引和语义检索
- MCP 依赖是否可用

发布级验收：

```bash
python3 tools/chubby.py --version
python3 tools/platform_smoke.py --mode all --check
python3 tools/golden_outputs.py examples/outputs
python3 tools/mcp_workflow_demo.py
```

更多发布检查见 [docs/release.md](./docs/release.md)。

## 安装方式

### 推荐：分档安装

```bash
bash setup.sh          # 默认 light：轻量能力
bash setup.sh video    # 视频转录重依赖
bash setup.sh podcast  # 播客转录
bash setup.sh wechat   # 公众号/PDF 处理
bash setup.sh all      # 全部依赖
bash setup.sh doctor   # 只做环境体检
```

轻量模式可直接使用：X 图文、小红书图文、公众号基础处理、行业情报雷达、知识库健康检查、content-enrich。视频和播客转录才需要 `ffmpeg`、`yt-dlp`、`funasr`、`torch`、`faster-whisper` 等重依赖。

### 手动安装

```bash
pip install -r requirements.txt
pip install -r podcast-transcribe/requirements.txt
```

每个 skill 都是独立目录，也可以只安装你需要的那个。

### Agent 安装

在 Claude Code、Codex、OpenClaw、Hermes 等支持 Skill 的 Agent 里，可以直接说：

```text
帮我安装这个 skill：https://github.com/chubbyguan/chubbyskills/tree/main/<skill-name>
```

Gitee 镜像：https://gitee.com/chubbyguan/chubbyskills

## 平台能力

| 平台 / 内容 | Skill | 能力 | 默认依赖 | 失败 fallback |
|---|---|---|---|---|
| B站 | [`bilibili-transcribe`](./bilibili-transcribe/SKILL.md) | 字幕优先，视频转录，批量 URL | `yt-dlp`，无字幕需 `ffmpeg` + `funasr` | 无字幕时走音频转录 |
| YouTube | [`youtube-transcribe`](./youtube-transcribe/SKILL.md) | 字幕优先，转录，翻译，中英对照，批量 URL | `yt-dlp`，翻译需 `DEEPSEEK_API_KEY` | 无字幕时走音频转录 |
| 抖音 | [`douyin-transcribe`](./douyin-transcribe/SKILL.md) | 视频转文字稿 | `ffmpeg` + `funasr` | 本地视频转录 |
| TikTok | [`tiktok-transcribe`](./tiktok-transcribe/SKILL.md) | 视频转文字稿 | `yt-dlp` + `ffmpeg` + `funasr` | 本地视频转录 |
| 微博 | [`weibo-transcribe`](./weibo-transcribe/SKILL.md) | 微博视频转文字稿 | `yt-dlp` + `ffmpeg` + `funasr` | 优先移动端链接或本地视频 |
| 知乎 | [`zhihu-transcribe`](./zhihu-transcribe/SKILL.md) | 知乎视频转文字稿 | `yt-dlp` + `ffmpeg` + `funasr` | 本地视频转录 |
| 播客 | [`podcast-transcribe`](./podcast-transcribe/SKILL.md) | 小宇宙 / 喜马拉雅 / RSS / 本地音频转录 | `ffmpeg` + `faster-whisper` | 本地音频转录 |
| 微信公众号 | [`wechat-article-ingest`](./wechat-article-ingest/SKILL.md) | 公众号文章 / PDF 转 Markdown | `beautifulsoup4`，PDF 增强需 `markitdown` / `pymupdf` | PDF 或保存 HTML |
| 小红书 | [`xiaohongshu-ingest`](./xiaohongshu-ingest/SKILL.md) | 图文存图、视频转录、爆款拆解、衍生选题 | 图文零依赖，建议 `XHS_COOKIE` | `--fallback-text` 手动正文 |
| X / Twitter | [`x-ingest`](./x-ingest/SKILL.md) | 推文正文、图片、视频转录，免 API Key | 图文零依赖，视频需 `ffmpeg` + `funasr` | `--fallback-text` 手动正文 |

平台状态页：[docs/platform-status.md](./docs/platform-status.md)

失败分型和 fallback 指南：[docs/platform-fallbacks.md](./docs/platform-fallbacks.md)

## 常用工作流

### 1. 单条链接采集

```bash
python3 tools/chubby_ingest.py "https://www.bilibili.com/video/BVxxxx" -o output/
python3 tools/chubby_ingest.py "https://x.com/user/status/123" -o output/
python3 tools/chubby_ingest.py "https://mp.weixin.qq.com/s/xxx" -o output/
```

自动识别平台失败时，可以显式指定：

```bash
python3 tools/chubby_ingest.py "<链接>" --skill youtube -o output/
```

### 2. 采集后加工摘要和标签

```bash
export DEEPSEEK_API_KEY="..."
python3 tools/chubby_ingest.py "<链接>" -o output/ --enrich
```

`content-enrich` 会补摘要、要点、标签、领域和价值判断，并保留原文。

### 3. 入库到 Obsidian / vault

```bash
python3 tools/chubby_ingest.py "<链接>" --vault ~/Documents/Obsidian/Inbox
```

也可以使用完整管线：

```bash
python3 tools/chubby.py init
python3 tools/chubby.py ingest "<链接>"
python3 tools/chubby.py status --latest
python3 tools/chubby.py retry --all-failed
```

`tools/chubby.py` 会记录：

- `.chubby/runs.jsonl`：每条 source 的状态、错误、输出路径、run_id
- `runs/YYYY-MM-DD.md`：每日运行报告
- schema v1 元数据：`run_id`、`source_hash`、`captured_at`、`processed_at`、`content_type`、`assets`

### 4. 批量队列

把链接逐行放进 `inbox/links.txt`：

```text
https://x.com/user/status/123
https://mp.weixin.qq.com/s/xxx
https://www.bilibili.com/video/BVxxxx
```

运行：

```bash
python3 tools/chubby.py run
python3 tools/chubby.py status --failed
python3 tools/chubby.py retry --all-failed
```

空行和 `#` 注释会被忽略。

### 5. 建立本地知识库索引

```bash
python3 tools/vault_index.py index ~/Documents/ObsidianVault
python3 tools/vault_index.py search "AI Agent"
python3 tools/vault_index.py semantic "内容策略"
python3 tools/vault_index.py recent --limit 10
python3 tools/vault_index.py stats
```

读取某篇笔记：

```bash
python3 tools/vault_index.py read "10_Sources/x/example.md" --vault ~/Documents/ObsidianVault
```

### 6. 使用真实 embedding provider

默认语义检索是零依赖 `semantic-lite`。如果你想用真实向量：

OpenAI：

```bash
export OPENAI_API_KEY="..."
python3 tools/vault_index.py embed ~/Documents/ObsidianVault --provider openai
python3 tools/vault_index.py semantic "内容策略" --provider openai
```

本地模型：

```bash
python3 -m pip install sentence-transformers
python3 tools/vault_index.py embed ~/Documents/ObsidianVault --provider local
python3 tools/vault_index.py semantic "内容策略" --provider local
```

更多说明见 [docs/knowledge-automation.md](./docs/knowledge-automation.md)。

### 7. 自动归档和知识卡片

默认 dry-run，不会移动文件：

```bash
python3 tools/vault_curator.py archive ~/Documents/ObsidianVault
```

确认后真正执行：

```bash
python3 tools/vault_curator.py archive ~/Documents/ObsidianVault --apply
python3 tools/vault_curator.py card ~/Documents/ObsidianVault "10_Sources/x/example.md" --apply
```

归档规则：

- `00_Inbox/**/*.md` 是待处理区。
- 有 `summary`、`archive_status: processed`、`processed` / `evergreen` 标签的笔记进入 `20_Processed/`。
- 其它笔记进入 `10_Sources/<platform>/`。
- 生成知识卡片时会保留来源、平台、source、tags 和关键要点。

### 8. 让 Agent 通过 MCP 使用你的 vault

启动 MCP server：

```bash
pip install mcp
VAULT_DIR=~/Documents/ObsidianVault python3 knowledge-base-management/scripts/mcp_server.py
```

MCP 工具：

- `search_vault`
- `semantic_search_vault`
- `read_kb_note`
- `list_recent_notes`
- `reindex_vault`
- `vault_index_stats`

示例工作流：

```bash
python3 tools/mcp_workflow_demo.py
```

这个 demo 会用 `fixtures/mcp-vault` 完成一次“检索 vault → 读取原文 → 带来源回答”的 Agent 任务。详细配置见 [docs/mcp-workflow.md](./docs/mcp-workflow.md)。

## 质量保障

这个仓库现在不是只提供脚本，也提供可复现的验收层。

| 检查 | 命令 | 作用 |
|---|---|---|
| 输出协议 | `python3 tools/validate_outputs.py examples/outputs --schema-v1` | 确认 Markdown frontmatter 和 schema v1 |
| 平台定义 | `python3 tools/platform_health.py --check` | 校验 `platforms/*.yaml`、模板和脚本路径 |
| 状态页新鲜度 | `python3 tools/platform_health.py --check-output` | 确认 `docs/platform-status.md` 未过期 |
| 平台 smoke | `python3 tools/platform_smoke.py --mode all --check` | 验证 offline / fallback / live 分层 |
| Golden outputs | `python3 tools/golden_outputs.py examples/outputs` | 防止示例输出结构被意外改坏 |
| MCP workflow | `python3 tools/mcp_workflow_demo.py` | 验证 Agent 能通过 vault 完成任务 |

live smoke 是显式 opt-in，因为真实平台会受 cookie、地区、风控、重依赖和链接有效期影响：

```bash
export CHUBBY_SMOKE_X_SOURCE='https://x.com/<user>/status/<id>'
python3 tools/platform_smoke.py --mode live --check
```

## 输出协议

所有采集类 skill 都输出带 frontmatter 的 Markdown，基础字段包括：

| 字段 | 含义 |
|---|---|
| `title` | 标题 |
| `type` | 类型，通常是 `note` |
| `platform` | 机器可读平台 ID，例如 `bilibili` / `x` / `wechat` |
| `source` | 原始链接或本地文件路径 |
| `created` | 入库日期，格式 `YYYY-MM-DD` |
| `author` | 作者 / UP 主 / 公众号，可为空 |
| `tags` | 标签，建议使用 inline list |

经过 `tools/chubby.py` 管线后，会补 schema v1 字段：

| 字段 | 含义 |
|---|---|
| `schema_version` | 当前为 `1` |
| `run_id` | 本次运行 ID |
| `source_hash` | source 短 hash，用于去重和重试 |
| `captured_at` | 采集开始时间 |
| `processed_at` | 处理完成时间 |
| `content_type` | `video` / `audio` / `article` / `social` / `note` |
| `status` | `success` / `failed` / `dry_run` |
| `assets` | 关联资源目录列表 |

校验：

```bash
python3 tools/validate_outputs.py output/ --schema-v1
```

## Skill 目录

| 类型 | Skill | 说明 |
|---|---|---|
| 视频转录 | [`douyin-transcribe`](./douyin-transcribe/SKILL.md) | 抖音视频转文字稿 |
| 视频转录 | [`bilibili-transcribe`](./bilibili-transcribe/SKILL.md) | B站字幕优先 / 视频转录 / 批量处理 |
| 视频转录 | [`tiktok-transcribe`](./tiktok-transcribe/SKILL.md) | TikTok 视频转文字稿 |
| 视频转录 | [`weibo-transcribe`](./weibo-transcribe/SKILL.md) | 微博视频转文字稿 |
| 视频转录 | [`zhihu-transcribe`](./zhihu-transcribe/SKILL.md) | 知乎视频转文字稿 |
| 视频转录 | [`youtube-transcribe`](./youtube-transcribe/SKILL.md) | YouTube 转录、翻译、中英对照 |
| 播客转录 | [`podcast-transcribe`](./podcast-transcribe/SKILL.md) | 播客 / RSS / 本地音频转文字 |
| 图文采集 | [`wechat-article-ingest`](./wechat-article-ingest/SKILL.md) | 公众号文章和 PDF 转 Markdown |
| 图文采集 | [`xiaohongshu-ingest`](./xiaohongshu-ingest/SKILL.md) | 小红书图文 / 视频 / 爆款拆解 |
| 图文采集 | [`x-ingest`](./x-ingest/SKILL.md) | X / Twitter 推文、图片、视频 |
| 内容加工 | [`content-enrich`](./content-enrich/SKILL.md) | 摘要、要点、标签、价值判断 |
| 知识库 | [`knowledge-base-management`](./knowledge-base-management/SKILL.md) | vault 管理、健康检查、索引、MCP |
| 工作流 | [`industry-intelligence-radar`](./industry-intelligence-radar/SKILL.md) | 多源情报扫描和趋势简报 |
| 工作流 | [`learning-notes-automation`](./learning-notes-automation/SKILL.md) | 学习笔记、闪卡、知识图谱 |

## 仓库结构

```text
.
├── platforms/                 # 平台定义：状态、依赖、fallback、样例 source
├── templates/sites/           # 站点模板：URL match、frontmatter、postprocess
├── tools/                     # 管线、索引、smoke、golden、归档、适配工具
├── examples/outputs/          # 示例 Markdown 输出
├── fixtures/                  # golden outputs、platform smoke、MCP demo vault
├── vault-template/            # Obsidian vault 推荐结构
├── knowledge-base-management/ # 知识库管理 skill 和 MCP server
└── *-transcribe / *-ingest    # 各平台 skill
```

## 贡献新平台

不要从复制旧目录开始。先生成最小可验证骨架：

```bash
python3 tools/platform_adapter.py new hacker-news \
  --name "Hacker News" \
  --sample-source "https://news.ycombinator.com/item?id=123" \
  --match "news.ycombinator.com"
```

然后跑：

```bash
python3 tools/platform_health.py --check
python3 tools/platform_smoke.py --mode offline --check
```

贡献规则见 [CONTRIBUTING.md](./CONTRIBUTING.md) 和 [docs/contributor-platform-adapter.md](./docs/contributor-platform-adapter.md)。

## 文档入口

- [快速开始](./docs/quickstart.md)
- [平台状态](./docs/platform-status.md)
- [平台失败分型和 fallback](./docs/platform-fallbacks.md)
- [知识库自动化](./docs/knowledge-automation.md)
- [MCP workflow](./docs/mcp-workflow.md)
- [贡献者平台适配](./docs/contributor-platform-adapter.md)
- [发布检查](./docs/release.md)
- [更新日志](./CHANGELOG.md)

## 环境变量

| 变量 | 用途 |
|---|---|
| `DEEPSEEK_API_KEY` | 内容加工、翻译、爆款拆解、学习笔记提取 |
| `XHS_COOKIE` | 小红书登录态，提高采集成功率 |
| `VAULT_DIR` | MCP server 默认 vault 路径 |
| `VAULT_INDEX_DB` | MCP server 自定义 SQLite 索引位置 |
| `OPENAI_API_KEY` | OpenAI embedding provider |
| `OPENAI_EMBEDDING_MODEL` | OpenAI embedding 模型，默认 `text-embedding-3-small` |
| `OPENAI_BASE_URL` | OpenAI 兼容代理或网关 |
| `CHUBBY_EMBEDDING_PROVIDER` | MCP / semantic 使用 `lite`、`openai` 或 `local` |
| `CHUBBY_LOCAL_EMBEDDING_MODEL` | 本地 embedding 模型 |
| `CHUBBY_SMOKE_<PLATFORM>_SOURCE` | 指定某个平台的 live smoke 链接 |

## 合规与免责

本仓库所有采集类 skill 仅供个人学习与研究使用：

- 请遵守目标平台服务条款、`robots.txt` 和相关法律法规。
- 不要用于批量抓取、商用爬取、二次分发或侵犯他人权益的场景。
- 抓取和转录所得内容版权归原作者所有，引用或转载请获得授权并注明出处。
- 涉及 cookie 或登录态时，仅在你自己的账号和授权范围内使用。
- 本项目按「现状」（AS IS）提供，作者不对使用本工具产生的后果负责。

如平台方或权利人认为某 skill 不当，欢迎提交 issue，我会及时处理。

## 致谢

- [Agent Skills](https://agentskills.io) — Agent Skill 开放标准
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载
- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 中文语音识别
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) / [OpenAI Whisper](https://github.com/openai/whisper) — 播客和音频转录
- [microsoft/markitdown](https://github.com/microsoft/markitdown) / [PyMuPDF](https://github.com/pymupdf/PyMuPDF) — 文档和 PDF 处理
- [Obsidian](https://obsidian.md/) — 本地知识库载体
- [GraphRAG](https://github.com/microsoft/graphrag) — 知识图谱方向参考
- [DeepSeek](https://platform.deepseek.com/) — 内容加工和翻译
- [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills) — 仓库结构和 README 风格参考

## 关于 Chubby

我是 Chubby，AI + 电商的探索者。平时做内容、搭个人知识库，也写一些 AI Agent / Skill 的实践。这个仓库里的工具，是我自己每天在用的一套内容入库工作流。

- X / Twitter: https://x.com/Chubbyguan
- 即刻: https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5
- 小红书: https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8
- 微信公众号：**关关不过**

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@chubbyguan](https://github.com/chubbyguan)

</div>
