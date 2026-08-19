# Changelog

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
