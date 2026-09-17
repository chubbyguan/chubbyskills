# Quickstart Checklist

`quickstart` 用于离线环境和样例验收，不计为真实平台采集成功。处理自己的素材请接着走[创作者工作流](./creator-workflow.md)。

## 离线自检

```bash
python3 tools/chubby.py quickstart
```

检查内容：

- 初始化 `chubby.yaml`、队列、状态和报告目录。
- 对一条 X 链接做 dry-run，确认平台识别和命令编排。
- 校验 `examples/outputs` 的基础 frontmatter 和 schema v1。
- 校验平台和站点模板定义。
- 为样例建立临时 SQLite 索引，执行关键词与 semantic-lite 检索。
- 检查兼容 MCP SDK 是否可导入；未安装时给 warning，不影响 CLI。

报告写入 `.chubby/quickstart.md`。需要真实 MCP 启动和协议调用检查时：

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

CI 或临时验证可使用独立环境：

```bash
python3 tools/chubby.py quickstart --ephemeral --no-state
```

## 配置知识库并运行完整流程

```bash
CHUBBY_VAULT="$HOME/Documents/creator-vault"
python3 tools/chubby.py init --vault "$CHUBBY_VAULT"
python3 tools/chubby.py doctor --platform youtube
python3 tools/chubby.py ingest "替换为真实素材链接" --no-enrich
python3 tools/chubby.py search "素材中的关键词"
python3 tools/chubby.py brief --topic "素材中的主题" \
  --output "$CHUBBY_VAULT/30_Output/brief.md"
python3 tools/chubby.py status --latest
```

把平台和素材替换为自己的内容。`init --vault` 使用知识库根目录，采集进入 `00_Inbox`，索引位于 `.chubby/index.sqlite`。采集成功后和统一查询前自动增量同步；未变化的向量保留。

`brief` 输出逐字原文、来源和真实行号，并写入 Markdown/JSON。将资料包交给现有 Agent 生成选题，仍需核对引用上下文；工具不认证原文事实。

独立 `vault_index.py` 不读取 `chubby.yaml`。如需使用，先 `export VAULT_DIR="$CHUBBY_VAULT"`，或对各命令显式传入同一个 `--db`。迁移和重建说明见[知识库自动化](./knowledge-automation.md#索引路径与迁移)。

连接 Agent：

```bash
VAULT_DIR="$CHUBBY_VAULT" python3 knowledge-base-management/scripts/mcp_server.py
```

MCP 的搜索、语义检索、最近笔记和统计都先自动同步索引；配置方式见 [MCP Workflow](./mcp-workflow.md)。
