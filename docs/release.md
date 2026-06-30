# Release Checklist

Current release: `0.10.0`

## Install Verification

```bash
bash setup.sh light
python3 tools/chubby.py --version
python3 tools/chubby.py quickstart --ephemeral --no-state
python3 tools/platform_smoke.py --mode all --check
python3 tools/golden_outputs.py examples/outputs
python3 tools/mcp_workflow_demo.py
```

## Optional Live Platform Smoke

Live smoke checks are intentionally opt-in because platform links, cookies, region limits, and heavy dependencies vary by machine.

```bash
export CHUBBY_SMOKE_X_SOURCE='https://x.com/<user>/status/<id>'
export CHUBBY_SMOKE_YOUTUBE_SOURCE='https://www.youtube.com/watch?v=<id>'
python3 tools/platform_smoke.py --mode live --check
```

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
