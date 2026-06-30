# Knowledge Automation

v0.9 在本地知识库层补了三个零依赖能力：semantic-lite 检索、自动归档、知识卡片生成。

## Semantic-Lite Search

先建索引：

```bash
python3 tools/vault_index.py index /path/to/vault
```

再做概念检索：

```bash
python3 tools/vault_index.py semantic "内容策略"
python3 tools/vault_index.py semantic "agent retrieval" --platform x
python3 tools/vault_index.py semantic "选题" --tag strategy --json
```

这不是大模型 embedding，不需要下载模型。它基于本地标题、标签、summary、正文做 token/bigram 向量排序，适合作为默认零依赖语义层；后续可以在同一接口后面接真正 embedding。

MCP server 也暴露 `semantic_search_vault`，Agent 可以直接用概念查询检索 vault。

## Real Embedding Providers

v0.10 起，`vault_index.py` 支持把真实 embedding 写入 SQLite。默认仍然是 `semantic-lite`，不会要求 API key 或模型下载。

OpenAI provider：

```bash
export OPENAI_API_KEY="..."
python3 tools/vault_index.py embed /path/to/vault --provider openai
python3 tools/vault_index.py semantic "内容策略" --provider openai
```

可选环境变量：

- `OPENAI_EMBEDDING_MODEL`：默认 `text-embedding-3-small`。
- `OPENAI_BASE_URL`：兼容代理或网关。

本地模型 provider：

```bash
python3 -m pip install sentence-transformers
python3 tools/vault_index.py embed /path/to/vault --provider local
python3 tools/vault_index.py semantic "内容策略" --provider local
```

可选环境变量：

- `CHUBBY_LOCAL_EMBEDDING_MODEL`：默认 `paraphrase-multilingual-MiniLM-L12-v2`。

MCP server 会读取 `CHUBBY_EMBEDDING_PROVIDER`。未设置时继续使用零依赖 `lite`。

## Auto Archive

默认 dry-run：

```bash
python3 tools/vault_curator.py archive /path/to/vault
```

真正移动文件：

```bash
python3 tools/vault_curator.py archive /path/to/vault --apply
```

规则：

- 只处理 `00_Inbox/**/*.md`。
- 有 `summary`、`archive_status: processed` 或 processed/evergreen 标签的笔记进入 `20_Processed/`。
- 其它笔记进入 `10_Sources/<platform>/`。
- 移动时会写入 `archived_at` 和 `archived_from`。
- 同名文件会自动加后缀，避免覆盖。

## Knowledge Cards

预览单篇笔记的知识卡片：

```bash
python3 tools/vault_curator.py card /path/to/vault "10_Sources/x/example.md"
```

写入 `20_Processed/Cards/`：

```bash
python3 tools/vault_curator.py card /path/to/vault "10_Sources/x/example.md" --apply
```

卡片会保留来源笔记、平台、source、tags，并从 summary、正文段落和 bullet 中提炼可复用摘要与要点。
