# 贡献指南

感谢你愿意为 **chubbyskills** 出一份力！无论是修 bug、补新平台，还是改进文档，都欢迎。

## 怎么贡献

### 报告问题 / 提需求
用 [issue 模板](.github/ISSUE_TEMPLATE/) 提交 bug 或新平台 / 功能请求。描述越具体（命令、报错、链接），越好处理。

### 提交一个新 skill

chubbyskills 的每个 skill 都要能**独立 clone 安装**（README 的安装方式就是单目录拉取），所以请遵守：

1. **一个 skill 一个目录**：命名 `<平台>-<动作>`，如 `xiaohongshu-ingest`、`douyin-transcribe`
2. **目录内自包含**：`SKILL.md` + `scripts/` + `requirements.txt`，**不要跨目录共享代码**（重复样板是可接受的代价）
3. **`SKILL.md` frontmatter** 必须有 `name`（与目录名一致）、`description`、`triggers`
4. **采集类 skill 必须带「合规声明」**（见现有 skill 末尾）
5. **产出 Markdown** 遵循[统一 frontmatter 约定](README.md#-统一-frontmatter-约定)，带 `platform` 字段，便于知识库聚合

### 代码规范

- 优先**零依赖**（仅标准库）；重依赖（`funasr` / `torch` 等）只在必要路径**延迟 import**，别让纯文本功能也被迫装 GPU 栈
- 网络 / 解析失败要**优雅降级**，给用户清晰提示，不要甩 traceback
- 脚本用 `argparse`；**结果路径打到 stdout、日志打到 stderr**（方便串管道）
- 提交前跑 `python3 -m py_compile <脚本>` 过语法
- 真实跑一遍：采集类 skill 请用**真实链接**验证，造数据测不出字段命名这类坑

### 提交流程

1. Fork → 新建分支
2. 改动 + 自测
3. 提 PR，用 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 说明动机和测试情况

## 本地开发

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/check_env.py     # 体检：看缺哪些依赖
```

## 行为准则

友善、就事论事。这是个人维护的开源项目，回复可能不会很快，但每个 issue / PR 都会看。🙏
