# Changelog

## 0.13.0 - 2026-09-17

- Added local Markdown/text/PDF import with source provenance, referenced-asset handling, safe publication, attachment-aware reuse and automatic indexing.
- Added shared podcast provider configuration and optional experimental Atlas/MuAPI adapters while retaining the local default. Persisted jobs resume polling or reuse completed results; ambiguous submissions require explicit resubmission.
- Restricted authenticated HTTP redirects and endpoint validation; froze provider/model/endpoint/language in capture and retry context, and made resubmission a one-shot action.
- Made podcast dependency checks provider-aware and documented cloud processing boundaries.
- Closed the superseded installation PR #1 with implementation evidence and credit. Adapted the ideas/code from #3/#5 and documented #6 as an optional external integration with a local Markdown handoff.

## 0.12.0 - 2026-09-17

- Added incremental vault synchronization with vault identity checks, transactional updates and deletion handling. Unchanged embedding inputs retain their vectors; only missing vectors are generated. MCP refreshes the same index before queries.
- Added source-aware capture reuse and `--refresh`, isolated working directories, collision-safe Markdown/assets publication and preservation of previous captures.
- Retry inherits the original effective capture configuration, with explicit overrides; credential values are redacted and must be supplied again when necessary.
- Added `init --vault`, automatic indexing after capture/reuse, unified `search` and platform-specific dependency checks with meaningful failure exits.
- Added `brief --topic` to export local source excerpts, exact line ranges, source links and SHA-256 as Markdown and JSON. Generated briefs are excluded from their own candidate set; original notes cannot be overwritten by brief export.
- Bundled the brief helper in portable knowledge-base skills. Added CLI integration, migration, refresh, collision, retry and citation regression coverage.


## 0.11.1 - 2026-09-16

- Added a portable skill installer that bundles local dependencies, refuses to overwrite existing skills, and supports all 14 skills. Runtime setup now accepts every full skill directory name.
- Standardized all 14 skill frontmatters; custom fields live in string-valued `metadata` and are checked for Agent Skill compatibility.
- Fixed MCP fresh installs by pinning the optional SDK to `mcp==1.30.0`; added actionable startup errors and a real stdio handshake/search/read check, including portable knowledge-base installs.
- Fixed shared Markdown serialization for colons, quotes, line breaks, control characters and typed metadata; indexing preserves escaped text and JSON list values.
- Fixed YouTube empty titles when metadata extraction encounters unavailable formats. Pipeline success now requires valid output files and schema v1 metadata; error summaries retain the final failure reason.
- Added selected-platform live checks with persistent local logs, output hashes and timestamps. Empty/skipped live evidence cannot pass `--require-live --check`.
- Added Linux/Python 3.11 and macOS/Python 3.12 CI plus a manual text/subtitle workflow. Offline checks, real-source observations and user evidence are documented separately.
- Replaced unsupported positioning claims with a creator workflow, real-source verification notes, community triage and a ten-person pilot template with no claimed participants.
- Installation clarification was informed by [PR #1](https://github.com/chubbyguan/chubbyskills/pull/1). MCP compatibility addresses [Issue #4](https://github.com/chubbyguan/chubbyskills/issues/4).

## 0.11.0 - 2026-08-19

- Added `chubby_common/` shared module: platform config, yt-dlp wrapper (with retry and dependency checks), SenseVoice transcription wrapper, unified Markdown generation, VTT subtitle parsing, and LLM JSON tolerance helpers.
- Refactored tiktok/weibo/zhihu transcribe scripts onto the shared module (removed ~400 lines of copy-paste), and bilibili/youtube/douyin now reuse shared yt-dlp / funasr / vtt components.
- Added friendly dependency checks: missing yt-dlp / ffmpeg / funasr now prints an install hint (pointing at `setup.sh` tiers) instead of a raw traceback.
- Hardened LLM call sites (content-enrich, analyze_hook, learning-notes-automation): tolerant JSON parsing with extraction fallback and readable errors, safe int coercion for model outputs.
- Fixed douyin downloader: page-structure changes now raise a readable error, standalone mode cleans up temp files, and ffmpeg is pre-checked.
- Fixed podcast RSS parsing crash when title/pubDate/duration tags are missing.
- Removed dual source of truth: `tools/chubby_ingest.py` now builds the skill route table from `platforms/*.yaml` (with a static fallback table).
- Added `tests/test_chubby_common.py` covering the shared module (16 new tests, 56 total).

## 0.10.0 - 2026-06-30

- Added deterministic platform smoke matrix with offline, fallback, and optional live layers.
- Added per-platform failure modes and fallback commands.
- Added golden output snapshots for reproducible fixtures.
- Added OpenAI and local embedding provider support for vault semantic search.
- Added MCP workflow demo that uses a vault to complete an Agent-style task.
- Added release checklist and versioned install verification path.
