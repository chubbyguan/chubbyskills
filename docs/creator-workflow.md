# 从收藏素材到可引用选题

这条流程面向已经在使用 Agent、愿意保留本地 Markdown 的内容创作者。目标是：用自己的 3 条素材，整理一份每个主要观点都能回到原文的选题资料。

没有真实素材时，可以运行离线样例了解输出；样例通过不计为真实采集成功。

## 1. 准备环境和素材

先按 [README 安装方式](../README.md#安装方式)克隆完整仓库，建立虚拟环境，安装需要的运行依赖。以下命令都在仓库根目录、已激活的虚拟环境里运行。

选择你有权读取和保存的 3 条真实素材，围绕同一个准备写的主题。先从一条开始：

| 素材 | 开始前确认 | 遇到限制时 |
|---|---|---|
| B站 / YouTube 视频 | 优先选有可用字幕的内容，安装 `yt-dlp` | 无字幕需本地转录依赖；登录或地区限制可能阻止下载 |
| 公众号文章 | 安装 `wechat` 运行依赖 | 可使用已保存的 HTML 或 PDF，按[失败指南](./platform-fallbacks.md)操作 |
| X / 小红书图文 | 阅读对应 skill 的登录态和链接要求 | 支持手动正文 fallback，但必须记录为人工导入 |

其他来源见[平台状态](./platform-status.md)。先解决一个平台的失败，再增加来源。

## 2. 采集第一条，检查原文

创建一个独立的试用库，便于查看这次到底存了什么：

```bash
CHUBBY_VAULT="$PWD/creator-vault"
mkdir -p "$CHUBBY_VAULT/00_Inbox"
python3 tools/chubby.py ingest "替换为第一条真实链接" \
  --vault "$CHUBBY_VAULT/00_Inbox" --no-enrich
python3 tools/chubby.py status --latest
```

`--no-enrich` 让这一步保留采集结果，不调用配置中的内容加工 API。命令失败时，先看报告和[失败指南](./platform-fallbacks.md)，不要把登录提示、错误页面或手动粘贴当作自动采集成功。

打开输出的 Markdown，核对标题、`source`、正文，以及这条素材应该包含的图片或字幕。通过后，再对另外两条真实链接重复 `ingest` 命令。

**这一步完成的证据：**本地存在可阅读的真实正文，来源可以回查。只有文件路径或 `success` 状态还不够。

## 3. 找回证据

为这个试用库建立独立索引，避免和已有知识库混用：

```bash
python3 tools/vault_index.py --db "$CHUBBY_VAULT/index.sqlite" index "$CHUBBY_VAULT"
python3 tools/vault_index.py --db "$CHUBBY_VAULT/index.sqlite" search "替换为素材中的关键词"
python3 tools/vault_index.py --db "$CHUBBY_VAULT/index.sqlite" semantic "替换为你准备写的问题" --provider lite
```

从结果中复制相对路径，读取原文：

```bash
python3 tools/vault_index.py read "00_Inbox/替换为实际文件名.md" --vault "$CHUBBY_VAULT"
```

关键词检索和默认 semantic-lite 都在本地执行。语义检索漏掉内容时，改用原文中的词或直接查看笔记；搜索结果不等于证据本身。

## 4. 让 Agent 整理选题资料

能读取本地文件的 Agent 可以直接使用这个目录。需要 MCP 的客户端，按 [MCP 配置](./mcp-workflow.md)设置同一个 vault。先验证 server 的真实连接：

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

该检查使用测试资料验证协议交互，不证明你的真实素材已采集，也不替代在所用客户端里的连接检查。使用云端 Agent 模型时，模型会接收你让它读取的内容。

把下面提示词交给 Agent，填入试用库的绝对路径和主题：

```text
我的素材库位于：<creator-vault 的绝对路径>。
我准备写的主题是：<主题>。

先检索素材，再读取相关原文；使用 MCP 时调用 search_vault /
semantic_search_vault 和 read_kb_note。
给我 3 个可发展的选题，每个包含：
- 面向谁，以及要回答的具体问题；
- 2–3 个有原文支持的事实或观点；
- 每条事实对应的笔记相对路径和原始 source 链接；
- 哪些是作者观点，哪些是你的推断；
- 还需要补充或验证的资料。
资料不足就写“证据不足”，不要补造事实、引文或来源。
```

将核对后的结果另存为自己的选题文档。发布内容前回到原文确认引用、上下文和来源授权。

## 怎么判断这次有效

| 阶段 | 完成标准 |
|---|---|
| 环境可用 | 离线 quickstart 通过；需要 MCP 时真实协议检查通过 |
| 素材入库 | 至少 1 条自己的真实内容保存完整，来源可回查；标记是否需要人工 fallback |
| 选题可用 | 至少 1 个选题被你选中，每个主要观点都有能打开的原文依据 |
| 后续复用 | 7 天内再次采集或使用素材完成一次自己的任务 |

前三步可以本次完成；最后一项要等实际发生再记录。[试用记录](./user-pilot.md)用于收集失败原因和复用情况，不能由演示结果代填。
