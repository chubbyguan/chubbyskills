# v0.13.0 — 本地文档入库与可恢复的可选云转录

这次迭代吸收社区提出的安装、云转录和外部文档交接需求。已有本地文档可以直接进入知识库；播客新增共用接口的 Atlas Cloud 和 MuAPI 实验后端。

- **本地导入**：`chubby import` 支持 Markdown、TXT 和 PDF 文字层，保留来源和内容摘要，复制文档引用的本地附件，自动更新索引。附件变化会触发重新导入，旧产物保留。
- **可选云转录**：默认仍使用本地模型。显式选择 Atlas 或 MuAPI 后才向第三方提交音频；任务 ID 与完成结果持久保存，轮询失败和进程中断后可以恢复。
- **重试与正文完整性**：普通恢复不自动创建新任务；`--resubmit` 是一次性显式操作。新任务不会被旧成功缓存遮住，服务端完整正文不会因时间戳不完整而丢失。
- **安全下载**：认证请求不跟随重定向，播客自动下载限制为公网 HTTP(S) 直连。需要代理或跳转的音频先自行下载，再传本地文件。
- **独立安装**：知识库技能包含本地导入工具；播客技能包含全部 provider 和下载辅助模块。

## 安装与使用

```bash
git clone --branch v0.13.0 https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/chubby.py init --vault "$HOME/Documents/creator-vault"
python3 tools/chubby.py import "/你的文档目录/report.md" --no-enrich
python3 tools/chubby.py search "报告中的关键词"
```

PDF 文字层提取需要可选 `pymupdf`，不含 OCR。完整用法见[本地文档导入](document-import.md)和[云端转录](cloud-transcription.md)。安装包 `chubbyskills-0.13.0-skills.tar.gz` 包含 14 个可独立移动的技能目录，Python 和系统依赖需另外安装。

## 社区贡献

- [PR #1](https://github.com/chubbyguan/chubbyskills/pull/1)，catwithtudou：安装职责划分已由现行安装器等效解决，已说明并关闭旧 PR。
- [PR #3](https://github.com/chubbyguan/chubbyskills/pull/3)，binyangzhu000-sudo：吸收 Atlas Cloud 可选转录需求，在共用接口上重新实现。
- [PR #5](https://github.com/chubbyguan/chubbyskills/pull/5)，Anil-matcha：吸收 MuAPI 上传和转录流程，加入相同的恢复与安全约束。
- [PR #6](https://github.com/chubbyguan/chubbyskills/pull/6)，huhoo：纳入[可选集成说明](integrations.md)，实现本地 Markdown 交接；第三方实际解析仍待验证。

旧 PR 没有原样合并。作者归属和公开处理结果见[社区处理记录](community-triage.md)。

## 验证范围

本地 220 项测试通过，包含真实 CLI 文档导入、附件变化、索引与资料包导出，以及云任务生命周期的模拟回归。语法检查、Ruff、平台离线样例和真实 MCP stdio 初始化、工具发现、搜索与读取通过。

发布包需经过重新解压、全部技能脚本隔离导入、独立知识库导入与资料包导出、真实 MCP 握手验证；精确候选提交的 Linux/Python 3.11 与 macOS/Python 3.12 CI 通过后发布。验证结果附在 release 资产中。

Atlas 和 MuAPI 均为 **experimental**：本版没有调用真实付费服务，也没有把模拟请求当作真实转录验收。服务端兼容性、转录质量和费用仍需独立验证。cue-omni-reader 未安装或调用，其上游能力说明不代表本项目已验证集成。没有进行实际用户使用调研。
