# Quickstart Checklist

这个入口用于离线环境和样例验收，不计为真实平台采集成功。首次处理自己的素材请从[创作者工作流](creator-workflow.md)开始。

推荐入口：

```bash
python3 tools/chubby.py quickstart
```

这条命令会完成这些检查：

- 初始化 `chubby.yaml`、队列、状态和报告目录。
- 对一条 X 链接跑 dry-run，确认自动平台识别和命令编排可用。
- 校验 `examples/outputs` 的基础 frontmatter 和 schema v1。
- 校验 `platforms/*.yaml` 与 `templates/sites/*.yaml` 的平台定义。
- 对 `examples/outputs` 建立临时 SQLite 索引，并执行关键词与 semantic-lite 示例搜索。
- 检查兼容 MCP SDK 是否可导入；未安装只给 warning，不影响 CLI。真实启动和协议调用另用 `python3 tools/mcp_smoke.py --json` 验收。

运行结束后会生成：

```text
.chubby/quickstart.md
```

如果要在 CI 或本地临时验证中避免写入仓库运行状态：

```bash
python3 tools/chubby.py quickstart --ephemeral --no-state
```

通过 quickstart 后，再替换成真实链接：

```bash
python3 tools/chubby.py ingest "https://x.com/user/status/123" --dry-run
python3 tools/chubby.py ingest "https://x.com/user/status/123"
python3 tools/chubby.py status --latest
python3 tools/vault_index.py index /path/to/your-vault
VAULT_DIR=/path/to/your-vault python3 knowledge-base-management/scripts/mcp_server.py
```

MCP 可选依赖：`python3 -m pip install -r knowledge-base-management/requirements-mcp.txt`。默认索引与检索不需要该依赖。
