# Chubby Vault Template

This is a minimal Obsidian-friendly vault layout for chubbyskills.

## Folders

- `00_Inbox/`: fresh captures copied from `tools/chubby.py --vault`.
- `10_Sources/`: immutable source notes grouped by platform or project.
- `20_Processed/`: summaries, evergreen notes, and reusable knowledge.
- `30_Dashboards/`: Dataview-style dashboards and review pages.
- `40_Assets/`: shared images, audio, PDFs, and generated assets.
- `Templates/`: note templates for manual capture and cleanup.

## Suggested Setup

```bash
python3 tools/chubby.py init
python3 tools/chubby.py ingest "<url>" --vault /path/to/vault/00_Inbox
python3 tools/vault_index.py index /path/to/vault
python3 tools/vault_index.py search "AI Agent"
```

The indexer reads Markdown frontmatter fields such as `platform`, `source`,
`tags`, `summary`, `schema_version`, and `content_type`.
