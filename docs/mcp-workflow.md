# MCP Workflow

`knowledge-base-management/scripts/mcp_server.py` 把本地 vault 暴露成 Agent 可调用工具：搜索、语义检索、读取笔记、最近笔记、重建索引和统计。

## 安装与真实 MCP 验收

使用 Python 3.10 或更新版本，在完整仓库根目录运行：

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

可选依赖固定为 `mcp==1.30.0`；2.x 已移除当前入口使用的 `mcp.server.fastmcp`，需要迁移后才能升级。运行 Agent 时应使用安装该依赖的同一个 Python 环境。

验收脚本通过官方 MCP 客户端启动真实 `mcp_server.py` 子进程，依次验证 `initialize`、`tools/list` 返回全部 6 个工具、`search_vault` 命中临时笔记和 `read_kb_note` 返回原文。测试 vault 和索引均创建在临时目录并自动清理，不读取你的 `VAULT_DIR`。默认总超时 20 秒，可用 `--timeout` 调整；失败退出非零。这个测试覆盖服务启动和基本检索链路，不代表完整 MCP 协议一致性测试。

独立安装知识库 skill 时，在仓库端运行安装器后启动安装目录中的入口：

```bash
python3 tools/install_skill.py knowledge-base-management --dest ~/.codex/skills
VAULT_DIR=/path/to/your-vault python3 ~/.codex/skills/knowledge-base-management/scripts/mcp_server.py
```

安装器包含 `tools/vault_index.py` 和 `tools/vault_curator.py`；MCP 入口优先加载 skill 内的工具，不依赖原仓库位置。

## 本地业务流程 Demo

```bash
python3 tools/mcp_workflow_demo.py
```

这个 demo 直接调用 Python 业务函数，使用 `fixtures/mcp-vault` 展示以下流程；它不建立 MCP 连接，不能代替上面的 stdio 验收：

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
