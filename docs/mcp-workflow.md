# MCP Workflow

`knowledge-base-management/scripts/mcp_server.py` 把本地知识库暴露成 6 个 Agent 工具：关键词搜索、语义检索、读取笔记、最近笔记、增量索引和统计。

## 安装与真实协议验收

使用 Python 3.10 或更新版本，在完整仓库根目录运行：

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

当前验证的可选 SDK 为 `mcp==1.30.0`。运行 Agent 时，使用安装了该依赖的同一个 Python 环境；更换 SDK 版本后重新执行协议验收。

验收脚本通过官方 MCP 客户端启动真实 server 子进程，验证 `initialize`、6 个工具的发现、`search_vault` 命中临时笔记，以及 `read_kb_note` 返回原文。临时 vault 和索引自动清理，不读取你的 `VAULT_DIR`。默认总超时 20 秒，可用 `--timeout` 调整；失败退出非零。这项检查不证明真实平台采集成功，也不代替目标客户端中的连接检查。

独立安装知识库 skill：

```bash
python3 tools/install_skill.py knowledge-base-management --dest ~/.codex/skills
python3 -m pip install -r ~/.codex/skills/knowledge-base-management/requirements-mcp.txt
VAULT_DIR=/path/to/your-vault python3 ~/.codex/skills/knowledge-base-management/scripts/mcp_server.py
```

安装器包含 `tools/vault_index.py`、`tools/vault_curator.py` 和 `tools/evidence_brief.py`。MCP 优先加载 skill 内的工具，安装后不依赖原仓库位置。目标技能目录必须不存在；已有安装先备份，再使用新的安装目录。

## 客户端配置

`VAULT_DIR` 指向知识库根目录，与 `chubby.py init --vault` 使用相同路径：

```json
{
  "mcpServers": {
    "chubby-kb": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/knowledge-base-management/scripts/mcp_server.py"],
      "env": {
        "VAULT_DIR": "/path/to/your-vault"
      }
    }
  }
}
```

默认数据库为 `$VAULT_DIR/.chubby/index.sqlite`。如需覆盖，在 `env` 中显式设置 `VAULT_INDEX_DB`；CLI 也应使用同一个数据库路径。

## 索引如何更新

| 工具 | 行为 |
|---|---|
| `search_vault` | 先增量同步，再做关键词搜索 |
| `semantic_search_vault` | 先增量同步，再按所选 provider 检索 |
| `list_recent_notes` | 先增量同步，再列最近笔记 |
| `vault_index_stats` | 先增量同步，再返回统计 |
| `read_kb_note` | 直接读取知识库范围内的指定文件 |
| `reindex_vault` | 名称保持不变，执行增量同步并保留未变化的向量 |

同一个 MCP 会话中，新建、修改或删除笔记后再次查询即可反映变化。扫描或读取失败时，同步不会把未读到的笔记误删。数据库绑定到知识库路径，不能静默切换到另一知识库。

需要完整重建并丢弃现有向量时，从命令行显式执行：

```bash
python3 tools/vault_index.py index /path/to/your-vault --rebuild
```

如果 MCP 使用 `VAULT_INDEX_DB`，重建时也要设置该环境变量，或在子命令前使用 `--db /path/to/index.sqlite`。旧版默认的 `$VAULT_DIR/.chubby/vault_index.sqlite` 会在新默认索引尚不存在时复制迁移；原数据库保留。仓库根目录或其他位置的旧数据库不会自动猜测所属知识库，参见[迁移说明](./knowledge-automation.md#索引路径与迁移)。

## 检索和资料包

默认语义检索为零依赖 `semantic-lite`。需要真实 embedding 时，先按[知识库自动化](./knowledge-automation.md#可选-embedding)生成向量，再设置 `CHUBBY_EMBEDDING_PROVIDER` 和对应模型、凭据。

可以这样约束 Agent：

```text
先用 chubby-kb 的 search_vault / semantic_search_vault 检索；
再用 read_kb_note 读取相关原文和上下文；
回答时注明笔记相对路径、原始 source，并区分原文观点与推断。
```

逐字摘录、真实行号和文件摘要由 CLI 资料包工具提供；它没有新增第 7 个 MCP 工具：

```bash
python3 tools/chubby.py brief --topic "内容策略" --output reports/content-brief.md
# 独立安装后也能使用：
python3 ~/.codex/skills/knowledge-base-management/tools/evidence_brief.py \
  --vault /path/to/your-vault --topic "内容策略" --output reports/content-brief.md
```

`brief` 输出原文证据包和 Agent 任务说明，选题由 Agent 另行生成；文件和摘录核验不等于事实认证。

## 本地业务函数 Demo

```bash
python3 tools/mcp_workflow_demo.py
```

这个 demo 直接调用 Python 业务函数，用 `fixtures/mcp-vault` 演示索引、检索、读取和带来源路径的回答。它不建立 MCP 连接，不能代替前面的 stdio 验收。
