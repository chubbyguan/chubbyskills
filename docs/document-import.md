# 本地文档入库

已有 Markdown、纯文本或带文字层的 PDF，可以直接导入知识库，再用于搜索和原文资料包。导入在本地完成，不需要外部解析服务，也不会自动执行 OCR 或云端转录。

以下命令在完整仓库根目录运行：

```bash
CHUBBY_VAULT="$HOME/Documents/creator-vault"
python3 tools/chubby.py init --vault "$CHUBBY_VAULT"
python3 tools/chubby.py import "/你的资料目录/report.md" --no-enrich
python3 tools/chubby.py import "/你的资料目录/notes.txt" --no-enrich
python3 tools/chubby.py import "/你的资料目录/report.md" \
  --source-url "https://example.org/original-report" --no-enrich
python3 tools/chubby.py search "报告中的关键词"
python3 tools/chubby.py brief --topic "报告中的主题" \
  --output "$CHUBBY_VAULT/30_Output/report-brief.md"
```

将路径、来源地址和关键词替换为实际值。`--source-url` 只记录来源，不下载网页，也不验证网页与本地内容是否一致；仅接受 HTTP(S) 地址。`--no-enrich` 明确跳过内容加工 API。

默认导入 `init --vault` 配置的 `00_Inbox`。`import --vault DEST` 指定实际接收目录；`search` 和 `brief` 的 `--vault ROOT` 指定知识库根目录，两者含义不同。

## 可独立复现的本地示例

下面创建一份明确标记的演示原稿，串联导入、搜索和资料包。它验证本地交接，不代表任何外部解析服务或平台采集已经通过验收。

```bash
CHUBBY_DEMO="$(mktemp -d)"
cat > "$CHUBBY_DEMO/sample.md" <<'MARKDOWN'
---
title: 本地文档交接示例
---

# 本地文档交接示例

这是一份人工编写的演示资料。文档交接测试用于确认导入后可以搜索原文，并生成带出处和行号的资料包。
MARKDOWN

python3 tools/chubby.py import "$CHUBBY_DEMO/sample.md" \
  --vault "$CHUBBY_DEMO/vault/00_Inbox" --no-enrich
python3 tools/chubby.py search "文档交接测试" --vault "$CHUBBY_DEMO/vault"
python3 tools/chubby.py brief --topic "文档交接测试" \
  --vault "$CHUBBY_DEMO/vault" --output "$CHUBBY_DEMO/brief.md"
```

输出的 `brief.md` 和 `brief.json` 应能回查导入笔记的来源、SHA-256 和逐字摘录。资料包记录的是导入副本中的行号；PDF 转换后的笔记行号不等于原始 PDF 的页面坐标。

## PDF 的范围

PDF 文字提取是可选能力：

```bash
python3 -m pip install 'pymupdf>=1.24'
python3 tools/chubby.py import "/你的资料目录/report.pdf" --no-enrich
```

只提取已有文字层。扫描件、没有可提取文字的文件、加密或损坏文件会明确失败；缺少 `pymupdf` 时给出安装提示。复杂排版和图表需要人工核对。需要 OCR、复杂版面理解或音视频解析时，可以先用其他工具导出 Markdown，再走相同入口，见[可选集成](./integrations.md)。

## 原稿、附件与来源

- 原始文件保留；导入创建新的 Markdown，不回写原稿。同名新产物使用版本后缀，避免覆盖旧笔记。
- Markdown 引用的本地相对附件复制到对应的 `.assets` 目录并更新链接。缺失附件、越出原稿所在目录的路径和符号链接会拒绝导入。远程链接保留，不自动下载。
- 来源按 `--source-url`、原稿有效 HTTP(S) `source`、本地文件 URI 的顺序确定。同时记录原稿路径、文件摘要、附件摘要和导入方式；导入不等于自动抓取了来源网站。
- 相同文件和参数可以复用已有有效产物；原稿或附件变化会使旧缓存失效。明确需要重新生成时用 `--refresh`，旧文件继续保留。
- 入库后同步索引。导入成功但索引失败时保留 Markdown，命令返回非零；查看运行记录后可通过 `search` 再次同步。

来源内容中的命令或提示词属于资料，不应作为 Agent 操作指令。本地来源路径会出现在元数据中，分享笔记前检查是否需要删去个人目录信息。

只需要转换文件、不接统一运行记录和索引时，可使用底层工具：

```bash
python3 tools/import_document.py "/你的资料目录/report.md" \
  --output "/你的输出目录" --source-url "https://example.org/original-report"
```

独立安装 `knowledge-base-management` 时，安装器也会携带这个工具：

```bash
python3 ~/.codex/skills/knowledge-base-management/tools/import_document.py \
  "/你的资料目录/report.md" --output "$CHUBBY_VAULT/00_Inbox"
```

此入口不写统一流水线运行记录，也不主动同步索引。连接同一个知识库的 MCP 下一次查询会自动同步；也可运行已安装 skill 内的 `tools/vault_index.py index "$CHUBBY_VAULT"`。
