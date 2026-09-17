<div align="center">

[中文](./README.md) · **English**

# 🧰 Chubby Skills

### Turn saved content into a source-backed idea library

Save the original text and sources from videos, articles, and image posts. Let your agent find evidence in your own library and prepare content ideas with references.

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Version](https://img.shields.io/badge/Version-0.13.0-10B981?style=for-the-badge)](./CHANGELOG.md)
[![Skills](https://img.shields.io/badge/Skills-14-10B981?style=for-the-badge)](#skills)

</div>

## Who this is for

Chubby Skills is for content creators who already use an agent or a local Markdown vault and want to find the sources behind their saved material when writing. It combines platform ingestion, Markdown storage, local search, and an optional knowledge-base MCP server.

Start with one of your own sources below. See the [creator workflow](./docs/creator-workflow.md) for the complete capture-to-brief workflow, or inspect the [sample outputs](./examples/README.md) before installing. Detailed workflow documents are currently in Chinese.

Storage is local by default. Fetching content still needs network access and may depend on captions, login state, or platform restrictions. Optional DeepSeek enrichment and OpenAI embeddings send content to the configured API and may incur charges. If you use a cloud agent, the material it reads enters that model's context. See [tool selection and data-processing boundaries](./docs/comparison.md).

## Start with one real source

The following commands target a macOS / Linux shell with Python 3. Clone the complete repository and create a virtual environment:

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 -m venv .venv
source .venv/bin/activate
bash setup.sh light
python3 tools/chubby.py init --vault "$PWD/creator-vault"
```

Choose a source you are allowed to read and save. Check its platform requirements below, replace the placeholders, then run:

```bash
python3 tools/chubby.py ingest "REPLACE_WITH_YOUR_REAL_URL" --no-enrich
python3 tools/chubby.py status --latest
python3 tools/chubby.py search "a phrase from the original"
python3 tools/chubby.py brief --topic "my writing question" --output research/brief.md
```

Import existing Markdown, text, or text-based PDF into the same workflow:

```bash
python3 tools/chubby.py import "/path/to/source.md"
python3 tools/chubby.py import "/path/to/source.pdf" --source-url "https://example.com/original"
```

Markdown/text imports use the standard library; PDF needs optional `pymupdf`. Sources and referenced local assets are preserved. See [document import](./docs/document-import.md) and [optional integrations](./docs/integrations.md).

Podcast transcription stays local by default. Atlas and MuAPI are experimental, opt-in cloud providers with persistent task recovery; see [cloud transcription](./docs/cloud-transcription.md).

Captures go into `creator-vault/00_Inbox` and synchronize the index automatically. Valid artifacts are reused for the same source, processing settings and destination; `--refresh` captures again and preserves previous versions. Brief exports contain exact source lines, links and file hashes in Markdown and JSON. They do not call a cloud model or verify whether a claim is true.

Open the resulting Markdown and check its text, source, and required media. The first useful result is your own readable content with a source you can revisit. Record manual-text fallback separately from automatic fetch success. See the [creator workflow](./docs/creator-workflow.md) and [0.12 migration notes](./docs/iteration-0.12.0.md).

To check the environment and sample workflow first:

```bash
python3 tools/chubby.py quickstart --ephemeral --no-state
```

This is an offline check. It does not fetch real platform content or prove that your login, target platform, or source quality is sufficient. MCP requires the separate protocol check below.

## Installation

### Runtime dependencies

Inside the active virtual environment, choose what you need:

```bash
bash setup.sh light   # lightweight text/image and knowledge tools
bash setup.sh video   # local video transcription dependencies
bash setup.sh podcast # local podcast transcription dependencies
bash setup.sh wechat  # WeChat / PDF dependencies
bash setup.sh all     # all runtime dependencies
bash setup.sh doctor  # environment checks
```

`setup.sh` installs runtime dependencies; it does not register skills with an agent. Caption extraction needs `yt-dlp`. Local audio transcription needs additional dependencies when captions are unavailable. X and Xiaohongshu text/image ingestion do not need video models; install the `video` group for transcription.

### Install a skill for your agent

Build a portable skill directory, including shared source dependencies, from the complete repository. For Codex:

```bash
python3 tools/install_skill.py bilibili-transcribe --dest ~/.codex/skills
```

List multiple skill names to install several, or use `--all` for all skills. For another agent, set `--dest` to its actual skills directory. The installer does not install Python packages or start the agent, and refuses to overwrite an existing directory.

Do not download a single source skill directory from GitHub: source skills reference shared repository modules. Directories produced by the installer can be moved as a unit. See the [installation guide](./docs/installation.md).

### Optional knowledge-base MCP

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

The check starts a real MCP process and verifies protocol interactions using test data. Configure your actual client and vault using the [MCP guide](./docs/mcp-workflow.md).

## Platform capabilities and limits

| Platform / content | Implemented path | Requirements and possible failures |
|---|---|---|
| Bilibili / YouTube | Captions first, then audio transcription | `yt-dlp`; local transcription stack without captions; login or region restrictions may apply |
| Douyin | Video transcription | `ffmpeg` and local model; links may expire or downloads may be blocked |
| TikTok / Weibo / Zhihu | Video transcription | `yt-dlp`, `ffmpeg`, local model; platform markup and access restrictions vary |
| Podcasts | Xiaoyuzhou / Ximalaya / RSS / local audio | `ffmpeg` + `faster-whisper`; downloads and long recordings can fail or take time |
| WeChat | Articles / PDF to Markdown | HTML/PDF extraction dependencies; saved HTML/PDF fallback for inaccessible pages |
| Xiaohongshu | Text/images and video transcription | Login state may be needed; manual-text fallback; video requires local transcription dependencies |
| X / Twitter | Text/images and video transcription | Public endpoints may fail; manual text / structured-data fallback; video requires local transcription dependencies |

This table describes implementation scope, not guaranteed live availability. The [platform status page](./docs/platform-status.md) is generated from definitions and templates. Labels such as `stable` do not replace recent real-link tests. See the [dated live verification report](./docs/live-verification.md) and [failure/fallback guide](./docs/platform-fallbacks.md).

## Use saved material

Keep a separate SQLite index for each vault:

```bash
python3 tools/vault_index.py --db /path/to/vault/index.sqlite index /path/to/vault
python3 tools/vault_index.py --db /path/to/vault/index.sqlite semantic "my writing question" --provider lite
python3 tools/vault_index.py read "00_Inbox/actual-note.md" --vault /path/to/vault
```

Keyword search and default semantic-lite run locally. Optional embedding providers and dry-run-first archive/card commands are covered in [knowledge automation](./docs/knowledge-automation.md).

Ask your agent to read the original notes before proposing ideas. For each factual claim, require both the note path and the original `source` link. Keep author claims separate from the agent's inferences, and mark missing evidence instead of inventing a reference. Manually check the sources before using the material in published work.

For queued ingestion and retries:

```bash
python3 tools/chubby.py run --queue inbox/links.txt
python3 tools/chubby.py status --latest
python3 tools/chubby.py retry --all-failed
```

The pipeline records per-source state in `.chubby/runs.jsonl`, writes daily reports in `runs/`, and adds schema v1 metadata. Put one authorized source per line in the queue.

## Skills

| Skill | Purpose |
|---|---|
| [douyin-transcribe](./douyin-transcribe/SKILL.md) | Douyin video transcription |
| [bilibili-transcribe](./bilibili-transcribe/SKILL.md) | Bilibili captions and transcription |
| [tiktok-transcribe](./tiktok-transcribe/SKILL.md) | TikTok video transcription |
| [weibo-transcribe](./weibo-transcribe/SKILL.md) | Weibo video transcription |
| [zhihu-transcribe](./zhihu-transcribe/SKILL.md) | Zhihu video transcription |
| [youtube-transcribe](./youtube-transcribe/SKILL.md) | YouTube captions, transcription, optional translation |
| [podcast-transcribe](./podcast-transcribe/SKILL.md) | Podcast / RSS / local audio transcription |
| [wechat-article-ingest](./wechat-article-ingest/SKILL.md) | WeChat articles and PDF ingestion |
| [xiaohongshu-ingest](./xiaohongshu-ingest/SKILL.md) | Xiaohongshu text, images, and video |
| [x-ingest](./x-ingest/SKILL.md) | X / Twitter text, images, and video |
| [content-enrich](./content-enrich/SKILL.md) | Optional API-based summaries, key points, and tags |
| [knowledge-base-management](./knowledge-base-management/SKILL.md) | Vault management, indexing, and MCP |
| [industry-intelligence-radar](./industry-intelligence-radar/SKILL.md) | Multi-source research workflow |
| [learning-notes-automation](./learning-notes-automation/SKILL.md) | Learning notes and flashcards |

## Verification

| Check | What it establishes |
|---|---|
| `python3 tools/chubby.py quickstart --ephemeral --no-state` | Offline environment and fixture workflow |
| `python3 tools/validate_outputs.py examples/outputs --schema-v1` | Example Markdown metadata conforms to schema v1 |
| `python3 tools/platform_health.py --check` | Platform definitions and templates are structurally valid |
| `python3 tools/platform_smoke.py --mode all --check` | Layered checks; unconfigured live checks are not successes |
| `python3 tools/mcp_workflow_demo.py` | Fixture-based indexing and source-reading logic |
| `python3 tools/mcp_smoke.py --json` | Real server startup, handshake, and tool calls |

Neither fixtures nor MCP protocol checks prove that real platform content can be fetched. Live tests require explicit source configuration; results are scoped to the sample, environment, and test date. See the [release checklist](./docs/release.md) and [live verification report](./docs/live-verification.md).

## Documentation and contributing

- [Creator workflow](./docs/creator-workflow.md)
- [Installation](./docs/installation.md)
- [Offline quickstart](./docs/quickstart.md)
- [MCP configuration](./docs/mcp-workflow.md)
- [Tool selection and processing boundaries](./docs/comparison.md)
- [Ten-creator pilot template — not yet executed](./docs/user-pilot.md)
- [Community contribution triage plan](./docs/community-triage.md)
- [Contributor guide](./CONTRIBUTING.md) and [platform adapters](./docs/contributor-platform-adapter.md)
- [Changelog](./CHANGELOG.md)

## Usage limits

Ingestion skills are intended for personal learning and research. Follow platform terms, `robots.txt`, and applicable laws. Do not use them for bulk scraping, commercial scraping, redistribution, or infringing uses. Use only your own authorized login state. Source content remains the original author's work; obtain permission when required and attribute it appropriately.

Code is provided under the [MIT License](./LICENSE), as is. This does not grant rights to third-party content.

Maintained by [Chubby](https://github.com/chubbyguan), who uses these workflows for content work and a personal knowledge base.
