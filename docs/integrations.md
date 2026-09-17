# 可选外部集成

外部工具可以承担本仓库尚未覆盖的解析工作，导出 Markdown 后接入[本地文档导入](./document-import.md)。这份目录记录接入条件和验证范围，不把外部工具列为 chubbyskills 的必需依赖。

| 入口 | 适用范围 | 当前验证状态 |
|---|---|---|
| 本仓库 `chubby import` | 已有 Markdown、TXT、带文字层的 PDF | 本地转换、入库、搜索与资料包可独立验收 |
| [Atlas / MuAPI 可选转录](./cloud-transcription.md) | 明确选择云端处理的播客音频 | experimental；离线测试覆盖，未完成真实付费服务验收 |
| [cue-omni-reader](https://github.com/sensedeal/cue-skills/tree/main/cue-omni-reader) | 上游声明支持网页和已授权的本地文档、音频、视频解析 | 仅核对上游文档；本项目未执行真实解析，保留待验证 |

## cue-omni-reader 的接入边界

来源是 [PR #6](https://github.com/chubbyguan/chubbyskills/pull/6)。提交者 [huhoo](https://github.com/huhoo) 已披露自己是上游维护者。该 PR 提供的是外部工具入口建议；本项目没有原样合入 README 推荐段落。

根据 2026-09-17 核对的[上游 skill](https://github.com/sensedeal/cue-skills/blob/main/cue-omni-reader/SKILL.md) 和[安装说明](https://github.com/sensedeal/cue-skills/blob/main/cue-omni-reader/references/setup.md)，接入需要 Node.js、Omni MCP Bridge 及 `CUE_API_KEY`。仅注册 skill 不能完成解析服务配置。本地文件依赖 Bridge 的目录授权；远程连接本身不能读取本机文件。请依照上游当前安装说明选择版本和配置凭据。

解析可能向外部服务上传来源内容并产生费用。MIT 是工具代码的许可证，不代表托管解析免费。上传范围、账号权限、任务费用和数据清理由上游服务决定。本项目不安装 Bridge、不代管其密钥、不扩大授权目录，也不承诺取消或重试能避免费用。

如已在自己的 Agent 中配置并授权该服务，应先让它完成原始任务，再把**完整 Markdown 结果**保存为本地文件。不要把任务状态 JSON 或预览片段当作完整正文。遇到异步任务先保存并恢复已有 operation，避免把轮询失败当成需要重新解析。

## 从外部结果交接到本项目

外部工具完成导出后，以下步骤全部使用本仓库命令：

```bash
CHUBBY_VAULT="$HOME/Documents/creator-vault"
python3 tools/chubby.py init --vault "$CHUBBY_VAULT"
python3 tools/chubby.py import "/你的导出目录/report.md" \
  --source-url "https://example.org/original-report" --no-enrich
python3 tools/chubby.py search "报告中的关键词"
python3 tools/chubby.py brief --topic "报告中的主题" \
  --output "$CHUBBY_VAULT/30_Output/report-brief.md"
```

将文件、原始来源地址和关键词替换为实际值。本地文件没有公开来源时省略 `--source-url`。相对附件需一并放在 Markdown 所在目录内；导入器会检查引用并复制附件。

可直接运行的人工样本文档位于[本地导入示例](./document-import.md#可独立复现的本地示例)。这条交接链路与上游服务无关；跑通它不会把 cue-omni-reader 的真实解析状态从“待验证”改为“已验证”。

## 何时更新验证状态

一条真实集成记录至少应包含：输入类型与可公开样本、使用的上游版本、实际上传范围、完整 Markdown 与附件、来源映射、索引查询和资料包的回查结果。涉及费用时记录服务实际返回的结果，不推测价格或免费额度。在这些证据补齐前，PR #6 保留为可选集成需求。
