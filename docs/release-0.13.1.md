# v0.13.1 — 社区反馈修复与首次跑通体验

这次迭代以社区反馈为主线：外部用户报告的 X 长文章采集缺口已修复并补了全文抓取通道，同时降低了新用户的首次跑通门槛。

- **X 长文章全文**：syndication 端点对 Article 只返回预览，此前仅静默标注。现在检测到预览时 stderr 明确告警；提供 `--cookies` / `X_COOKIES`（自己账号的 auth_token + ct0）后，通过登录态 GraphQL 抓取全文，失败时告警回退为预览。`platforms/x.yaml` 新增 `article_preview_only` 失败模式。
- **输出校验修复**：文件名超过文件系统限制的声明输出，不再被误报为"文件缺失"，恢复回归测试契约。
- **新手引导**：README（中英）Quickstart 旁新增平台可用性速览表，声明能力与实测证据分开链接；`check_env` 体检后给出零依赖的 init → import → search 三步命令，按平台检查在依赖就绪时给出可直接执行的采集命令。
- **pip 安装**：`pip install -e .` 后任意目录可用 `chubby` 命令，核心保持零依赖，平台能力拆为 extras。非 editable 安装（pipx）尚未支持，见 [#16](https://github.com/chubbyguan/chubbyskills/issues/16)。

## 安装与使用

```bash
git clone --branch v0.13.1 https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 -m pip install -e .
chubby init --vault "$HOME/Documents/creator-vault"
chubby import "/你的文档目录/report.md" --no-enrich
chubby search "报告中的关键词"
```

安装包 `chubbyskills-0.13.1-skills.tar.gz` 包含 14 个可独立移动的技能目录，Python 和系统依赖需另外安装。

## 社区贡献

- [Issue #11](https://github.com/chubbyguan/chubbyskills/issues/11)，AIcodexAN：报告 X 长文章只采到预览并给出完整根因分析，本版修复（[#12](https://github.com/chubbyguan/chubbyskills/pull/12)）。登录态 GraphQL 路径未在真实 cookie 下实测，欢迎有条件的用户反馈。

## 验证范围

本地 226 项测试通过（含 X Article 预览标记、全文提取与 cookie 解析的新增用例），语法检查与 Ruff 通过。CI 在 Linux/Python 3.11 与 macOS/Python 3.12 通过，含新增的 editable 安装冒烟。

发布包重新解压后验证技能脚本隔离导入。X 登录态 GraphQL 抓取只有解析层单元测试覆盖，未做真实账号实测；其 queryId 随 X 前端发版轮换，失效时会告警回退，不会静默出错。
