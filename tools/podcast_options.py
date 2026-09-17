"""Resolve podcast options without importing a model or making network calls."""

import argparse
import importlib.util
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[1] / "podcast-transcribe" / "scripts" / "provider_config.py"
CONFIG_OPTIONS = {"--provider", "--model", "--language", "--base-url", "--state-dir"}


def resolve_config(**kwargs):
    spec = importlib.util.spec_from_file_location("chubby_podcast_config", CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load podcast provider configuration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resolve_provider_config(**kwargs)


class OptionParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def resolve_extra(extra, default_state_dir=None):
    parser = OptionParser(add_help=False, allow_abbrev=False)
    for flag in sorted(CONFIG_OPTIONS):
        parser.add_argument(flag)
    options, remaining = parser.parse_known_args(list(extra))
    settings = resolve_config(provider=options.provider, model=options.model,
                              language=options.language, base_url=options.base_url,
                              state_dir=options.state_dir or default_state_dir)
    canonical = []
    for key in ("provider", "model", "language", "base_url", "state_dir"):
        if settings[key] or key == "language":
            canonical.extend(["--" + key.replace("_", "-"), str(settings[key])])
    return remaining + canonical, settings
