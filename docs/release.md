# Release Checklist

Current version: `0.12.0`. Release notes: [0.12.0](release-0.12.0.md).

## Install Verification

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt -r knowledge-base-management/requirements-mcp.txt
bash setup.sh light
python3 tools/chubby.py --version
python3 -m unittest discover -s tests -v
python3 tools/mcp_smoke.py --json
python3 tools/chubby.py quickstart --ephemeral --no-state
python3 tools/platform_smoke.py --mode all --check
python3 tools/golden_outputs.py examples/outputs
python3 tools/validate_outputs.py examples/outputs --schema-v1
python3 tools/platform_health.py --check
python3 tools/platform_health.py --check-output
ruff check . --select E,F,W --ignore E402,E501
git diff --check
```

Use Python 3.11 or 3.12. The suite covers relocated skill outputs and real YAML round trips; MCP smoke starts the actual server with a temporary vault. The general platform matrix checks offline/fallback paths; skipped live rows remain unverified.

## Optional Live Platform Smoke

Live smoke checks are intentionally opt-in because platform links, cookies, region limits, and heavy dependencies vary by machine.

```bash
export CHUBBY_SMOKE_X_SOURCE='https://x.com/<user>/status/<id>'
export CHUBBY_SMOKE_YOUTUBE_SOURCE='https://www.youtube.com/watch?v=<id>'
python3 tools/platform_smoke.py --mode live --platform x --platform youtube \
  --require-live --check --artifacts-dir runs/live-release --json
```

The manual GitHub workflow installs only text/subtitle dependencies, without ASR or cookies. A failure due to missing dependencies does not establish that a platform is broken. Inspect captured content and record the sample count; keep failed attempts. Local logs and captures may contain private or copyrighted content, so publish reviewed summaries instead of raw captures. See [live verification](live-verification.md).

## Portable skill asset and publication

1. Generate all 14 skill outputs in a fresh temporary directory using `python3 tools/install_skill.py --all --dest <temporary-directory>`.
2. Archive the directories as `chubbyskills-0.12.0-skills.tar.gz`, calculate SHA-256, then extract into a fresh directory and verify imports, installed knowledge-base MCP and `tools/evidence_brief.py --output` with Python isolated mode (`-I`).
3. Require the local gates and both GitHub CI matrix jobs to pass on the exact candidate commit before tagging it.
4. Publish release notes and verified assets, then confirm the remote commit/tag and asset checksum.

Each skill bundles local code, license and version manifest; Python/system packages remain separate. The creator-flow test uses explicitly marked manual text imports and real CLI processes. These checks do not measure real user adoption or establish remote platform availability.

## Embedding Providers

OpenAI:

```bash
export OPENAI_API_KEY='...'
python3 tools/vault_index.py --db .chubby/vault_index.sqlite embed /path/to/vault --provider openai
python3 tools/vault_index.py --db .chubby/vault_index.sqlite semantic "内容策略" --provider openai
```

Local model:

```bash
python3 -m pip install sentence-transformers
python3 tools/vault_index.py --db .chubby/vault_index.sqlite embed /path/to/vault --provider local
python3 tools/vault_index.py --db .chubby/vault_index.sqlite semantic "内容策略" --provider local
```
