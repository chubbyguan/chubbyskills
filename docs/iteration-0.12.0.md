# 0.12：采集、搜索与原文资料包

这一轮把已有能力接成一条可重复运行的工作流：素材入库后更新索引，重复任务复用有效产物，选题准备可以导出带原文位置的资料包。

## 入口与目录

在完整仓库中运行：

```bash
python3 tools/chubby.py init --vault "$PWD/creator-vault"
python3 tools/chubby.py doctor --platform x
python3 tools/chubby.py ingest "替换为实际来源链接" --no-enrich
python3 tools/chubby.py search "原文中的关键词"
python3 tools/chubby.py search "准备写的问题" --mode lite
python3 tools/chubby.py brief --topic "准备写的问题" --output research/brief.md
```

`init --vault ROOT` 将配置中的 `vault_root` 设为根目录、`vault_dir` 设为 `ROOT/00_Inbox`，`index_db` 设为 `ROOT/.chubby/index.sqlite`。已有配置仅更新这三个字段，保留其他设置。`ingest --vault DEST` 保持旧语义：直接写入指定目录，不自动追加 `00_Inbox`。`search/brief --vault ROOT` 指定检索范围。

`doctor --platform` 只针对所选平台检查必需依赖。缺少必需项返回非零；可选的媒体或本地转录组件缺失会单独列出。依赖齐全不代表远端平台、登录态或目标内容可访问。

## 重复采集与失败重试

- YouTube 长短链接按视频 ID 识别；B站保留分 P；X 与 Twitter 链接按帖子 ID 识别。未知链接保持原样，不猜测短链重定向。本地输入同时检查路径和文件内容。
- 来源、处理参数、目的地和项目版本一致，且记录中的 Markdown 与附件仍有效时，复用上次成功产物。传入的本地正文等文件发生变化会重新采集。复用保留原来的采集时间与运行标识，不重写用户修改的正文。
- `ingest/run/retry --refresh` 强制重新采集；新文件使用来源摘要和必要的版本后缀，旧文件保留。同名不同来源不会互相覆盖。
- `retry` 继承原任务的输出位置、知识库、加工开关、附加参数和超时；显式参数覆盖原值。状态与报告中的常见 URL/CLI 凭据字段会脱敏；需要已脱敏凭据的重试要求重新提供参数。
- 入库成功但索引失败时，保留原文并分别记录采集和索引状态，命令返回非零；后续 `search` 会再次同步索引。

旧记录缺少新的执行指纹时，不推断复用。升级后的第一次重复任务可能重新采集，但仍保留已有文件。

## 索引升级

采集入库及统一搜索、MCP 查询会增量同步索引。新增、修改和删除的笔记同步到 SQLite/FTS；未改变的笔记与向量保留，影响 embedding 输入的修改才使对应向量失效。向量补齐仍由显式 `embed` 命令执行，普通查询不会调用付费 embedding API。

```bash
export VAULT_DIR="/你的/知识库绝对路径"
python3 tools/vault_index.py index "$VAULT_DIR"
python3 tools/vault_index.py search "关键词"
# 只有明确要丢弃该索引的向量并重新绑定知识库时才使用：
# python3 tools/vault_index.py index "$VAULT_DIR" --rebuild
```

默认索引统一为所选知识库内的 `.chubby/index.sqlite`。显式 `--db` 或配置中的 `index_db` 优先于 `VAULT_INDEX_DB`，环境变量优先于默认位置。直接使用独立索引 CLI 时，每次命令需有 `--db` 或 `VAULT_DIR`，不会悄悄使用仓库共享索引。

知识库内旧 `.chubby/vault_index.sqlite` 会在可安全确认时复制到新位置，保留旧文件。显式使用的旧数据库若已绑定同一知识库可继续使用；无法确认归属的外部旧库会拒绝自动绑定，可指定新的数据库路径。跨知识库复用数据库需显式 `--rebuild`。旧仓库根目录中的共享数据库不会自动搬到任意知识库。

增量指数据库写入与向量更新；当前同步仍扫描知识库 Markdown 并读取内容。大库的查询耗时仍可能受全库扫描影响，本版没有文件监听或后台同步服务。

## 资料包包含什么

`brief` 先检索本地原始笔记；关键词无结果时使用本地 semantic-lite。输出配对的 Markdown 和 JSON，包含来源链接、笔记路径、采集时间、文件 SHA-256，以及带起止行号的逐字摘录。生成及导出前都会核对来源文件。资料不足会明确写出，不补造引用。

它不生成最终选题、不联网调查，也不认证原文观点的真实性。可以将生成的资料包交给 Agent，按内附任务说明区分原文与推断、整理选题并列出待补材料。生成的 `research_brief` 不作为后续 brief 的原始证据，避免结果反复引用自身。

输出默认拒绝覆盖；`--force` 只替换已有资料包，拒绝覆盖普通笔记和当前引用的原文。JSON 包含本机知识库绝对路径和原文摘录，分享前检查内容；Markdown 的本地链接相对输出目录生成，移动文件后可能需要重新导出。

## 验证范围

本轮验收覆盖增量索引、向量保留、MCP 查询同步、重复采集、同名文件、附件缺失、重试上下文、脱敏、逐字引用、独立安装与真实 CLI 进程串联。CLI 串联使用明确标记的本地正文导入，不把它算作平台自动抓取成功。平台远端适配器没有因本次离线验收获得新的可用性保证，已有记录见[真实平台验证](live-verification.md)。
