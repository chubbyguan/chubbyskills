# v0.12.0 — 重复采集可复用，素材入库即可搜索

保存素材后可直接搜索并导出带出处的资料包，无需手动串联多个索引命令。

- **统一入口**：`init --vault` 配置知识库，`search` 检索素材，`brief` 导出 Markdown/JSON 原文资料包。`doctor --platform` 区分必需依赖与可选组件。
- **增量索引**：采集入库与 MCP 查询同步新增、修改和删除的笔记；保留未变化的向量，显式 `--rebuild` 才重建。数据库绑定知识库，避免串库。
- **安全复用**：规范化已知平台来源，相同任务复用有效产物；刷新保留旧版本，同名不同来源分别保存。缺失附件、参数或本地输入变化会重新采集。
- **可恢复重试**：保留原任务输出位置、知识库与处理参数，允许显式覆盖；状态和报告脱敏常见凭据。
- **可回查资料包**：来源链接、原文行号、逐字摘录和 SHA-256 一起导出；生成结果不会进入后续 brief 的证据候选，普通笔记不能被 `--force` 覆盖。
- **独立安装**：知识库技能包含资料包导出工具，支持搬离仓库后使用。

## 安装与升级

```bash
git clone --branch v0.12.0 https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/install_skill.py knowledge-base-management --dest ~/.codex/skills
```

安装器保留已有同名目录，升级前将新版本安装到另一目录核对定制。[0.12 升级说明](iteration-0.12.0.md)记录索引迁移、参数语义和复用规则；[创作者工作流](creator-workflow.md)给出完整命令。

发布资产 `chubbyskills-0.12.0-skills.tar.gz` 包含 14 个可独立移动的技能目录。Python、系统包和可选 MCP SDK 仍需按[安装文档](installation.md)配置。

## 验证边界

本地 167 项测试通过，Ruff 与语法检查通过；真实 MCP stdio 完成初始化、工具列表、搜索与原文读取。发布包解压后验证 14 个技能目录、21 个脚本隔离导入，以及独立知识库 MCP 和 Python 3.9 资料包导出。

[发布检查](release.md)覆盖本地测试、真实 MCP stdio 交互、CLI 流程、便携包和 Linux/macOS CI。本轮 CLI 验收中的正文导入明确标记为人工 fallback；没有将离线样例计为新的平台自动抓取记录。

资料包只核验摘录与本地文件相符，不证明事实正确。默认检索和资料包导出在本地执行；本轮没有调用付费模型。增量同步仍需扫描 Markdown，大库性能与后台监听留待后续优化。
