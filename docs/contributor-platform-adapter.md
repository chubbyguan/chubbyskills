# Contributor Platform Adapter

新平台不应该从复制旧目录开始。v0.9 提供 `tools/platform_adapter.py`，先生成最小可验证骨架，再逐步补真实抓取逻辑。

## Scaffold

```bash
python3 tools/platform_adapter.py new hacker-news \
  --name "Hacker News" \
  --sample-source "https://news.ycombinator.com/item?id=123" \
  --match "news.ycombinator.com"
```

它会生成：

- `platforms/hacker-news.yaml`
- `templates/sites/hacker-news.yaml`
- `hacker-news-ingest/SKILL.md`
- `hacker-news-ingest/scripts/fetch_hacker_news.py`

生成后先跑：

```bash
python3 tools/platform_health.py --check
python3 hacker-news-ingest/scripts/fetch_hacker_news.py "https://news.ycombinator.com/item?id=123" --output output
python3 tools/validate_outputs.py output --schema-v1 --platform-dir platforms
```

## Review Rules

贡献新平台时，PR 至少要包含：

- `platforms/<id>.yaml`：状态、依赖、fallback、sample source 清楚。
- `templates/sites/<id>.yaml`：URL match、frontmatter、postprocess 清楚。
- `<skill>/SKILL.md`：说明使用方式、依赖和限制。
- `<skill>/scripts/...`：能输出符合 schema v1 的 Markdown。
- 一个失败 fallback 说明：平台风控、登录、cookie 或手动输入路径。

新平台默认用 `status: experimental`。只有有稳定样例、CI 或维护者确认后，再提升为 `beta` 或 `stable`。
