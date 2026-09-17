"""Network-free configuration shared by podcast CLI, batch runner and pipeline."""
from __future__ import annotations

import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

DEFAULT_MODELS = {"local": "small", "atlas": "bytedance/seed-asr-2.0", "muapi": "openai-whisper"}
DEFAULT_BASE_URLS = {"local": "", "atlas": "https://api.atlascloud.ai/api/v1", "muapi": "https://api.muapi.ai/api/v1"}


def validate_https_url(value: str, *, base: bool = False) -> str:
    """Reject credentials and ambiguous URLs before adding authentication."""
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
        raise ValueError("Cloud URL must be a valid HTTPS URL without credentials")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ValueError("Cloud URL must be a valid HTTPS URL without credentials") from None
    if (parts.scheme != "https" or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.fragment or "\\" in value
            or (base and parts.query) or (port is not None and not 0 < port <= 65535)):
        raise ValueError("Cloud URL must be HTTPS without userinfo, fragments or base query parameters")
    return urlunsplit(("https", parts.netloc.lower(), parts.path.rstrip("/") if base else parts.path, parts.query, ""))


def positive_seconds(value: float, label: str, maximum: float = 86400) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a finite positive number") from None
    if not math.isfinite(number) or number <= 0 or number > maximum:
        raise ValueError(f"{label} must be finite and in (0, {maximum}]")
    return number


def resolve_provider_config(provider=None, model=None, language=None, base_url=None, state_dir=None) -> dict:
    provider = provider or os.environ.get("PODCAST_TRANSCRIBE_PROVIDER") or "local"
    if provider not in DEFAULT_MODELS:
        raise ValueError("provider must be local, atlas or muapi")
    model = model or DEFAULT_MODELS[provider]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,199}", model) or ".." in model:
        raise ValueError("Invalid transcription model")
    if provider == "muapi" and "/" in model:
        raise ValueError("MuAPI model must be a single endpoint name")
    language = "zh" if language is None else language
    if not isinstance(language, str) or not re.fullmatch(r"[A-Za-z-]{0,32}", language):
        raise ValueError("language must be a language code or empty for automatic detection")
    if provider == "local":
        base_url = ""
    else:
        base_url = validate_https_url(base_url or os.environ.get(f"{provider.upper()}_BASE_URL") or DEFAULT_BASE_URLS[provider], base=True)
    default_state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "chubbyskills" / "podcast"
    state_dir = Path(state_dir or os.environ.get("CHUBBY_PODCAST_STATE_DIR") or default_state).expanduser().resolve()
    return {"provider": provider, "model": model, "language": language, "base_url": base_url, "state_dir": str(state_dir)}


def add_provider_arguments(parser) -> None:
    parser.add_argument("--provider", choices=tuple(DEFAULT_MODELS), default=None, help="Transcription provider (default: local; PODCAST_TRANSCRIBE_PROVIDER supported)")
    parser.add_argument("--model", default=None, help="Provider model (small / bytedance/seed-asr-2.0 / openai-whisper)")
    parser.add_argument("--language", default=None, help="Language code, default zh; empty enables automatic detection")
    parser.add_argument("--base-url", default=None, help="Explicit HTTPS API endpoint; persists across retries")
    parser.add_argument("--cloud-timeout", type=float, default=1800, help="Bounded cloud operation timeout in seconds")
    parser.add_argument("--poll-interval", type=float, default=3, help="Cloud poll interval in seconds")
    parser.add_argument("--state-dir", default=None, help="Persistent cloud jobs directory")
    parser.add_argument("--resubmit", action="store_true", help="Explicitly submit a new potentially billable cloud job, preserving old state")
