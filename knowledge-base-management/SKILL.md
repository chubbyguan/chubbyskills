---
name: knowledge-base-management
description: "Obsidian 知识库全生命周期管理：三层架构、素材入库(ABC分级)、健康检查、GBrain/GraphRAG/LLM Wiki 三件套集成、目录整理"
triggers:
  - "知识库管理"
  - "素材入库"
  - "健康检查"
  - "盘点知识库"
  - "清理知识库"
  - "搜索知识库"
  - "GBrain"
  - "GraphRAG"
  - "知识图谱"
  - "整理知识库"
  - "知识库架构"
version: 1.0
created: 2026-06-02
tags: [knowledge-base, obsidian, wiki, note-taking, gbrain, graphrag]
---

# Knowledge Base Management — 知识库全生命周期管理

## 核心架构

### 三层架构

```
素材库/  → Layer 1: 不可变原始素材（AI 只读）
wiki/    → Layer 2: AI 编译的结构化知识（AI 维护）
产出/    → Layer 3: 按需生成的视图（不持久化）
```

**核心原则**：素材库是事实源（不可变），Wiki 是 AI 编译的投影（必须溯源），产出是按需生成的视图（不持久化）。

### Vault 配置

vault 路径通过环境变量配置，不写死在脚本里：

```bash
export VAULT_DIR="$HOME/Documents/your-vault"   # 你的 Obsidian vault 根目录
```

- **健康检查 cron**：建议每周日 9:00 运行 `scripts/vault_health_check.py`（见第 2 节）

---

## 1. 素材入库 (Ingest)

### 新素材处理流水线

```
用户丢素材 →
  ① 判断类型 → 存入素材库/对应子目录
  ② 提取关键信息 → 决定是否建 wiki 页面
  ③ 如果值得：建选题（打 SHARP 分）或更新项目页
  ④ 更新 wiki/index.md 索引
```

### 素材分级 (ABC Grading)

| 等级 | 标准 | 处理 |
|------|------|------|
| **A** | 核心方法论/框架/系统 | 优先编译为选题 |
| **B** | 有洞察但不够系统 | 备选，作为 A 的补充 |
| **C** | 水货/重复/与定位无关 | 归档，不主动编译 |

### 公众号文章处理

**来源一：wechat-article-exporter 自动同步（每天 07:00 cron）**
公众号文章直接存入 `素材库/公众号文章/<公众号名>/`，每日自动增量同步。

**来源二：手机保存的文章同步（每天 08:00 cron）**
通过手机保存的文章先落到一个待处理目录（按日期），再由一个归类脚本搬入素材库并按领域筛选优质文章做 A+B 深度处理。

> 归类脚本（如 `sync_notes_to_kb.py`）与各人的目录结构强相关，本仓库不内置，按下面的「工作流」自建即可。

**工作流**：
```
新文章入库 →
  ① 脚本自动归类到 素材库/公众号文章/<公众号名>/
  ② URL 去重（跳过已存在的文章）
  ③ 领域关键词筛选（AI/半导体/消费/电商/品牌/投资/Agent/Skill）
     跳过纯营销、与用户领域无关的文章
  ④ 命中关键词的精选文章 → A+B 双轨处理（每日上限 5 篇）
     A层：观点提取+分类+3条Takeaway → wiki/📡 外部输入/公众号/<公众号名>/<主题>/
     B层：问题链+伴读引导 → 同上
  ⑤ 更新 wiki/index.md（外部输入 — 最新 A+B 处理 表格）
```

**关键原则**：
- 聚焦高价值主题（匹配用户兴趣），不追求全量覆盖
- 每个 wiki 页面必须用 `source` frontmatter 列出引用素材路径
- 深度处理上限 5 篇/天，分批消化
- 文章路径格式：`[[../../../../素材库/公众号文章/<公众号>/<文件名>]]`

---

## 2. 健康检查 (Audit)

### 自动检查项

每周日 9:00 cron 自动运行，检查：
- 断链（broken wikilinks）
- 缺 source 字段
- frontmatter 缺失
- 待沉淀概念
- 低链接密度

**脚本**：`scripts/vault_health_check.py`（本仓库提供，零依赖，纯标准库）

```bash
# 指定 vault 路径
python3 scripts/vault_health_check.py "$HOME/Documents/your-vault"

# 或读 VAULT_DIR 环境变量
export VAULT_DIR="$HOME/Documents/your-vault"
python3 scripts/vault_health_check.py --json

# 把缺 source 字段也视为问题（强溯源场景）
python3 scripts/vault_health_check.py --require-source
```

检查项：断链、缺 frontmatter/source/summary、孤立笔记、空目录、内容重复、文件名含空格。
存在断链时退出码为 1，方便接入 cron / CI 告警。

### 清理标准

| 操作 | 规则 |
|------|------|
| 去重 | SHA256 或 diff 确认相同后删除副本 |
| 归位 | 散落文件按类型移到素材库/对应子目录 |
| 归档 | 历史版本移到 `wiki/🗄️ 归档/`，不删除 |
| 空目录 | 直接删除。含 redirect README 的 legacy 目录也算空目录 |
| 全库审计 | 执行第 6 节「全库审计与批量归档」 |
| 目录审查 | 执行第 5 节「目录审查与增量清理」 |

### 文件命名规范

```
✅ 选题-AI-Agent-未来方向.md    # 连字符连接，无空格
❌ 选题-DemisHassabis Agent.md  # 含空格，wikilink 断裂
```

### 迁移提示页格式

当文档内容迁移到新位置时，旧文件不删除，改为迁移提示：

```yaml
---
title: ⚠️ 已迁移 - 原文件名（旧版 vX.0）
type: note
tags: [已废弃, 旧版, 已迁移]
created: YYYY-MM-DD
summary: 已被 [[新位置/新文件名|新版本]] 取代。
---
```

**关键规则**：
- frontmatter: `⚠️ 已迁移` 标题 + `已废弃` 标签
- 说明为什么旧版不再适用（1-3条）
- 明确的新链接
- **不要保留旧的正文内容**

---

## 3. 工具集成 (Tools)

### 🔌 MCP Server（本仓库提供，推荐）

`scripts/mcp_server.py` 把知识库的「搜索 / 读取 / 最近笔记」暴露成 MCP 工具，让**任何支持 MCP 的 Agent**（Claude Code、Codex 等）直接查你的库——形成「采集类 skill 负责写入、MCP 负责被调用查询」的闭环。

```bash
pip install mcp
VAULT_DIR=/path/to/your-vault python3 scripts/mcp_server.py
```

在 Agent 的 MCP 配置里：

```json
{
  "mcpServers": {
    "chubby-kb": {
      "command": "python3",
      "args": ["<knowledge-base-management/scripts/mcp_server.py 的绝对路径>"],
      "env": { "VAULT_DIR": "/path/to/your-vault" }
    }
  }
}
```

暴露的工具：`search_vault(query, limit)`、`read_kb_note(path)`、`list_recent_notes(limit)`。
内置路径穿越防护，只能读 `VAULT_DIR` 范围内的笔记。

---

> 以下均为**可选的第三方/外部工具**，不随本仓库提供。路径（如 `~/graphrag-poc/`、
> `~/.hermes/...`）是作者本机的示例位置，请替换为你自己的安装路径。没有它们也不影响
> 第 1、2 节的核心流程与 `scripts/vault_health_check.py`。

### 知识库三件套

| 工具 | 定位 | 适用场景 |
|:----|:----|:---------|
| **GBrain** | 搜索 | 知道要找什么关键词 |
| **GraphRAG** | 发现 | 不知道关键词，想发现隐藏关联 |
| **LLM Wiki** | 写作 | 用 Karpathy 模式建 LLM 可读的 Wiki |
| **Understand-Anything** | 可视化 | 看懂全库结构，发现隐性关联 |

### GBrain 搜索集成

**日常使用**：
```bash
alias gs='GBRAIN_SKIP_RECIPES=1 gbrain search'
gs "定价 品牌"
gs "奥德赛时期"

# 混合搜索
gbrain query "消费者心理剩余"

# 读全文（注意 slug 含 emoji 目录名）
gbrain get "wiki/📡 外部输入/播客/XXX/观点提取"

# 查看统计
gbrain stats
```

**配置**：DeepSeek downstream LLM（`deepseek_api_key` + `deepseek_model: deepseek-chat` + `search.mode: balanced`）
**完整手册**：`wiki/🧠 AI系统/GBrain-完整操作手册.md`

### GraphRAG 发现

> **⚠️ 已移至独立项目**：按你的实际安装路径配置
> **Flask API**：localhost:8999（默认）
> **内容**：自定义知识库 + DeepSeek + BGE 嵌入

用于发现知识库中的隐性关联和跨领域连接。

### LLM Wiki（Karpathy 模式）

Karpathy 的 LLM Wiki 模式：构建 interlinked markdown 知识库，让 LLM 在推理时直接查。
已集成到 Obsidian vault。

### Understand-Anything — 知识图谱可视化

已安装为独立 skill。

**使用**：
```bash
# 必须指向 wiki 根目录，必须用 python3.11+
python3 parse-knowledge-base.py /path/to/your-vault/wiki
```

**⚠️ 关键 pitfalls**：
- Python 3.11+ 必需
- 必须指向 wiki 根目录（子目录没有 index.md 会报错）
- Dashboard 需先 build core 包
- 需要 GRAPH_DIR 和 ACCESS_TOKEN 环境变量

---

## 4. 目录整理 (Organization)

### 目录审查与增量清理

当用户说"看一下目录是否合理"时执行：

```
Step 1: 全量目录扫描
  → find . -maxdepth 3 -type d | sort
  → 对每个 wiki 子目录统计 .md 文件数

Step 2: 逐项检查
  | 检查项 | 特征 | 严重性 |
  |--------|------|--------|
  | 旧版残留目录 | diff -rq 确认新旧版本内容不同 | 🔴 |
  | Legacy redirect 只剩 README | 目录只有一个 redirect 文件 | 🟡 |
  | 概念卡片散落根目录 | wiki/🧬 知识图谱/XXX.md 应在概念/下 | 🟡 |
  | cron 脚本写入旧路径 | grep -rn "旧目录" ~/.hermes/scripts/ | 🔴 |

Step 3: 分类执行 → 归档/删除/移动/更新引用

Step 4: 验证 → 零残留
```

### 全库审计与批量归档

```
Step 1: 全量扫描目录结构和文件数
Step 2: 逐目录与最新管理办法对照
Step 3: 分级标记（🔴明确无用 → 🟡重复 → 🟠草稿 → 🔵过时）
Step 4: 批量 mv 到 wiki/🗄️ 归档/
Step 5: 修复残留引用（README/wiki/index/项目索引）
```

**归档目录结构**：
```
wiki/🗄️ 归档/
├── 归档清单-YYYY-MM-DD.md
├── 旧版管理办法/
├── 旧版流程/
├── 旧版草稿/
├── 旧选题/
└── ...
```

**反模式**：
- ❌ 不要删除归档目录下的文件
- ❌ 归档后必须同步更新所有 index/README 引用
- ❌ 素材库/ 下的文件不归档
- ❌ 归档时不要改文件名
- ✅ 每次大清理必须创建 `归档清单-YYYY-MM-DD.md`

---

## 5. Wiki 实体管理

### Wiki 实体格式

每个团队/项目在 `wiki/teams/` 下有对应 `.md` 实体：

```yaml
---
title: 团队名
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity
tags: [team, ...]
sources: [50.团队/实际目录名]   # 重要：路径必须是实际存在的目录名
---

# 团队名

## Overview
## 文件结构（表格，列出子目录和数量）
## Related
```

**sources 路径必须与实际目录名完全匹配**：
- ❌ `sources: [50.团队/02.事业线]` （旧/错）
- ✅ `sources: [50.团队/事业线]` （新/对）

### 异常文件处理

某些 `.md` 文件可能被误认为目录名（如 `千金-日报索引.md`、`OKR看板.md`）。检查方式：

```python
# 检查是否是文件被当作目录
for d in team_dir.iterdir():
    if d.is_file() and not d.name.startswith("."):
        print(f"⚠️ {d.name} 是文件却像目录")
```

修复：用 `mv` 把它们移到对应目录下。

---

## 6. 批量修复模式

### broken wikilink 修复（播客 EP 文件）

**问题**：播客 wiki 文件中的 wikilink 引用素材库 EP 文件，因文件名含特殊字符（引号、emoji、反斜杠）导致相对路径解析失败。

**修复方式**：
```python
# 1. 建索引: EP编号 → 实际文件路径
ep_index = {}
for f in 素材库_dir.iterdir():
    ep_match = re.match(r'(EP\d+)', f.name)
    if ep_match:
        ep_index[ep_match.group(1)] = f

# 2. 扫描 wiki 文件，用 EP 编号匹配实际文件，重建相对路径
for link in wikilinks:
    ep_match = re.search(r'(EP\d+)', target)
    if ep_match and ep_match.group(1) in ep_index:
        rel = os.path.relpath(ep_index[ep_id], md.parent)
        # 替换 wikilink
```

### 批量补 frontmatter（summary + source）

**问题**：大量 A+B 产物（观点提取/问题链）缺少 summary 和 source 字段。

**修复方式**：
```python
# summary: 从正文第一个 # 标题提取
title_match = re.search(r'^#\s+(.+)', body, re.MULTILINE)
summary = title_match.group(1).strip()[:100] if title_match else md.stem

# source: 从文件路径推断
if '观点提取' in md.name or '问题链' in md.name:
    source = '素材库/播客/给女孩的商业第一课'
```

**⚠️ PITFALL**：GraphRAG 自动生成的实体文件（`🧬 知识图谱/GraphRAG*/实体/`）约 260+ 个没有 summary，这是正常的，不需要修复。

### 文件名含空格修复

```bash
# 扫描
find wiki/ -name "* *" -type f

# 重命名
mv "MarkItDown 操作手册.md" "MarkItDown-操作手册.md"
```

### 目录迁移提示页格式

当目录整体迁移时，旧位置保留 README.md 提示页：
```yaml
---
title: "⚠️ 已迁移 - 目录名"
type: note
tags: [已废弃, 已迁移]
created: YYYY-MM-DD
summary: 已迁移到 ../../新位置。
source: "原系统名"
---
```

---

## 7. 事业线文件命名规范

事业线（`50.团队/事业线/`）的文件命名与 Agent 的对应关系：

| 文件名前缀 | Agent | 应放入子目录 |
|-----------|-------|-------------|
| `O1-猎手` / `猎手-内容情报` / `猎手-渠道情报` / `猎手-技术调研` / **`内容情报-给女孩的商业第一课`** | 猎手 | `猎手/` |
| `O2-笔神` | 笔神 | `笔神/` |
| `O2-天眼` | 天眼 | `天眼/` |
| `O3-管家` | 管家 | `管家/` |
| `O4-极客` | 极客 | `极客/` |
| `O4-画神` | 画神 | `画神/` |
| `千金-` | 千金 | `千金/` |

**特别注意**：`内容情报-给女孩的商业第一课-*.md` 这些文件名（87个）不是系列名，是猎手的产出，需归入 `猎手/` 目录。

**O3-CFO 文件**：属于 `家庭线/CFO/`，不是事业线。

---

## 8. 千金日报文件命名规范

| 文件名包含 | 子目录 |
|-----------|-------|
| `总裁日报` | `总裁日报/` |
| `O1线`/`O2线`/`O3线`/`O4线` | `O线日报/` |
| `晨间简报` | `晨间简报/` |
| `浪漫-` | `浪漫/` |
| `系统-` | `系统/` |
| 其他 | `其他/` |

---

## 反模式

- ❌ 不要删除素材库/ 下的任何文件
- ❌ Wiki 页面必须有 source 字段指向原始素材
- ❌ 不要创建没有入链的孤立 wiki 页面（除索引页）
- ❌ 清理前先 dry-run
- ❌ 归档时不要改文件名
- ✅ 每次大清理必须创建 `归档清单-YYYY-MM-DD.md`

---

## 相关 Skill

- `kb-ingest` — 素材入库（详细流程）
- `kb-audit` — 健康检查与清理（详细流程）
- `kb-tools` — GBrain/GraphRAG/LLM Wiki 集成（详细配置）
- `chubby-knowledge-base-organization` — 团队文件组织规范
- `content-ab-processing` — A+B 双轨处理
- `memory-obsidian-sync` — Memory 同步到 Obsidian
- `understand` / `understand-knowledge` — 知识图谱可视化
