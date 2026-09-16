<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

#### 信息流会忘，知识库会记，Agent 会用。

<h3 align="center"><strong>把收藏素材变成可引用的选题资料库</strong></h3>

<p align="center"><em>保存视频、文章和图文的原文与来源，让 Agent 从你的素材库中查找证据、整理选题。</em></p>

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Version](https://img.shields.io/badge/Version-0.11.1-10B981?style=for-the-badge)](./CHANGELOG.md)
[![Skills](https://img.shields.io/badge/Skills-14-10B981?style=for-the-badge)](#skill-目录)
[![Stars](https://img.shields.io/github/stars/chubbyguan/chubbyskills?style=for-the-badge&color=F59E0B)](https://github.com/chubbyguan/chubbyskills/stargazers)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-8B5CF6?style=flat-square)
![Hermes](https://img.shields.io/badge/Hermes-Skill-EC4899?style=flat-square)

</div>

---

## 这是什么

Chubby Skills 是一套面向内容创作者的采集和知识库工具。把 B站、YouTube、抖音、小红书、公众号、X、播客等素材保存为本地 Markdown，再通过搜索或 MCP 让 Agent 读取原文、整理带来源的选题资料。

如果你经常收藏内容，写作时却找不到原文，并且已经在使用 Agent 或 Obsidian，可以从下面的一条素材开始。完整流程见[创作者工作流](./docs/creator-workflow.md)，安装前也可以先看[输出样例](./examples/README.md)。

**本地存储是默认路径。**采集需要访问内容平台，字幕和登录态影响成功率；DeepSeek 内容加工、OpenAI embedding 等可选功能会把内容发送给对应 API，可能计费。使用云端 Agent 时，它读取的素材也会进入模型上下文。[工具选择与处理边界](./docs/comparison.md)

## 从一条真实素材开始

以下命令适用于有 Python 3 的 macOS / Linux shell。先克隆完整仓库，建立独立运行环境：

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 -m venv .venv
source .venv/bin/activate
bash setup.sh light
python3 tools/chubby.py init
```

选一条你有权保存的真实链接，先查看下方平台要求，再运行：

```bash
python3 tools/chubby.py ingest "替换为你的真实链接" \
  --vault "$PWD/creator-vault/00_Inbox" --no-enrich
python3 tools/chubby.py status --latest
python3 tools/vault_index.py --db "$PWD/creator-vault/index.sqlite" index "$PWD/creator-vault"
python3 tools/vault_index.py --db "$PWD/creator-vault/index.sqlite" search "替换为原文中的关键词"
```

打开生成的 Markdown，核对正文、来源和需要保留的图片。**第一次成功指你自己的真实素材保存完整，并能找回原文。**手动正文 fallback 要单独记录，不能当作自动抓取成功。之后按[创作者工作流](./docs/creator-workflow.md)用 3 条素材整理一份带引用的选题资料。

只想先检查环境，可以运行：

```bash
python3 tools/chubby.py quickstart --ephemeral --no-state
```

这是离线样例与环境检查，不抓真实平台，不证明登录态、平台可用性或用户素材质量。需要 MCP 时还要运行后面的协议检查。

## 安装方式

### 运行依赖

在已激活的虚拟环境中，按需要选择：

```bash
bash setup.sh light   # 轻量图文与知识库路径
bash setup.sh video   # 本地视频转录依赖
bash setup.sh podcast # 本地播客转录依赖
bash setup.sh wechat  # 公众号 / PDF 依赖
bash setup.sh all     # 全部运行依赖
bash setup.sh doctor  # 环境体检
```

`setup.sh` 安装运行依赖，不负责把 skill 注册到 Agent。字幕优先路径需要 `yt-dlp`；没有字幕时才需要本地转录模型。X / 小红书图文不需要视频模型，视频转录需另外安装 `video` 依赖。

### 放入 Agent 的技能目录

从完整仓库生成带公共源码的独立技能包。例如安装到 Codex：

```bash
python3 tools/install_skill.py bilibili-transcribe --dest ~/.codex/skills
```

多个技能可在命令中依次列出；全部安装使用 `--all`。其它 Agent 用其实际技能目录作为 `--dest`。安装器不安装 Python 依赖、不启动 Agent，遇到已有同名目录会拒绝覆盖。

源码中的技能会引用仓库公共模块，不要只下载 GitHub 上的单个 skill 目录。使用安装器生成的目录可以整体搬移。完整说明见[安装指南](./docs/installation.md)。

### 可选：知识库 MCP

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

该检查会启动真实 MCP 进程并验证协议交互。连接自己的 Agent 和 vault 见 [MCP 配置](./docs/mcp-workflow.md)。

Gitee 镜像：[chubbyguan/chubbyskills](https://gitee.com/chubbyguan/chubbyskills)。

## 现在有什么

当前版本：`0.11.1`。

| 模块 | 用途 | 入口 |
|---|---|---|
| 平台采集 | 内容转成保留来源的 Markdown | `tools/chubby_ingest.py` / 各 skill 脚本 |
| 管线编排 | 队列、状态、重试、每次运行报告 | `tools/chubby.py` |
| 内容加工 | 可选的摘要、要点、标签 | `content-enrich` |
| 知识库 | 本地索引、搜索、读取原文、归档与知识卡片 | `tools/vault_index.py` / `tools/vault_curator.py` |
| MCP | Agent 搜索、读取和管理知识库索引 | `knowledge-base-management/scripts/mcp_server.py` |
| 维护工具 | 平台定义、分层 smoke、输出格式、适配骨架 | `tools/`；见[发布检查](./docs/release.md) |

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

平台状态页：[docs/platform-status.md](./docs/platform-status.md)。上表列出实现范围，不是在线成功保证。状态页来自平台定义和模板；`stable` 等标签不能替代最近的真实链接测试。

最近一次[真实平台验证报告](./docs/live-verification.md)记录测试日期、环境和结果；失败分型见 [fallback 指南](./docs/platform-fallbacks.md)。

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
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
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

这个 demo 用 `fixtures/mcp-vault` 演示索引、读取与带来源回答的逻辑；它不是 Agent 客户端的端到端验证。真实 MCP 协议检查运行 `python3 tools/mcp_smoke.py --json`。详细配置见 [docs/mcp-workflow.md](./docs/mcp-workflow.md)。

## 质量保障

这个仓库现在不是只提供脚本，也提供可复现的验收层。

| 检查 | 命令 | 作用 |
|---|---|---|
| 输出协议 | `python3 tools/validate_outputs.py examples/outputs --schema-v1` | 确认 Markdown frontmatter 和 schema v1 |
| 平台定义 | `python3 tools/platform_health.py --check` | 校验 `platforms/*.yaml`、模板和脚本路径 |
| 状态页一致性 | `python3 tools/platform_health.py --check-output` | 检查状态页与定义是否一致，不验证平台在线可用性 |
| 平台 smoke | `python3 tools/platform_smoke.py --mode all --check` | 分层检查；未配置的 live 项不等于成功 |
| Golden outputs | `python3 tools/golden_outputs.py examples/outputs` | 防止示例输出结构被意外改坏 |
| 本地示例工作流 | `python3 tools/mcp_workflow_demo.py` | 验证 fixture 上的索引与来源读取逻辑 |
| MCP 协议 | `python3 tools/mcp_smoke.py --json` | 启动真实 server，检查握手和工具调用 |

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
├── chubby_common/             # 公共模块：yt-dlp / SenseVoice 封装、依赖体检、Markdown 生成
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

- [创作者工作流：素材到可引用选题](./docs/creator-workflow.md)
- [安装指南](./docs/installation.md)
- [离线环境与样例检查](./docs/quickstart.md)
- [平台状态](./docs/platform-status.md)
- [平台失败分型和 fallback](./docs/platform-fallbacks.md)
- [知识库自动化](./docs/knowledge-automation.md)
- [MCP workflow](./docs/mcp-workflow.md)
- [贡献者平台适配](./docs/contributor-platform-adapter.md)
- [发布检查](./docs/release.md)
- [工具选择与处理边界](./docs/comparison.md)
- [十人试用计划（待执行）](./docs/user-pilot.md)
- [社区贡献处理计划](./docs/community-triage.md)
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
