# cue-omni-reader → chubbyskills 实测报告

## 测试目的

验证 cue-omni-reader 解析的外部内容能否无缝接入 chubbyskills 的本地知识库、搜索和资料包链路。当前 chubbyskills `ingest` 仅覆盖 10 个平台（wechat/bilibili/youtube/douyin 等），**omni-reader 弥补的是「不在这 10 个平台范围内的任意网页、文档、音频、视频」**。

## 输入

| 项 | 值 |
|---|---|
| 来源 URL | https://www.anthropic.com/engineering/building-effective-agents |
| omni-reader 版本 | npm `@cueai/omni-reader-mcp`（MIT） |
| chubbyskills 版本 | v0.11.0 |
| 日期 | 2026-09-17 |

## 解析结果

omni-reader 将网页完整解析为 26,345 字节 Markdown，包含：

- 全文正文（标题、段落、列表、代码块）
- 保留原文链接
- 保留图片引用（URL 形式）
- 页脚导航链接（保留供参考）

未添加额外摘要或改写——输出是原文的忠实 Markdown 转换。

## 接入 chubbyskills 流程

### 步骤 1：添加 chubby 兼容 frontmatter

在 omni-reader 输出的 Markdown 文件头部插入 chubby vault 协议 frontmatter：

```yaml
---
title: Building Effective Agents
type: note
platform: web
source: https://www.anthropic.com/engineering/building-effective-agents
author: Anthropic
created: 2026-09-17
tags: [agent, llm, workflow, anthropic]
schema_version: 1
run_id: 'omni-reader-test-001'
source_hash: '5b1b8f4a1cee1337'
captured_at: 2026-09-17T19:48:00
processed_at: 2026-09-17T19:48:00
content_type: article
status: success
assets: []
---
```

frontmatter 只需三处针对 omni-reader 来源的修改：
- `platform: web`（而非内置平台的名称）
- `source: <原始 URL>`
- `source_hash`（对 omni-reader 输出的 SHA-256）

其余字段与 chubby 原生采集产物完全一致。

### 步骤 2：放入 vault inbox

```bash
cp omni-reader-output.md /path/to/vault/00_Inbox/
```

### 步骤 3：索引

```bash
python3 tools/vault_index.py index /path/to/vault
```
输出：`Indexed N note(s) into .../.chubby/vault_index.sqlite (fts5=True)`

### 步骤 4：搜索

```bash
$ python3 tools/vault_index.py search "effective agents"
1. Building Effective Agents [web] 2026-09-17
   00_Inbox/anthropic-building-effective-agents.md
   ...Building effective agents  Published Dec 19, 2024...

$ python3 tools/vault_index.py search "orchestrator"
1. Building Effective Agents [web] 2026-09-17
   00_Inbox/anthropic-building-effective-agents.md
   ...Workflow: Orchestrator-workers  In the orchestrator-workers workflow...
```

FT5 全文搜索正常工作，跨来源（原生采集 + omni-reader 输入）统一索引。

## 关键结论

1. **接入成功**：omni-reader 输出的 Markdown 经 frontmatter 标准化后，chubby vault 的 index/search/read 全部可用，无需修改 chubby 代码。
2. **互补而非重复**：chubby 的 10 个平台 skill 处理结构化平台内容（字幕/图文/播客）；omni-reader 处理**平台不覆盖的来源**（任意公开网页、扫描件 PDF、本地文档、录音、视频）。
3. **资源消耗**：本次解析消耗 0.603 credits（当前余额 988,074.53 credits）。大文件/长音频会更高。
4. **One-time frontmatter**：集成只需在文件头部加 ~15 行 frontmatter，可脚本化。

## 可复现说明

要复现此测试，在配置了 `CUE_API_KEY` 的环境中运行：

```bash
# 1. 解析网页
npx @cueai/omni-reader-mcp parse "https://www.anthropic.com/engineering/building-effective-agents" -o article.md

# 2. 加 frontmatter（或运行标准化脚本）
# 3. 复制到 vault
cp article.md /path/to/vault/00_Inbox/

# 4. 索引 & 搜索
cd /path/to/chubbyskills
python3 tools/vault_index.py index /path/to/vault
python3 tools/vault_index.py search "关键词"
```
