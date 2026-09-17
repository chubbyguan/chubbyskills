<div align="center">

**中文** · [English](./README.en.md)

# 🧰 Chubby Skills

### 信息流会忘，知识库会记，Agent 会用。

把视频、播客、文章和本地文档保存为 Markdown，整理成能搜索、能回查来源、能交给 Agent 使用的素材库。

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Version](https://img.shields.io/badge/Version-0.13.0-10B981?style=for-the-badge)](https://github.com/chubbyguan/chubbyskills/releases/tag/v0.13.0)
[![Skills](https://img.shields.io/badge/Skills-14-10B981?style=for-the-badge)](#skill-目录)
[![Stars](https://img.shields.io/github/stars/chubbyguan/chubbyskills?style=for-the-badge&color=F59E0B)](https://github.com/chubbyguan/chubbyskills/stargazers)

[快速开始](#快速开始) · [安装到 Agent](#安装到-agent) · [Skill 目录](#skill-目录) · [文档](#文档入口) · [更新日志](./CHANGELOG.md)

</div>

## 这是什么

Chubby Skills 是一套面向内容创作者和个人知识库的 **14 个 Agent Skills 与命令行工具**。你可以按需安装技能，让 Agent 处理素材；也可以直接运行命令，把采集、入库、搜索和资料包导出串起来。

适合经常收藏视频、文章和播客，希望在写作时找到原文、核对出处的人。产物保存在本地 Markdown 文件中，可以用 Obsidian、文本编辑器或你的 Agent 继续处理。

```text
链接 / 本地文档 → Markdown 原文与附件 → 本地搜索 → 带出处的资料包 → Agent 整理选题
```

| 你想做什么 | 项目提供什么 |
|---|---|
| 保存平台素材 | 视频字幕与转录、播客转录、文章和图文采集 |
| 导入已有资料 | Markdown、TXT、PDF 文字层导入，保留来源和引用的本地附件 |
| 写作时找回证据 | 关键词搜索、可选语义检索、原文读取；采集入库后自动更新索引 |
| 整理一份选题资料 | 导出 Markdown / JSON 资料包，包含原文摘录、行号、来源和文件摘要 |
| 让 Agent 使用知识库 | 独立技能包，以及提供搜索、原文读取等工具的可选 MCP 服务 |

先看[输出样例](./examples/README.md)，或直接运行下面的本地示例。

<a id="安装方式"></a>

## 快速开始

建议使用 **Python 3.11 或 3.12，macOS / Linux shell**。下面用一份示例 Markdown 跑通「导入 → 搜索 → 资料包」，无需安装第三方 Python 包、配置 API Key 或下载模型。

### 1. 获取项目并配置知识库

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 -m venv .venv
source .venv/bin/activate
python3 tools/chubby.py init --vault "$PWD/creator-vault"
```

`init` 会创建 `chubby.yaml` 和知识库目录。下面的命令在仓库根目录运行，沿用这份配置。已有知识库可将 `--vault` 换成它的根目录；已有配置的调整见[创作者工作流](./docs/creator-workflow.md)。

### 2. 导入一份文档

```bash
mkdir -p demo-input
cat > demo-input/notes.md <<'NOTE'
# 内容复用笔记

内容复用从保留原文和来源开始。同一份材料可以用于选题、文章和播客，但引用前要重新核对上下文。
NOTE

python3 tools/chubby.py import demo-input/notes.md --no-enrich
```

将示例路径换成自己的 `.md`、`.markdown` 或 `.txt` 文件即可导入真实材料。已知原始网页时，加 `--source-url "原始网页地址"`；本地文件默认记录文件 URI。

### 3. 搜索并导出资料包

```bash
python3 tools/chubby.py search "内容复用"
python3 tools/chubby.py brief --topic "内容复用" \
  --output "$PWD/creator-vault/30_Output/brief.md"
python3 tools/chubby.py status --latest
```

你会得到：

- `creator-vault/00_Inbox/`：带来源信息的 Markdown 和引用的本地附件。
- `creator-vault/30_Output/brief.md` 与 `brief.json`：包含逐字摘录、原文行号、来源和 SHA-256 的资料包。
- `.chubby/runs.jsonl` 与 `runs/`：任务状态和运行报告，方便检查失败与重试。

打开资料包核对引用，然后交给 Agent 整理选题。`brief` 在本地导出证据，不调用云模型，也不判断原文观点是否正确。上面的演示材料是人工样例；平台采集需要下一节对应的依赖。

再次导出时请换一个输出文件名；确认要替换已生成的资料包后再加 `--force`。

## 处理你的素材

### 平台链接

按所需能力安装运行依赖。以 YouTube 字幕为例：

```bash
bash setup.sh light
python3 -m pip install yt-dlp
python3 tools/chubby.py doctor --platform youtube
python3 tools/chubby.py ingest "替换为你的真实链接" --no-enrich
python3 tools/chubby.py search "原文中的关键词"
```

`light` 检查 Python 并提示轻量路径，不安装字幕或转录依赖。B站和 YouTube 优先取字幕；没有字幕时需要视频转录依赖。查看 [Skill 目录](#skill-目录)选择平台，并按下表补依赖：

| 处理路径 | 安装 / 配置 |
|---|---|
| Markdown / TXT 导入、关键词检索、资料包 | Python 标准库，无需额外包 |
| X / 小红书图文 | Python 标准库；`bash setup.sh light` 检查环境，登录态与平台限制仍可能影响采集 |
| B站 / YouTube 字幕 | `python3 -m pip install yt-dlp` |
| 本地视频转录 | `bash setup.sh video`；需要系统 `ffmpeg`，本地模型首次使用会下载 |
| 本地播客转录 | `bash setup.sh podcast`；使用 `faster-whisper`，默认模型 `small` |
| 公众号及其 PDF 路径 | `bash setup.sh wechat` |
| 通用 PDF 文字层导入 | `python3 -m pip install 'pymupdf>=1.24'` |

平台抓取受 Cookie、字幕、地区和页面变化影响。失败时查看[平台状态](./docs/platform-status.md)和[替代处理方式](./docs/platform-fallbacks.md)，也可以保存正文后走本地导入。支持范围与最近的实测结果分开记录，见[真实平台验证](./docs/live-verification.md)。

### 本地文档与 PDF

```bash
python3 tools/chubby.py import "/你的资料目录/report.md" --no-enrich
python3 tools/chubby.py import "/你的资料目录/report.pdf" \
  --source-url "https://example.org/original-report" --no-enrich
```

导入器保留原文件，把文档引用的目录内附件复制到产物旁；缺失或越界的本地附件会报错。PDF 只提取文字层，不做 OCR；扫描件需先由其他工具识别。详见[文档导入](./docs/document-import.md)。

### 播客与可选云转录

默认在本地转录音频：

```bash
python3 tools/chubby.py ingest "/你的音频目录/episode.mp3" \
  --skill podcast --provider local --no-enrich
```

v0.13.0 新增 **Atlas Cloud / MuAPI 实验后端**。需要主动选择 provider 并配置对应凭据；云服务会接收音频并可能计费。任务 ID 和完成结果持久保存，轮询失败或进程中断后可恢复；`--resubmit` 会明确创建新任务，可能再次计费。

播客自动下载仅接受公网 HTTP(S) 直连地址，不跟随重定向，也不使用代理。需要跳转或代理的资源，先自行下载，再传本地文件。配置和恢复方法见[云转录说明](./docs/cloud-transcription.md)。云服务的真实转录尚未完成验收。

### 重复采集、批量与重试

相同来源、处理参数和目的地的有效产物会复用；原文件或引用附件变化后会重新导入。`--refresh` 重新处理并保留旧版本。

把链接逐行放入 `inbox/links.txt`，再运行：

```bash
python3 tools/chubby.py run --queue inbox/links.txt --no-enrich
python3 tools/chubby.py status --failed
python3 tools/chubby.py retry --all-failed
```

采集入库后和统一查询前，索引会增量同步。更多例子见[创作者工作流](./docs/creator-workflow.md)；已有索引的迁移和重建见[知识库自动化](./docs/knowledge-automation.md)。

## 安装到 Agent

### 按需安装技能

在完整仓库根目录运行。以 Codex 为例，安装知识库技能：

```bash
python3 tools/install_skill.py knowledge-base-management --dest ~/.codex/skills
```

查看技能列表；如果选择全部安装，用 `--all` 替代上面的单技能安装，并指定一个没有同名技能的目标目录：

```bash
python3 tools/install_skill.py --list
python3 tools/install_skill.py --all --dest /path/to/agent/skills
```

Claude Code、OpenCode、OpenClaw、Hermes 等客户端使用各自实际配置的 skills 目录作为 `--dest`，并按客户端方式启用技能。运行环境中的 Python 和系统依赖仍需另外配置。

安装器会打包仓库内依赖，生成可独立搬移的技能目录；`setup.sh` 负责安装运行依赖。已有同名技能时安装器会拒绝覆盖，升级时先安装到临时目录核对自己的修改。请使用安装器或 [Release 技能包](https://github.com/chubbyguan/chubbyskills/releases/tag/v0.13.0)，避免只下载单个源码目录漏掉公共模块。[完整安装指南](./docs/installation.md)

首页的 `tools/chubby.py` 统一流程需要完整仓库。独立知识库技能使用其自带的 `tools/import_document.py`、`tools/vault_index.py` 和 `tools/evidence_brief.py`，命令见[文档导入](./docs/document-import.md)。

### 通过 MCP 连接知识库

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

MCP 提供搜索、语义检索、读取原文、最近笔记、重新索引和统计共 6 个工具。上面的命令用临时知识库检查真实服务启动和交互；连接自己的 Agent 时，还需配置服务器命令与 `VAULT_DIR`。见 [MCP 配置](./docs/mcp-workflow.md)。

## Skill 目录

| 方向 | Skill | 主要用途 |
|---|---|---|
| 视频 | [bilibili-transcribe](./bilibili-transcribe/SKILL.md) | B站字幕优先、视频转录、批量处理 |
| 视频 | [youtube-transcribe](./youtube-transcribe/SKILL.md) | YouTube 字幕、转录、可选翻译与中英对照 |
| 视频 | [douyin-transcribe](./douyin-transcribe/SKILL.md) | 抖音视频转文字稿 |
| 视频 | [tiktok-transcribe](./tiktok-transcribe/SKILL.md) | TikTok 视频转录 |
| 视频 | [weibo-transcribe](./weibo-transcribe/SKILL.md) | 微博视频转录 |
| 视频 | [zhihu-transcribe](./zhihu-transcribe/SKILL.md) | 知乎视频转录 |
| 播客 | [podcast-transcribe](./podcast-transcribe/SKILL.md) | 单集、RSS、本地音频；可选实验云后端 |
| 图文 | [wechat-article-ingest](./wechat-article-ingest/SKILL.md) | 公众号文章和 PDF 转 Markdown |
| 图文 | [xiaohongshu-ingest](./xiaohongshu-ingest/SKILL.md) | 小红书图文、视频及可选内容分析 |
| 图文 | [x-ingest](./x-ingest/SKILL.md) | X / Twitter 正文、图片和视频 |
| 加工 | [content-enrich](./content-enrich/SKILL.md) | 可选的摘要、要点和标签加工 |
| 知识库 | [knowledge-base-management](./knowledge-base-management/SKILL.md) | 文档导入、索引、资料包、归档与 MCP |
| 工作流 | [industry-intelligence-radar](./industry-intelligence-radar/SKILL.md) | 多源情报扫描和趋势简报 |
| 工作流 | [learning-notes-automation](./learning-notes-automation/SKILL.md) | 学习笔记、闪卡和知识关联 |

## 数据与处理边界

素材默认保存在本地。不同处理路径的联网范围如下：

| 功能 | 处理位置与配置 |
|---|---|
| 文档导入、关键词搜索、`semantic-lite`、资料包 | 本地；本地导入不抓取远程附件 |
| 平台采集 | 访问来源平台；小红书可按需配置自己的 `XHS_COOKIE` |
| 本地音视频转录 | 本机推理；首次运行可能需要下载模型 |
| 内容加工、翻译、学习笔记提取 | 可选 `DEEPSEEK_API_KEY`，内容发送至对应 API |
| OpenAI 向量检索 | 可选 `OPENAI_API_KEY`，参与向量化的内容发送至 API |
| Atlas / MuAPI 转录 | 可选 `ATLAS_API_KEY` / `MUAPI_API_KEY`，音频发送至服务商 |
| 云端 Agent 读取素材 | 被读取的内容进入该 Agent 的模型上下文 |

API 服务可能计费，密钥和 Cookie 不要写入笔记或提交到仓库。外部解析工具可以把完整 Markdown 交给本地导入；cue-omni-reader 等入口及其验证状态见[可选集成](./docs/integrations.md)。

## 输出协议

采集与导入产物使用带 frontmatter 的 Markdown，记录标题、类型、平台、来源和日期。统一 CLI 还会补充 schema v1 的任务 ID、采集时间、来源摘要与附件信息，供索引和重试使用。[查看输出样例](./examples/README.md)

```bash
python3 tools/validate_outputs.py output/ --schema-v1
```

## 验证与社区贡献

[v0.13.0 发布记录](./docs/release-0.13.0.md)包含 **220 项测试、Linux / macOS CI、14 个技能包的 24 个脚本隔离导入、实际 PDF 导入和 MCP 交互验证**。发布资产附带校验和与验证记录；这些结果不代表所有平台或云服务都已完成在线验收。

本地环境自检：

```bash
python3 tools/chubby.py quickstart --ephemeral --no-state
```

这条命令检查离线样例和环境，不抓取真实平台内容。开发者的完整命令见[发布检查](./docs/release.md)。

安装建议来自 [catwithtudou 的 #1](https://github.com/chubbyguan/chubbyskills/pull/1)；Atlas 和 MuAPI 需求分别来自 [binyangzhu000-sudo 的 #3](https://github.com/chubbyguan/chubbyskills/pull/3) 与 [Anil-matcha 的 #5](https://github.com/chubbyguan/chubbyskills/pull/5)。这些需求已通过现行实现吸收并保留归属。 [huhoo 的 #6](https://github.com/chubbyguan/chubbyskills/pull/6) 已进入可选集成文档，真实解析示例仍待补充。[处理记录](./docs/community-triage.md)

欢迎提交可复现的问题、修正 PR 或平台适配。贡献方式见 [CONTRIBUTING.md](./CONTRIBUTING.md) 和[平台适配指南](./docs/contributor-platform-adapter.md)。

## 文档入口

| 文档 | 内容 |
|---|---|
| [安装指南](./docs/installation.md) | 运行依赖、技能目录、独立安装与升级 |
| [创作者工作流](./docs/creator-workflow.md) | 从素材到搜索、资料包和 Agent 选题 |
| [文档导入](./docs/document-import.md) | Markdown / TXT / PDF、来源和附件规则 |
| [云转录](./docs/cloud-transcription.md) | Provider 配置、任务恢复和计费边界 |
| [知识库自动化](./docs/knowledge-automation.md) | 索引、向量检索、归档和知识卡片 |
| [MCP 配置](./docs/mcp-workflow.md) | 将知识库接入 Agent |
| [平台状态与替代方式](./docs/platform-fallbacks.md) | 依赖、常见失败与补救路径 |
| [可选集成](./docs/integrations.md) | 外部解析工具的 Markdown 交接 |
| [更新日志](./CHANGELOG.md) | 版本变化；当前版本为 **0.13.0** |

## 使用范围与许可

采集类技能用于个人学习与研究。请遵守来源平台条款、`robots.txt` 和相关法律，使用自己有权访问和保存的内容；不要用于批量抓取、商用爬取、二次分发或侵犯他人权益的场景。原内容版权归原作者，引用与转载按需要取得授权并注明来源。

代码采用 [MIT License](./LICENSE)，按现状提供。代码许可不授予第三方内容的使用权。

<details>
<summary>致谢</summary>

感谢 [Agent Skills](https://agentskills.io)、[yt-dlp](https://github.com/yt-dlp/yt-dlp)、[SenseVoice](https://github.com/FunAudioLLM/SenseVoice)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[Whisper](https://github.com/openai/whisper)、[MarkItDown](https://github.com/microsoft/markitdown)、[PyMuPDF](https://github.com/pymupdf/PyMuPDF)、[Obsidian](https://obsidian.md/)、[GraphRAG](https://github.com/microsoft/graphrag)、[DeepSeek](https://platform.deepseek.com/) 以及 [khazix-skills](https://github.com/KKKKhazix/khazix-skills) 提供工具、标准和参考。

</details>

## 关于 Chubby

我是 Chubby，平时做内容、搭个人知识库，也记录 AI Agent / Skill 和电商实践。

[X / Twitter](https://x.com/Chubbyguan) · [即刻](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5) · [小红书](https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8) · 微信公众号：**关关不过**

[Gitee 镜像](https://gitee.com/chubbyguan/chubbyskills) · Made by [@chubbyguan](https://github.com/chubbyguan)
