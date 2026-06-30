# MCP Workflow

`knowledge-base-management/scripts/mcp_server.py` 把本地 vault 暴露成 Agent 可调用工具：搜索、语义检索、读取笔记、最近笔记、重建索引和统计。

## Demo

```bash
python3 tools/mcp_workflow_demo.py
```

这个 demo 使用 `fixtures/mcp-vault` 执行一个完整任务：

1. 重建 vault 索引。
2. 用 `semantic_search` 找到相关笔记。
3. 用 `read_note` 读取原文。
4. 生成带来源路径的回答。

## Agent Prompt Pattern

给支持 MCP 的 Agent 下任务时，可以使用这个约束：

```text
先用 chubby-kb 的 semantic_search_vault 检索相关笔记；
再 read_kb_note 读取最相关的 1-3 篇；
最后回答时必须引用 vault 中的相对路径。
```

## MCP Config

```json
{
  "mcpServers": {
    "chubby-kb": {
      "command": "python3",
      "args": ["knowledge-base-management/scripts/mcp_server.py"],
      "env": {
        "VAULT_DIR": "/path/to/your-vault"
      }
    }
  }
}
```

默认语义检索使用零依赖 `semantic-lite`。如果已经建立真实 embedding，可以让 MCP 走 provider：

```bash
export CHUBBY_EMBEDDING_PROVIDER=openai
export OPENAI_API_KEY='...'
VAULT_DIR=/path/to/vault python3 knowledge-base-management/scripts/mcp_server.py
```
