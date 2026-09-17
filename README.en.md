<div align="center">

[中文](./README.md) · **English**

# 🧰 Chubby Skills

### Turn saved content into a searchable source library

Import documents, capture articles and transcripts, and search the original text when you need it. Export a source-backed brief for your agent to work from.

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Version](https://img.shields.io/badge/Version-0.13.0-10B981?style=for-the-badge)](https://github.com/chubbyguan/chubbyskills/releases/tag/v0.13.0)
[![Skills](https://img.shields.io/badge/Skills-14-10B981?style=for-the-badge)](#skills)
[![Stars](https://img.shields.io/github/stars/chubbyguan/chubbyskills?style=for-the-badge&color=F59E0B)](https://github.com/chubbyguan/chubbyskills/stargazers)

[Quick start](#try-the-local-workflow) · [Agent installation](#install-skills-for-your-agent) · [Skills](#skills) · [Documentation](#documentation) · [Changelog](./CHANGELOG.md)

</div>

Chubby Skills is a set of **14 agent skills and a local command-line workflow** for content creators, researchers, and people who keep a Markdown knowledge base. It connects saved material to the sources behind it, so an agent can read your notes before helping you write.

Your library stays in ordinary Markdown files. The repository provides import, platform capture, indexing, search, and evidence-brief export; an optional MCP server lets your agent query the same library.

## What you can do

| Start with | Get |
|---|---|
| Existing Markdown, TXT, or text-based PDF | Notes with provenance, content hashes, and referenced local attachments |
| Articles, video links, podcasts, or local audio | Markdown text or transcripts through platform-specific skills |
| A growing Markdown library | Local keyword search and lightweight semantic retrieval |
| A writing or research question | A Markdown/JSON brief with exact excerpts, source links, line numbers, and file hashes |
| An agent that supports skills or MCP | Reusable workflows and direct access to your own source material |

**New in [v0.13.0](./docs/release-0.13.0.md):** unified local document import, experimental Atlas/MuAPI podcast transcription with saved task recovery, and portable installation bundles for the new tools.

See [sample outputs](./examples/README.md) to inspect the files before installing. Most detailed guides are currently in Chinese.

## Try the local workflow

We recommend Python 3.11 or 3.12 and a macOS/Linux shell. The following example imports a small document you create yourself, searches it, and exports a brief. **No pip packages, API keys, or models are needed for this Markdown/TXT workflow.**

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 -m venv .venv
source .venv/bin/activate

python3 tools/chubby.py init --vault "$PWD/creator-vault"
mkdir -p demo-input
cat > demo-input/sample.md <<'MARKDOWN'
---
title: Source library demo
---

# Source library demo

This is a manually written example. A source library keeps the original text
available so a writer can check context before using an excerpt.
MARKDOWN

python3 tools/chubby.py import demo-input/sample.md --no-enrich
python3 tools/chubby.py search "source library"
python3 tools/chubby.py brief --topic "source library" \
  --output "$PWD/creator-vault/30_Output/source-library-brief.md"
```

Open the imported note in `creator-vault/00_Inbox` and the brief in `creator-vault/30_Output`. The brief has a companion JSON file and points back to exact lines in the imported note. For this local example, provenance points to the original local file.

The import preserves the original document, copies supported local attachments, and updates the index. Repeating the same import can reuse a valid result; changing the document or its attachments creates a new result while retaining the old one. If you repeat the brief export, choose a different output filename or explicitly add `--force` to replace the previous brief.

To use your own files:

```bash
python3 tools/chubby.py import "/path/to/notes.md" --no-enrich
python3 tools/chubby.py import "/path/to/notes.txt" --no-enrich

# Optional dependency for PDFs that already contain a text layer:
python3 -m pip install 'pymupdf>=1.24'
python3 tools/chubby.py import "/path/to/report.pdf" --no-enrich
```

PDF import does **not** include OCR. Scanned PDFs without extractable text fail with an explanation. Use `--source-url` to record an original HTTP(S) source; it records provenance without downloading or verifying that page. See [document import](./docs/document-import.md) for attachment rules and [the creator workflow](./docs/creator-workflow.md) for the full capture-to-brief process.

## Work with your own material

### Platform links

Choose the runtime dependencies for the content you need. Run installation commands inside your active virtual environment:

| Content or operation | Setup |
|---|---|
| Local Markdown/TXT import, search, briefs | Python standard library; no additional setup |
| X/Xiaohongshu text and image posts | `bash setup.sh light` checks Python and prints configuration guidance; it does not install packages |
| Bilibili/YouTube captions | `python3 -m pip install yt-dlp` |
| Local video transcription | `bash setup.sh video`; requires system `ffmpeg` and installs transcription dependencies |
| Local podcast transcription | `bash setup.sh podcast`; installs `faster-whisper` dependencies |
| WeChat article/PDF processing | `bash setup.sh wechat` |

`setup.sh` handles runtime checks and selected dependencies; `tools/install_skill.py` builds skill directories. See [installation](./docs/installation.md) for all profiles, agent paths, and upgrade details.

For example, install the caption downloader, check YouTube requirements, and ingest a video you are allowed to save:

```bash
python3 -m pip install yt-dlp
python3 tools/chubby.py doctor --platform youtube
python3 tools/chubby.py ingest "REPLACE_WITH_YOUR_YOUTUBE_URL" --no-enrich
python3 tools/chubby.py status --latest
```

Platform capture is implemented for Bilibili, YouTube, Douyin, TikTok, Weibo, Zhihu, WeChat, Xiaohongshu, X/Twitter, and podcasts. Support varies by content type:

- **Bilibili/YouTube:** available captions first; audio transcription needs additional local dependencies when captions are unavailable.
- **Articles and image posts:** platform access, login state, and page changes can affect extraction. Manual-text fallback is recorded as manual input.
- **Video and audio:** local transcription needs its runtime/model dependencies and may take time. Check the corresponding skill before starting.

These are supported code paths, not a guarantee that every live link works. See [platform status](./docs/platform-status.md), the [dated live verification report](./docs/live-verification.md), and [failure/fallback guidance](./docs/platform-fallbacks.md).

### Podcasts and optional cloud transcription

To transcribe local audio with the local provider:

```bash
python3 tools/chubby.py ingest "/path/to/episode.mp3" \
  --skill podcast --provider local --no-enrich
```

Podcast transcription defaults to local `faster-whisper`. Atlas Cloud and MuAPI are **experimental, opt-in** providers. Their request lifecycle, saved task recovery, and error handling are tested with simulated responses; **real paid-service transcription has not been validated for v0.13.0**.

Cloud mode sends audio to the selected provider and may incur charges. Ordinary recovery resumes a saved task; `--resubmit` explicitly creates a new task and may charge again. Follow the [cloud transcription guide](./docs/cloud-transcription.md) for credentials, configuration, limits, and recovery.

Automatic podcast/RSS downloads accept only direct public HTTP(S) addresses, without redirects or proxies. For a source requiring either, download the audio yourself first and pass its local file path.

### Reuse, queues, and retries

Valid results are reused for the same source, processing settings, and destination. `--refresh` processes the source again while keeping previous versions. For batch capture, place one source per line in `inbox/links.txt`:

```bash
python3 tools/chubby.py run --queue inbox/links.txt --no-enrich
python3 tools/chubby.py status --failed
python3 tools/chubby.py retry --all-failed
```

The index updates after ingestion and before unified searches. See the [creator workflow](./docs/creator-workflow.md) for retry behavior and [knowledge automation](./docs/knowledge-automation.md) for index migration or rebuilding.

## Install skills for your agent

From the complete repository, install one skill into your agent's actual skills directory. For example, for Codex:

```bash
python3 tools/install_skill.py knowledge-base-management --dest ~/.codex/skills
```

This produces a self-contained skill directory, including its shared source modules and local import/index/brief tools. It can be moved as a unit without the original repository. **Do not download just a raw skill folder from GitHub:** it may reference modules elsewhere in the repository.

To browse the available skills or install all 14, use the following commands. **`--all` is an alternative to the single-skill installation above**, for a destination without existing copies of these skills:

```bash
python3 tools/install_skill.py --list
python3 tools/install_skill.py --all --dest /path/to/agent/skills
```

The installer refuses to overwrite existing skill directories. For an update, install into a new directory, compare changes, and retain your customizations before replacing the old copy. It does not install Python packages or configure/start your agent.

The `tools/chubby.py` workflow on this page requires the complete repository. An installed knowledge-base skill instead provides its own `tools/import_document.py`, `tools/vault_index.py`, and `tools/evidence_brief.py`; see [document import](./docs/document-import.md) for those commands.

### Connect the library through MCP

You can give the exported brief directly to an agent that can read files. Ask it to read the cited notes, distinguish source claims from its own inferences, and mark missing evidence. `brief` retrieves and quotes material; it does not generate a finished article or establish that a source's claims are true.

For direct library access, enable the optional MCP server using Python 3.10 or newer:

```bash
python3 -m pip install -r knowledge-base-management/requirements-mcp.txt
python3 tools/mcp_smoke.py --json
```

The requirements file pins the verified SDK to `mcp==1.30.0`. The smoke check starts a real server, completes the protocol handshake, and tests search/read calls against temporary notes.

Configure your actual client with the server command and `VAULT_DIR` pointing to the same library. Use the Python environment where you installed the MCP dependency. The [MCP guide](./docs/mcp-workflow.md) includes a client configuration example, all six tools, and standalone-skill setup; check the connection in your client too.

## Skills

| Skill | Purpose |
|---|---|
| [douyin-transcribe](./douyin-transcribe/SKILL.md) | Douyin video transcription |
| [bilibili-transcribe](./bilibili-transcribe/SKILL.md) | Bilibili captions and transcription |
| [tiktok-transcribe](./tiktok-transcribe/SKILL.md) | TikTok video transcription |
| [weibo-transcribe](./weibo-transcribe/SKILL.md) | Weibo video transcription |
| [zhihu-transcribe](./zhihu-transcribe/SKILL.md) | Zhihu video transcription |
| [youtube-transcribe](./youtube-transcribe/SKILL.md) | YouTube captions, transcription, optional translation |
| [podcast-transcribe](./podcast-transcribe/SKILL.md) | Podcasts, RSS, and local audio; optional cloud providers |
| [wechat-article-ingest](./wechat-article-ingest/SKILL.md) | WeChat articles and PDF ingestion |
| [xiaohongshu-ingest](./xiaohongshu-ingest/SKILL.md) | Xiaohongshu text, images, and video |
| [x-ingest](./x-ingest/SKILL.md) | X/Twitter text, images, and video |
| [content-enrich](./content-enrich/SKILL.md) | Optional API-based summaries, key points, and tags |
| [knowledge-base-management](./knowledge-base-management/SKILL.md) | Document import, indexing, briefs, and MCP |
| [industry-intelligence-radar](./industry-intelligence-radar/SKILL.md) | Multi-source research workflow |
| [learning-notes-automation](./learning-notes-automation/SKILL.md) | Learning notes and flashcards |

## Data and processing boundaries

Source material is stored locally by default. Network access depends on the operation:

| Operation | Where content is processed |
|---|---|
| Local import, keyword search, semantic-lite, briefs | Local; document import does not fetch remote attachments |
| Platform capture | The source platform; some paths need your own login state |
| Local transcription | Local inference; the first run may download a model |
| Optional enrichment, translation, learning-note extraction | The configured API, using `DEEPSEEK_API_KEY` |
| Optional OpenAI embeddings | OpenAI API, using `OPENAI_API_KEY` |
| Atlas/MuAPI transcription | The selected provider, using `ATLAS_API_KEY` or `MUAPI_API_KEY` |
| A cloud agent reading notes | The material it reads enters that agent's model context |

API services may charge. Keep credentials and cookies out of notes and version control. Other parsers can hand off Markdown to the local importer; see [optional integrations](./docs/integrations.md) for cue-omni-reader and its current verification status.

## Output format

Captures and imports use Markdown with frontmatter for the title, type, platform, source, and date. The unified CLI adds schema v1 metadata for task identity, capture time, source hashes, and attachments. See the [sample outputs](./examples/README.md).

```bash
python3 tools/validate_outputs.py output/ --schema-v1
```

## Verification and community contributions

The [v0.13.0 release](./docs/release-0.13.0.md) records **220 passing tests**, Linux/Python 3.11 and macOS/Python 3.12 CI, real PDF import, and real MCP protocol checks. The extracted release bundle was checked across **14 skills and 24 isolated script imports**. These checks cover the reported local behavior; they do not prove platform availability or real cloud transcription quality.

For a quick offline environment/workflow check:

```bash
python3 tools/chubby.py quickstart --ephemeral --no-state
```

The current implementation incorporates installation suggestions from [catwithtudou's #1](https://github.com/chubbyguan/chubbyskills/pull/1), Atlas requirements from [binyangzhu000-sudo's #3](https://github.com/chubbyguan/chubbyskills/pull/3), and MuAPI requirements from [Anil-matcha's #5](https://github.com/chubbyguan/chubbyskills/pull/5). [huhoo's #6](https://github.com/chubbyguan/chubbyskills/pull/6) is covered in the optional integration guide; a real parser example is still pending. See the [community triage record](./docs/community-triage.md) for attribution and decisions.

Issues and contributions are welcome. See [CONTRIBUTING](./CONTRIBUTING.md) and the [platform adapter guide](./docs/contributor-platform-adapter.md). Include reproducible inputs or errors without credentials or private content.

## Documentation

Most detailed guides are currently in Chinese.

| Guide | Use it for |
|---|---|
| [Creator workflow](./docs/creator-workflow.md) | Capture → search → evidence brief → agent handoff |
| [Document import](./docs/document-import.md) | File formats, attachments, provenance, and PDF limits |
| [Installation](./docs/installation.md) | Runtime dependencies and portable skill installation |
| [MCP configuration](./docs/mcp-workflow.md) | Connect an agent to your library |
| [Cloud transcription](./docs/cloud-transcription.md) | Atlas/MuAPI configuration and task recovery |
| [Knowledge automation](./docs/knowledge-automation.md) | Retrieval, optional embeddings, and archive/card workflows |
| [Optional integrations](./docs/integrations.md) | Import Markdown produced by other tools |
| [Community triage](./docs/community-triage.md) | Contribution attribution and adoption decisions |
| [Changelog](./CHANGELOG.md) | Changes by version |

## Usage limits

Ingestion skills are intended for personal learning and research. Follow platform terms, `robots.txt`, and applicable laws. Do not use them for bulk scraping, commercial scraping, redistribution, or infringing uses. Use only your own authorized login state. Source content remains the original author's work; obtain permission when required and attribute it appropriately.

Code is provided under the [MIT License](./LICENSE), as is. This does not grant rights to third-party content.

## About Chubby

I am Chubby. I create content, build a personal knowledge base, and share what I learn about AI agents, skills, and e-commerce.

[X/Twitter](https://x.com/Chubbyguan) · [Jike](https://web.okjike.com/u/a876838d-d9a8-494b-9494-bb3410b77dd5) · [Xiaohongshu](https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8) · WeChat: **关关不过**

[Gitee mirror](https://gitee.com/chubbyguan/chubbyskills) · Made by [@chubbyguan](https://github.com/chubbyguan)
