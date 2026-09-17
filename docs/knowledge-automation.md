# 知识库自动化

v0.12.0 把采集、增量索引、搜索和原文资料包接到同一个知识库配置。默认检索使用 Python 标准库和 SQLite，真实 embedding 为可选能力。

## 统一入口

在仓库根目录完成一次配置：

```bash
python3 tools/chubby.py init --vault /path/to/vault
python3 tools/chubby.py ingest "替换为真实链接" --no-enrich
python3 tools/chubby.py search "内容策略"
python3 tools/chubby.py search "内容策略" --mode lite
python3 tools/chubby.py brief --topic "内容策略" --output reports/content-brief.md
```

采集结果进入根目录的 `00_Inbox`。成功采集后，以及统一 `search` / `brief` 查询前，自动增量同步根目录下的 `.chubby/index.sqlite`。

增量同步保留未变化笔记的向量。标题、标签、摘要或实际送入向量模型的正文片段变化时，对应旧向量失效；删除笔记时移除索引和向量。重命名或移动笔记按旧路径删除、新路径加入处理。

## 独立索引与搜索

独立 `vault_index.py` 不读取 `chubby.yaml`。指定知识库后，后续命令仍需 `VAULT_DIR` 或显式 `--db`；不能只在首次 `index` 命令中传一次路径。

```bash
export VAULT_DIR="/path/to/vault"
python3 tools/vault_index.py index "$VAULT_DIR"
python3 tools/vault_index.py search "内容策略"
python3 tools/vault_index.py semantic "agent retrieval" --platform x
python3 tools/vault_index.py semantic "选题" --tag strategy --json
python3 tools/vault_index.py recent --limit 10
python3 tools/vault_index.py stats
```

独立搜索读取现有索引；笔记改变后先再次运行 `index`。统一 `chubby.py search` 和 MCP 查询会自动完成该同步。

`semantic-lite` 基于标题、标签、摘要和正文中的词语及字符组合排序，不下载模型，也不调用模型 API。

使用显式数据库时，`--db` 放在子命令前，并在后续命令中保持一致：

```bash
python3 tools/vault_index.py --db /path/to/index.sqlite index /path/to/vault
python3 tools/vault_index.py --db /path/to/index.sqlite search "内容策略"
```

## 索引路径与迁移

- 默认位置为 `<知识库根目录>/.chubby/index.sqlite`；`VAULT_INDEX_DB` 或显式 `--db` 可以覆盖。
- 新默认索引尚不存在、知识库中有旧 `.chubby/vault_index.sqlite` 时，首次同步会复制迁移并保留旧文件，未变化的向量可继续使用。
- 仓库根目录或其他位置的旧数据库需要显式指定。没有 vault 绑定信息的外部旧数据库，仅在已有笔记能与当前知识库对应时自动接管；无法确认时会报错，避免误删另一知识库的数据。
- 已绑定数据库拒绝切换到不同知识库；扫描失败或读取错误会回滚本次同步。指向知识库之外的笔记符号链接会被拒绝。

明确需要全量重建时：

```bash
python3 tools/vault_index.py index "$VAULT_DIR" --rebuild
```

该命令会丢弃现有 embedding，并从 Markdown 重建索引。MCP 的 `reindex_vault()` 保留原名称，但默认只做增量同步。

## 可选 embedding

默认的 `lite` 路径无需 API key。以下操作会调用对应服务或下载本地模型，只在你选择该 provider 时执行。

OpenAI provider：

```bash
export VAULT_DIR="/path/to/vault"
export OPENAI_API_KEY="替换为自己的凭据"
python3 tools/vault_index.py embed "$VAULT_DIR" --provider openai
python3 tools/vault_index.py semantic "内容策略" --provider openai
```

`OPENAI_EMBEDDING_MODEL` 默认是 `text-embedding-3-small`；`OPENAI_BASE_URL` 可指定兼容服务。生成和检索应使用相同模型。

本地模型 provider：

```bash
export VAULT_DIR="/path/to/vault"
python3 -m pip install sentence-transformers
python3 tools/vault_index.py embed "$VAULT_DIR" --provider local
python3 tools/vault_index.py semantic "内容策略" --provider local
```

`CHUBBY_LOCAL_EMBEDDING_MODEL` 默认是 `paraphrase-multilingual-MiniLM-L12-v2`。重复执行 `embed` 只处理所选 provider/model 缺少向量的笔记。生成期间若笔记发生变化，旧响应会被跳过，结果中的 `skipped_changed` 会记录数量，可重新执行 `embed` 补齐。

MCP 读取 `CHUBBY_EMBEDDING_PROVIDER` 和可选的 `CHUBBY_EMBEDDING_MODEL`。未设置时使用 `lite`；自动同步只让变化笔记的旧向量失效，不自动触发付费 API 或模型下载。

## 逐字原文资料包

```bash
python3 tools/chubby.py brief --topic "内容策略" --limit 5 \
  --output reports/content-brief.md
```

输出 Markdown 和同名 JSON，保留来源、笔记路径、真实行号、逐字摘录和文件 SHA-256。检索范围为本地知识库，生成的资料包不会成为后续资料包的检索候选。内容不足时标明证据不足；工具不会自行生成选题或认证原文事实。

独立安装知识库 skill 后：

```bash
python3 ~/.codex/skills/knowledge-base-management/tools/evidence_brief.py \
  --vault /path/to/vault --topic "内容策略" --output reports/content-brief.md
```

已有输出默认拒绝覆盖；确实要替换时使用 `--force`。完整过程见[创作者工作流](./creator-workflow.md)。

## 自动归档

默认预览，使用 `--apply` 才移动文件：

```bash
python3 tools/vault_curator.py archive /path/to/vault
python3 tools/vault_curator.py archive /path/to/vault --apply
```

只处理 `00_Inbox/**/*.md`。有 `summary`、`archive_status: processed` 或 processed/evergreen 标签的笔记进入 `20_Processed/`；其他笔记进入 `10_Sources/<platform>/`。移动时写入 `archived_at` 和 `archived_from`，同名文件自动增加后缀。

## 知识卡片

```bash
python3 tools/vault_curator.py card /path/to/vault "10_Sources/x/example.md"
python3 tools/vault_curator.py card /path/to/vault "10_Sources/x/example.md" --apply
```

预览确认后，`--apply` 写入 `20_Processed/Cards/`。卡片保留来源笔记、平台、source、tags，并从摘要和正文段落提取要点。
