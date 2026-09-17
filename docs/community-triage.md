# 社区贡献处理记录

更新日期：**2026-09-17**。本轮检查公开 PR、评论、提交和当前代码，在离线环境复现影响合入的缺陷。下表区分问题吸收、代码实现与公开维护动作；完成测试不等于第三方服务已经通过真实验收。

## 处理决定

| 贡献 | 值得吸收的需求 | 本项目的处理 |
|---|---|---|
| [PR #1：安装依赖路由](https://github.com/chubbyguan/chubbyskills/pull/1) | 区分运行依赖安装与 Agent skill 注册，完整名称路由和轻量依赖边界 | v0.11.1 已以当前安装器等效解决；本轮说明对应关系并关闭旧 PR |
| [PR #3：Atlas Cloud 播客转录](https://github.com/chubbyguan/chubbyskills/pull/3)，[binyangzhu000-sudo](https://github.com/binyangzhu000-sudo) | 为不便运行本地模型的用户提供可选云端转录 | 在统一 provider 接口上重新实现，加入任务恢复和安全请求；保留本地默认，标记 experimental |
| [PR #5：MuAPI 播客转录](https://github.com/chubbyguan/chubbyskills/pull/5)，[Anil-matcha](https://github.com/Anil-matcha) | 可选托管转录、上传、轮询和统一 Markdown | 与 Atlas 共用恢复和输出约定，修复显式本地选择失效等问题；标记 experimental |
| [PR #6：cue-omni-reader 文档入口](https://github.com/chubbyguan/chubbyskills/pull/6)，[huhoo](https://github.com/huhoo) | 让站外文档或外部解析结果能进入知识库 | 增加通用本地文档导入和[可选集成页](./integrations.md)，保留第三方解析待验证状态；未原样合入 README 推荐段落 |

## 为什么重新实现云端接入

两份 PR 提供了有用的后端划分和调用示例，但现有离线测试没有覆盖以下实际问题：

- 两份实现都只在内存保存云端任务 ID。提交成功后查询失败，再运行会重复提交，可能重复计费。
- 认证请求未限制跨服务或 HTTPS 降级重定向，标准库可能把凭据一起转发。
- #5 的批量入口在 `local` 时省略 provider 参数；如果环境变量选择 MuAPI，用户显式指定本地仍会让子进程使用云端。
- #3 新增同目录模块导入，需适配独立安装后的隔离运行方式，保持本地模式可用。

本轮按共同接口吸收需求和实现思路，补充任务持久化、明确重新提交边界、本地选择优先级和可搬迁验证。来源保留上述作者归属；这不等于原 PR 已合并或远端服务已验收。使用方式见[云端转录说明](./cloud-transcription.md)。

## 文档交接的范围

#6 提交者已披露自己是上游维护者。上游解析依赖 MCP Bridge、API key、目录授权和可能计费的外部服务，不能只用一行 skill 安装命令证明集成可用。

本轮先实现本地 Markdown、TXT 和 PDF 文字层导入，接入现有搜索、资料包和原稿保护流程。外部工具只要能完整导出 Markdown，就可以使用相同入口。可运行示例见[本地文档导入](./document-import.md)；示例使用人工样本，不冒充 cue-omni-reader 的真实解析结果。

## 公开处理记录

| 贡献 | 已执行的公开动作 | 链接或当前边界 |
|---|---|---|
| #1 | 已评论说明等效解决并关闭 | [维护说明](https://github.com/chubbyguan/chubbyskills/pull/1#issuecomment-5708973399) |
| #3 | 尚未在本记录中确认公开处理 | 代码吸收与 PR 评论、关闭是不同动作 |
| #5 | 尚未在本记录中确认公开处理 | 代码吸收与 PR 评论、关闭是不同动作 |
| #6 | 保留待真实集成示例 | 未安装或调用上游服务，未声称已验证解析 |

仅在维护动作真实完成后更新此表，不用计划替代已执行状态。

Issue [#4](https://github.com/chubbyguan/chubbyskills/issues/4) 的 MCP 启动失败已在 SDK 2.2.0 上复现；v0.11.1 固定 SDK 1.30.0，并通过真实 stdio 初始化、6 个工具发现、搜索和读取。该验证不等于完整 MCP 协议一致性认证。
