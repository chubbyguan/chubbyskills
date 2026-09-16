# v0.11.1 — 安装可移植、MCP 可启动、采集结果可核验

这一版修复新用户从安装到使用时遇到的断点。

- **独立技能安装**：新增 `tools/install_skill.py`，14 个技能的安装产物包含所需公共源码，可单独搬迁；同名目录不覆盖。`setup.sh` 负责运行依赖，并支持完整技能名。
- **技能格式兼容**：14 个 `SKILL.md` 的扩展字段统一放入标准 `metadata`，增加格式回归检查。
- **MCP 恢复可用**：可选 SDK 固定为 `mcp==1.30.0`。真实 stdio 验收覆盖初始化、6 个工具、搜索和原文读取；缺包或不兼容时提供明确安装提示。
- **Markdown 保真**：标题、作者中的冒号、引号、换行和控制字符安全写入 frontmatter，列表和布尔值保留类型，索引正确读取转义内容。
- **采集结果验收**：修复 YouTube 空标题；子进程退出成功但产物缺失或元数据不合格时，管线记录为失败。错误摘要保留真正的失败原因。
- **实测证据**：live 检查可选平台并保留时间、日志、输出 hash；未测与失败明确分开。Linux/macOS CI 验证离线流程，手动 workflow 另验真实图文/字幕路径。
- **创作者入口**：中英 README 改为“素材到可引用选题”的工作流，删除未经证实的比较结论，并补充十位用户试用表和社区贡献处理记录。

## 安装

```bash
git clone --branch v0.11.1 https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/install_skill.py bilibili-transcribe --dest ~/.codex/skills
```

按[安装文档](installation.md)配置运行依赖。发布资产 `chubbyskills-0.11.1-skills.tar.gz` 内含可独立移动的 14 个技能目录；解压到新的目录检查后，只复制需要的技能，保留已有定制。

## 验证与边界

[发布检查](release.md)列出可复现命令；[真实平台记录](live-verification.md)列出本次来源、结果和失败原因。一次样本通过不能代表整个平台稳定，离线样例不能代替真实采集，协议冒烟测试也不等于完整 MCP 一致性认证。十位创作者试用尚待真实参与者，不计为本次已完成验证。

安装职责和路由的改进参考了 [PR #1](https://github.com/chubbyguan/chubbyskills/pull/1) 提出的问题；MCP 修复回应 [Issue #4](https://github.com/chubbyguan/chubbyskills/issues/4)。第三方云转录 PR 未在本版合入。
