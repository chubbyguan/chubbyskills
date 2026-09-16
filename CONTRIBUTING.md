# 贡献指南

感谢你愿意为 **chubbyskills** 出一份力！无论是修 bug、补新平台，还是改进文档，都欢迎。

## 怎么贡献

### 报告问题 / 提需求
用 [issue 模板](.github/ISSUE_TEMPLATE/) 提交 bug 或新平台 / 功能请求。描述越具体（命令、报错、链接），越好处理。

### 提交一个新 skill

每个 skill 的安装产物都应能独立移动和运行。源码可以复用仓库公共模块，分发时由 `tools/install_skill.py` 带上依赖：

1. **一个 skill 一个目录**：命名 `<平台>-<动作>`，如 `xiaohongshu-ingest`、`douyin-transcribe`
2. **分发后自包含**：`SKILL.md` + `scripts/` + 按需的依赖声明。新增共享模块时同步安装器的依赖清单，并测试移走原仓库后的安装产物。
3. **`SKILL.md` frontmatter** 必须有 `name`（与目录名一致）和 `description`（说明适用场景）；`triggers`、`tags`、`version` 等扩展信息放入 `metadata`，其键和值都必须是字符串。
4. **采集类 skill 必须带「合规声明」**（见现有 skill 末尾）
5. **产出 Markdown** 遵循[输出协议](README.md#输出协议)，带 `platform` 字段。公共生成器接收真实字符串、列表和布尔值，不要传入预先拼接的 YAML。

### 提交平台定义 / 站点模板

v0.6 之后，每个平台除了 skill 本身，还需要声明健康检查和知识库模板：

推荐先用 scaffold：

```bash
python3 tools/platform_adapter.py new <platform-id> \
  --name "<平台名>" \
  --sample-source "https://example.com/item/1" \
  --match "example.com"
```

1. 在 `platforms/<platform>.yaml` 里声明平台 ID、skill 目录、入口脚本、依赖、fallback 和样例链接
2. 在 `templates/sites/<platform>.yaml` 里声明 URL 匹配、frontmatter 字段、资源保存和后处理流程
3. 跑 `python3 tools/platform_health.py --check`，确认定义和模板能通过校验
4. 如果修改了平台状态说明，跑 `python3 tools/platform_health.py` 更新 `docs/platform-status.md`

平台状态页只做结构和本地依赖检查，不会在 CI 里访问真实平台。真实链接 smoke test 请在 PR 描述里贴命令和结果。更完整的规则见 [docs/contributor-platform-adapter.md](docs/contributor-platform-adapter.md)。

### 代码规范

- 优先**零依赖**（仅标准库）；重依赖（`funasr` / `torch` 等）只在必要路径**延迟 import**，别让纯文本功能也被迫装 GPU 栈
- 网络 / 解析失败要**优雅降级**，给用户清晰提示，不要甩 traceback
- 脚本用 `argparse`；**结果路径打到 stdout、日志打到 stderr**（方便串管道）
- 提交前跑 `python3 -m py_compile <脚本>` 过语法
- 若改动输出 Markdown，请跑 `python3 tools/validate_outputs.py examples/outputs` 或用你的真实输出目录替代 `examples/outputs`
- 若改动平台定义 / 模板，请跑 `python3 tools/platform_health.py --check`
- 若改动公共工具，请跑 `python3 -m unittest discover -s tests -v`
- 真实跑一遍：采集类 skill 请用**真实链接**验证，造数据测不出字段命名这类坑

### 提交流程

1. Fork → 新建分支
2. 改动 + 自测
3. 提 PR，用 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 说明动机和测试情况

## 本地开发

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt -r knowledge-base-management/requirements-mcp.txt
python3 -m unittest discover -s tests -v
python3 tools/mcp_smoke.py --json
python3 tools/check_env.py     # 体检：看缺哪些依赖
```

测试依赖中的 PyYAML 用于验证真实 YAML 往返；运行时 Markdown 生成仍仅使用标准库。CI 分别在 Linux/Python 3.11、macOS/Python 3.12 检查安装产物、协议交互、输出和代码风格。真实平台验收使用手动 workflow 或 [live verification](docs/live-verification.md) 中的命令，未提供链接的 skipped 不能算成功。

## 可选服务与生态贡献

云端 ASR provider 应显式选择，保留本地默认，并说明音频上传、费用、大小限制、超时和重试边界。mock 测试之外仍需经授权的真实服务验收，禁止把付费请求放进默认 CI。外部工具推荐先提供明确缺口和可复现集成示例，再决定是否列入可选集成文档。当前贡献处理记录见 [community-triage](docs/community-triage.md)。

## 行为准则

友善、就事论事。这是个人维护的开源项目，回复可能不会很快，但每个 issue / PR 都会看。🙏
