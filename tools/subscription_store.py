"""Configuration and durable SQLite state for Chubby subscription P0."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CONFIG_SCHEMA_VERSION = 1
DATABASE_SCHEMA_VERSION = 3
SOURCE_KINDS = {"feed", "youtube_channel"}
PROVIDERS = {"native", "rsshub_byo", "rssbridge_byo", "generic_byo"}
# Claims are liveness-based: a worker heartbeats while transcribing, so the
# stale threshold only fires after a real crash, not a long transcription.
CLAIM_STALE_SECONDS = 6 * 3600
MODES = {"auto_ingest", "discover_only", "disabled"}
ENTRY_STATES = {
    "seen",
    "discovered",
    "queued",
    "ingesting",
    "succeeded",
    "retry_wait",
    "index_retry",
    "failed_terminal",
    "skipped",
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
SENSITIVE_KEY_RE = re.compile(
    r"(?:cookie|token|password|passwd|secret|authorization|credential|api[_-]?key)",
    re.IGNORECASE,
)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}


class SubscriptionError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def jitter_seconds(seed: str, span_seconds: int) -> int:
    """Deterministic per-source jitter in [0, span_seconds], anti-thundering-herd."""
    if span_seconds <= 0:
        return 0
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (span_seconds + 1)


def default_provider(kind: str) -> str:
    return "native" if kind == "youtube_channel" else "generic_byo"


def default_document() -> dict[str, Any]:
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "defaults": {
            "poll_minutes": 240,
            "max_new_per_sync": 3,
            "mode": "discover_only",
            "process_limit_per_tick": 3,
        },
        "subscriptions": [],
    }


def config_path(root: Path, override: str | None = None) -> Path:
    path = (
        Path(override).expanduser()
        if override
        else root / ".chubby" / "subscriptions.json"
    )
    return path.resolve()


def state_path(vault_root: Path) -> Path:
    return vault_root.resolve() / ".chubby" / "subscriptions.sqlite"


def _json_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_document()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubscriptionError(
            f"cannot read subscription config {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SubscriptionError("subscription config root must be a JSON object")
    return data


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    handle, staging = tempfile.mkstemp(
        prefix="subscriptions-", suffix=".json", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    except Exception:
        Path(staging).unlink(missing_ok=True)
        raise


def _unknown_keys(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise SubscriptionError(f"unknown {where} field(s): {', '.join(unknown)}")


def _positive_int(value: Any, key: str, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise SubscriptionError(
            f"{key} must be an integer between {minimum} and {maximum}"
        )
    return value


def _safe_public_https(url: Any, key: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise SubscriptionError(f"{key} must be a non-empty HTTPS URL")
    parsed = urlsplit(url.strip())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise SubscriptionError(f"{key} must be an HTTPS URL without credentials")
    if parsed.port not in {None, 443}:
        raise SubscriptionError(f"{key} may only use HTTPS port 443")
    for query_key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if SENSITIVE_KEY_RE.search(query_key):
            raise SubscriptionError(
                f"{key} must not contain credential-like query parameters"
            )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _validate_regexes(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise SubscriptionError(f"{field} must be an array of non-empty regex strings")
    if any(len(item) > 240 for item in value):
        raise SubscriptionError(f"{field} regex is too long")
    for item in value:
        try:
            re.compile(item)
        except re.error as exc:
            raise SubscriptionError(f"invalid regex in {field}: {exc}") from exc
    return value


def _validate_policy(
    value: Any, defaults: dict[str, Any], label: str
) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise SubscriptionError(f"{label}.policy must be an object")
    _unknown_keys(
        value,
        {
            "poll_minutes",
            "max_new_per_sync",
            "include_title_regex",
            "exclude_title_regex",
            "content_profile",
            "initial_sync",
            "user_agent",
        },
        f"{label}.policy",
    )
    result = dict(value)
    result["poll_minutes"] = _positive_int(
        result.get("poll_minutes", defaults["poll_minutes"]),
        f"{label}.policy.poll_minutes",
        60,
        1440,
    )
    result["max_new_per_sync"] = _positive_int(
        result.get("max_new_per_sync", defaults["max_new_per_sync"]),
        f"{label}.policy.max_new_per_sync",
        1,
        10,
    )
    result["include_title_regex"] = _validate_regexes(
        result.get("include_title_regex", []), f"{label}.policy.include_title_regex"
    )
    result["exclude_title_regex"] = _validate_regexes(
        result.get("exclude_title_regex", []), f"{label}.policy.exclude_title_regex"
    )
    profile = result.get("content_profile", "auto")
    if profile not in {"auto", "video", "podcast", "article"}:
        raise SubscriptionError(
            f"{label}.policy.content_profile must be auto, video, podcast or article"
        )
    result["content_profile"] = profile
    initial_sync = result.get("initial_sync", "from_now")
    if initial_sync not in {"from_now", "backfill"}:
        raise SubscriptionError(
            f"{label}.policy.initial_sync must be from_now or backfill"
        )
    result["initial_sync"] = initial_sync
    user_agent = result.get("user_agent", "")
    if user_agent is None:
        user_agent = ""
    if not isinstance(user_agent, str) or len(user_agent.strip()) > 200:
        raise SubscriptionError(f"{label}.policy.user_agent must be a string up to 200 characters")
    result["user_agent"] = user_agent.strip()
    return result


def validate_document(data: dict[str, Any]) -> dict[str, Any]:
    _unknown_keys(
        data, {"schema_version", "defaults", "subscriptions"}, "subscription config"
    )
    if data.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise SubscriptionError(
            f"subscription schema_version must be {CONFIG_SCHEMA_VERSION}"
        )
    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        raise SubscriptionError("defaults must be an object")
    _unknown_keys(
        defaults,
        {"poll_minutes", "max_new_per_sync", "mode", "process_limit_per_tick"},
        "defaults",
    )
    normalized_defaults = dict(defaults)
    normalized_defaults["poll_minutes"] = _positive_int(
        normalized_defaults.get("poll_minutes", 240), "defaults.poll_minutes", 60, 1440
    )
    normalized_defaults["max_new_per_sync"] = _positive_int(
        normalized_defaults.get("max_new_per_sync", 3),
        "defaults.max_new_per_sync",
        1,
        10,
    )
    normalized_defaults["process_limit_per_tick"] = _positive_int(
        normalized_defaults.get("process_limit_per_tick", 3),
        "defaults.process_limit_per_tick",
        1,
        10,
    )
    if normalized_defaults.get("mode", "discover_only") not in MODES - {"disabled"}:
        raise SubscriptionError("defaults.mode must be auto_ingest or discover_only")
    normalized_defaults["mode"] = normalized_defaults.get("mode", "discover_only")
    subscriptions = data.get("subscriptions")
    if not isinstance(subscriptions, list):
        raise SubscriptionError("subscriptions must be an array")
    normalized = []
    seen_ids = set()
    for index, item in enumerate(subscriptions):
        label = f"subscriptions[{index}]"
        if not isinstance(item, dict):
            raise SubscriptionError(f"{label} must be an object")
        _unknown_keys(
            item,
            {"id", "name", "kind", "provider", "enabled", "mode", "config", "policy"},
            label,
        )
        item_id = item.get("id")
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            raise SubscriptionError(f"{label}.id must match {ID_RE.pattern}")
        if item_id in seen_ids:
            raise SubscriptionError(f"duplicate subscription id: {item_id}")
        seen_ids.add(item_id)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise SubscriptionError(
                f"{label}.name must be a non-empty string up to 120 characters"
            )
        kind = item.get("kind")
        if kind not in SOURCE_KINDS:
            raise SubscriptionError(
                f"{label}.kind must be one of: {', '.join(sorted(SOURCE_KINDS))}"
            )
        provider = item.get("provider", default_provider(kind))
        if provider not in PROVIDERS:
            raise SubscriptionError(
                f"{label}.provider must be one of: {', '.join(sorted(PROVIDERS))}"
            )
        if kind == "youtube_channel" and provider != "native":
            raise SubscriptionError(
                f"{label}.provider must be native for youtube_channel"
            )
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise SubscriptionError(f"{label}.enabled must be boolean")
        mode = item.get("mode", normalized_defaults["mode"])
        if mode not in MODES:
            raise SubscriptionError(
                f"{label}.mode must be one of: {', '.join(sorted(MODES))}"
            )
        source_config = item.get("config")
        if not isinstance(source_config, dict):
            raise SubscriptionError(f"{label}.config must be an object")
        if kind == "feed":
            _unknown_keys(source_config, {"feed_url", "format"}, f"{label}.config")
            source_config = dict(source_config)
            source_config["feed_url"] = _safe_public_https(
                source_config.get("feed_url"), f"{label}.config.feed_url"
            )
            source_config["format"] = source_config.get("format", "auto")
            if source_config["format"] not in {"auto", "rss", "atom", "json"}:
                raise SubscriptionError(
                    f"{label}.config.format must be auto, rss, atom or json"
                )
        else:
            _unknown_keys(source_config, {"channel_id"}, f"{label}.config")
            channel = source_config.get("channel_id")
            if (
                not isinstance(channel, str)
                or not channel.strip()
                or any(char.isspace() for char in channel)
            ):
                raise SubscriptionError(f"{label}.config.channel_id is required")
            source_config = {"channel_id": channel.strip()}
        normalized.append(
            {
                "id": item_id,
                "name": name.strip(),
                "kind": kind,
                "provider": provider,
                "enabled": enabled,
                "mode": mode,
                "config": source_config,
                "policy": _validate_policy(
                    item.get("policy"), normalized_defaults, label
                ),
            }
        )
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "defaults": normalized_defaults,
        "subscriptions": normalized,
    }


def load_document(path: Path) -> dict[str, Any]:
    return validate_document(_json_load(path))


def save_document(path: Path, document: dict[str, Any]) -> dict[str, Any]:
    valid = validate_document(document)
    atomic_write_json(path, valid)
    return valid


def config_digest(subscription: dict[str, Any]) -> str:
    material = dict(subscription)
    # Provider provenance and the optional user_agent default do not change
    # content identity; upgrading must not reset existing cursors.
    material.pop("provider", None)
    policy = dict(material.get("policy") or {})
    if not policy.get("user_agent"):
        policy.pop("user_agent", None)
    material["policy"] = policy
    data = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def canonical_url(value: str) -> str:
    """Strip standard tracking tokens while preserving meaningful query values."""

    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    pairs = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            urlencode(pairs, doseq=True),
            "",
        )
    )


def entry_key(entry: dict[str, Any]) -> str:
    external_id = str(entry.get("external_id") or "").strip()
    if external_id:
        material = "id:" + external_id
    elif entry.get("enclosure_url"):
        material = "enclosure:" + canonical_url(str(entry["enclosure_url"]))
    elif entry.get("url"):
        material = "url:" + canonical_url(str(entry["url"]))
    else:
        material = (
            "fallback:"
            + str(entry.get("title") or "")
            + "\n"
            + str(entry.get("published_at") or "")
        )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class SubscriptionStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def session(self):
        """commit-on-success connection that is always closed.

        `with self.connect()` only commits — the connection (and its file
        descriptor) stays open until GC. Long ticks with a heartbeat thread
        otherwise leak descriptors into launchd's low file limit.
        """
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.session() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version > DATABASE_SCHEMA_VERSION:
                raise SubscriptionError(
                    f"subscription database version {version} is newer than supported {DATABASE_SCHEMA_VERSION}"
                )
            if version == 0:
                con.executescript("""
                CREATE TABLE source_state (
                  subscription_id TEXT PRIMARY KEY,
                  config_hash TEXT NOT NULL,
                  initialized_at TEXT,
                  last_checked_at TEXT,
                  last_success_at TEXT,
                  next_due_at TEXT NOT NULL,
                  etag TEXT,
                  last_modified TEXT,
                  error_streak INTEGER NOT NULL DEFAULT 0,
                  last_error_code TEXT,
                  last_error TEXT,
                  lease_token TEXT,
                  lease_expires_at TEXT
                );
                CREATE TABLE entries (
                  id INTEGER PRIMARY KEY,
                  subscription_id TEXT NOT NULL,
                  entry_key TEXT NOT NULL,
                  external_id TEXT,
                  canonical_url TEXT,
                  title TEXT NOT NULL,
                  author TEXT,
                  published_at TEXT,
                  updated_at TEXT,
                  content_kind TEXT NOT NULL,
                  completeness TEXT NOT NULL,
                  content_html TEXT,
                  summary_html TEXT,
                  enclosure_url TEXT,
                  raw_payload_json TEXT,
                  discovered_at TEXT NOT NULL,
                  state TEXT NOT NULL,
                  skip_reason TEXT,
                  queued_at TEXT,
                  claimed_at TEXT,
                  completed_at TEXT,
                  attempt_count INTEGER NOT NULL DEFAULT 0,
                  next_retry_at TEXT,
                  last_run_id TEXT,
                  output_path TEXT,
                  last_error_code TEXT,
                  last_error TEXT,
                  claim_token TEXT,
                  heartbeat_at TEXT,
                  UNIQUE(subscription_id, entry_key)
                );
                CREATE TABLE entry_attempts (
                  id INTEGER PRIMARY KEY,
                  entry_id INTEGER NOT NULL REFERENCES entries(id),
                  attempt_no INTEGER NOT NULL,
                  started_at TEXT NOT NULL,
                  finished_at TEXT,
                  outcome TEXT NOT NULL,
                  run_id TEXT,
                  error_code TEXT,
                  error TEXT,
                  UNIQUE(entry_id, attempt_no)
                );
                CREATE TABLE scheduler_locks (
                  name TEXT PRIMARY KEY,
                  owner_token TEXT NOT NULL,
                  acquired_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                );
                CREATE INDEX entries_ready_idx ON entries(state, next_retry_at, queued_at);
                CREATE INDEX entries_source_idx ON entries(subscription_id, published_at DESC);
                PRAGMA user_version = 1;
                """)
                version = 1
            if version == 1:
                con.executescript("""
                CREATE TABLE IF NOT EXISTS source_checks (
                  id INTEGER PRIMARY KEY,
                  subscription_id TEXT NOT NULL,
                  checked_at TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  outcome TEXT NOT NULL CHECK(outcome IN ('success', 'unchanged', 'error')),
                  http_status INTEGER,
                  entries_parsed INTEGER NOT NULL DEFAULT 0,
                  new_entries INTEGER NOT NULL DEFAULT 0,
                  duplicate_entries INTEGER NOT NULL DEFAULT 0,
                  queued_entries INTEGER NOT NULL DEFAULT 0,
                  discovered_entries INTEGER NOT NULL DEFAULT 0,
                  baseline_entries INTEGER NOT NULL DEFAULT 0,
                  skipped_entries INTEGER NOT NULL DEFAULT 0,
                  error_code TEXT,
                  error TEXT
                );
                CREATE INDEX IF NOT EXISTS source_checks_source_time_idx
                  ON source_checks(subscription_id, checked_at DESC);
                PRAGMA user_version = 2;
                """)
                version = 2
            if version == 2:
                columns = {
                    row["name"]
                    for row in con.execute("PRAGMA table_info(entries)").fetchall()
                }
                if "claim_token" not in columns:
                    con.execute("ALTER TABLE entries ADD COLUMN claim_token TEXT")
                if "heartbeat_at" not in columns:
                    con.execute("ALTER TABLE entries ADD COLUMN heartbeat_at TEXT")
                con.execute("PRAGMA user_version = 3")
                version = 3
            if version != DATABASE_SCHEMA_VERSION:
                raise SubscriptionError(
                    f"subscription database migration stopped at version {version}"
                )

    def ensure_sources(
        self, subscriptions: Iterable[dict[str, Any]], *, now: str | None = None
    ) -> None:
        stamp = now or now_iso()
        with self.session() as con:
            for subscription in subscriptions:
                item_id = subscription["id"]
                digest = config_digest(subscription)
                # Spread first syncs per source; a fresh batch of subscriptions
                # must not fire at the same second.
                first_due = (
                    parse_iso(stamp)
                    + timedelta(
                        seconds=jitter_seconds(
                            item_id, subscription["policy"]["poll_minutes"] * 60
                        )
                    )
                ).isoformat()
                row = con.execute(
                    "SELECT config_hash FROM source_state WHERE subscription_id = ?",
                    (item_id,),
                ).fetchone()
                if row is None:
                    con.execute(
                        "INSERT INTO source_state (subscription_id, config_hash, next_due_at) VALUES (?, ?, ?)",
                        (item_id, digest, first_due),
                    )
                elif row["config_hash"] != digest:
                    con.execute(
                        "UPDATE source_state SET config_hash = ?, next_due_at = ?, etag = NULL, last_modified = NULL, error_streak = 0, last_error_code = NULL, last_error = NULL WHERE subscription_id = ?",
                        (digest, first_due, item_id),
                    )

    def state_for(self, subscription_id: str) -> dict[str, Any]:
        with self.session() as con:
            row = con.execute(
                "SELECT * FROM source_state WHERE subscription_id = ?",
                (subscription_id,),
            ).fetchone()
        return dict(row) if row else {}

    def due_subscriptions(
        self,
        subscriptions: Iterable[dict[str, Any]],
        *,
        now: str | None = None,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        stamp = parse_iso(now or now_iso())
        self.ensure_sources(subscriptions, now=stamp.isoformat())
        result = []
        for subscription in subscriptions:
            if not subscription["enabled"] or subscription["mode"] == "disabled":
                continue
            state = self.state_for(subscription["id"])
            if force or parse_iso(state["next_due_at"]) <= stamp:
                result.append(subscription)
        return result

    def acquire_lock(
        self, name: str, *, seconds: int, now: str | None = None
    ) -> str | None:
        stamp = parse_iso(now or now_iso())
        token = uuid.uuid4().hex
        expires = (stamp + timedelta(seconds=seconds)).isoformat()
        with self.session() as con:
            row = con.execute(
                "SELECT expires_at FROM scheduler_locks WHERE name = ?", (name,)
            ).fetchone()
            if row and parse_iso(row["expires_at"]) > stamp:
                return None
            con.execute(
                "INSERT INTO scheduler_locks(name, owner_token, acquired_at, expires_at) VALUES (?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET owner_token=excluded.owner_token, acquired_at=excluded.acquired_at, expires_at=excluded.expires_at",
                (name, token, stamp.isoformat(), expires),
            )
        return token

    def release_lock(self, name: str, token: str) -> None:
        with self.session() as con:
            con.execute(
                "DELETE FROM scheduler_locks WHERE name = ? AND owner_token = ?",
                (name, token),
            )

    def acquire_source_lease(
        self, subscription_id: str, *, seconds: int = 900, now: str | None = None
    ) -> str | None:
        stamp = parse_iso(now or now_iso())
        token = uuid.uuid4().hex
        expires = (stamp + timedelta(seconds=seconds)).isoformat()
        with self.session() as con:
            row = con.execute(
                "SELECT lease_expires_at FROM source_state WHERE subscription_id = ?",
                (subscription_id,),
            ).fetchone()
            if not row:
                return None
            if row["lease_expires_at"] and parse_iso(row["lease_expires_at"]) > stamp:
                return None
            con.execute(
                "UPDATE source_state SET lease_token = ?, lease_expires_at = ? WHERE subscription_id = ?",
                (token, expires, subscription_id),
            )
        return token

    def release_source_lease(self, subscription_id: str, token: str) -> None:
        with self.session() as con:
            con.execute(
                "UPDATE source_state SET lease_token = NULL, lease_expires_at = NULL WHERE subscription_id = ? AND lease_token = ?",
                (subscription_id, token),
            )

    def mark_source_success(
        self,
        subscription: dict[str, Any],
        *,
        etag: str,
        last_modified: str,
        not_modified: bool = False,
        now: str | None = None,
    ) -> None:
        stamp = parse_iso(now or now_iso())
        poll_seconds = subscription["policy"]["poll_minutes"] * 60
        due = (
            stamp
            + timedelta(
                seconds=poll_seconds
                + jitter_seconds(subscription["id"], poll_seconds // 10)
            )
        ).isoformat()
        with self.session() as con:
            con.execute(
                "UPDATE source_state SET initialized_at = COALESCE(initialized_at, ?), last_checked_at = ?, last_success_at = ?, next_due_at = ?, etag = ?, last_modified = ?, error_streak = 0, last_error_code = NULL, last_error = NULL WHERE subscription_id = ?",
                (
                    stamp.isoformat(),
                    stamp.isoformat(),
                    stamp.isoformat(),
                    due,
                    etag,
                    last_modified,
                    subscription["id"],
                ),
            )

    def mark_source_error(
        self,
        subscription_id: str,
        code: str,
        message: str,
        *,
        retry_after: int | None = None,
        pause: bool = False,
        now: str | None = None,
    ) -> None:
        stamp = parse_iso(now or now_iso())
        with self.session() as con:
            state = con.execute(
                "SELECT error_streak FROM source_state WHERE subscription_id = ?",
                (subscription_id,),
            ).fetchone()
            streak = int(state["error_streak"] if state else 0) + 1
            delay_seconds = min(24 * 3600, 3600 * (2 ** (streak - 1)))
            if retry_after is not None:
                delay_seconds = max(delay_seconds, retry_after)
            if pause:
                delay_seconds = 365 * 24 * 3600
            else:
                delay_seconds += jitter_seconds(subscription_id, delay_seconds // 10)
            due = (stamp + timedelta(seconds=delay_seconds)).isoformat()
            con.execute(
                "UPDATE source_state SET last_checked_at = ?, next_due_at = ?, error_streak = ?, last_error_code = ?, last_error = ? WHERE subscription_id = ?",
                (stamp.isoformat(), due, streak, code, message[:800], subscription_id),
            )

    def record_source_check(
        self,
        subscription_id: str,
        *,
        provider: str,
        outcome: str,
        http_status: int | None = None,
        entries_parsed: int = 0,
        new_entries: int = 0,
        duplicate_entries: int = 0,
        queued_entries: int = 0,
        discovered_entries: int = 0,
        baseline_entries: int = 0,
        skipped_entries: int = 0,
        error_code: str = "",
        error: str = "",
        now: str | None = None,
    ) -> None:
        if outcome not in {"success", "unchanged", "error"}:
            raise SubscriptionError(f"invalid source check outcome: {outcome}")
        values = (
            subscription_id,
            now or now_iso(),
            provider,
            outcome,
            http_status,
            entries_parsed,
            new_entries,
            duplicate_entries,
            queued_entries,
            discovered_entries,
            baseline_entries,
            skipped_entries,
            error_code or None,
            error[:800] or None,
        )
        with self.session() as con:
            con.execute(
                "INSERT INTO source_checks(subscription_id, checked_at, provider, outcome, http_status, entries_parsed, new_entries, duplicate_entries, queued_entries, discovered_entries, baseline_entries, skipped_entries, error_code, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )

    def is_initialized(self, subscription_id: str) -> bool:
        return bool(self.state_for(subscription_id).get("initialized_at"))

    def has_entry(self, subscription_id: str, entry: dict[str, Any]) -> bool:
        with self.session() as con:
            row = con.execute(
                "SELECT 1 FROM entries WHERE subscription_id = ? AND entry_key = ?",
                (subscription_id, entry_key(entry)),
            ).fetchone()
        return row is not None

    def insert_entry(
        self,
        subscription_id: str,
        entry: dict[str, Any],
        *,
        state: str,
        skip_reason: str = "",
        now: str | None = None,
    ) -> tuple[int, bool]:
        if state not in ENTRY_STATES:
            raise SubscriptionError(f"invalid entry state: {state}")
        stamp = now or now_iso()
        key = entry_key(entry)
        raw = json.dumps(entry.get("raw") or {}, ensure_ascii=False, sort_keys=True)
        if len(raw.encode("utf-8")) > 256 * 1024:
            raw = json.dumps({"truncated": True}, ensure_ascii=False)
        content = str(entry.get("content_html") or "")
        summary = str(entry.get("summary_html") or "")
        completeness = "full" if content else "summary"
        content_kind = str(entry.get("content_kind") or "article")
        url = canonical_url(str(entry.get("url") or ""))
        with self.session() as con:
            con.execute(
                "INSERT OR IGNORE INTO entries(subscription_id, entry_key, external_id, canonical_url, title, author, published_at, updated_at, content_kind, completeness, content_html, summary_html, enclosure_url, raw_payload_json, discovered_at, state, skip_reason, queued_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    subscription_id,
                    key,
                    str(entry.get("external_id") or ""),
                    url,
                    str(entry.get("title") or "Untitled feed entry"),
                    str(entry.get("author") or ""),
                    str(entry.get("published_at") or ""),
                    str(entry.get("updated_at") or ""),
                    content_kind,
                    completeness,
                    content,
                    summary,
                    str(entry.get("enclosure_url") or ""),
                    raw,
                    stamp,
                    state,
                    skip_reason,
                    stamp if state == "queued" else None,
                ),
            )
            row = con.execute(
                "SELECT id FROM entries WHERE subscription_id = ? AND entry_key = ?",
                (subscription_id, key),
            ).fetchone()
            created = con.execute("SELECT changes()").fetchone()[0] == 1
        return int(row["id"]), created

    def promote(self, entry_ids: Iterable[int], *, now: str | None = None) -> int:
        stamp = now or now_iso()
        ids = [int(item) for item in entry_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self.session() as con:
            con.execute(
                f"UPDATE entries SET state='queued', queued_at=?, skip_reason=NULL, next_retry_at=NULL WHERE id IN ({placeholders}) AND state IN ('discovered', 'retry_wait', 'index_retry', 'seen')",
                (stamp, *ids),
            )
            return con.execute("SELECT changes()").fetchone()[0]

    def deferred_entry_ids(self, budgets: dict[str, int]) -> list[int]:
        """Discovered entries the per-sync budget pushed aside.

        `_sync_one` writes anything past `max_new_per_sync` as `discovered`
        with skip_reason 'max_new_per_sync'. A later sync sees those rows as
        duplicates and skips them, so nothing ever revisits the decision: on a
        source that publishes in bursts, the surplus waits for a manual
        `promote` indefinitely. A scheduled tick drains up to the same budget
        per source, which keeps the pacing the budget exists for while letting
        the backlog clear itself.
        """
        if not budgets:
            return []
        with self.session() as con:
            rows = con.execute(
                "SELECT id, subscription_id FROM entries "
                "WHERE state = 'discovered' AND skip_reason = 'max_new_per_sync' "
                "ORDER BY id"
            ).fetchall()
        taken: dict[str, int] = {}
        selected = []
        for row in rows:
            source = row["subscription_id"]
            limit = int(budgets.get(source, 0))
            if taken.get(source, 0) >= limit:
                continue
            taken[source] = taken.get(source, 0) + 1
            selected.append(row["id"])
        return selected

    def requeue_terminal(self, entry_ids: Iterable[int], *, now: str | None = None) -> int:
        """Requeue failed_terminal entries after an environment fix.

        attempt_count is aligned with the attempts journal so the next claim
        does not collide with recorded attempts.
        """
        stamp = now or now_iso()
        ids = [int(item) for item in entry_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self.session() as con:
            con.execute(
                f"""UPDATE entries SET state='queued', queued_at=?, next_retry_at=NULL,
                    claim_token=NULL, heartbeat_at=NULL, last_error_code=NULL, last_error=NULL,
                    completed_at=NULL,
                    attempt_count=COALESCE((SELECT MAX(attempt_no) FROM entry_attempts WHERE entry_id=entries.id), 0)
                    WHERE id IN ({placeholders}) AND state='failed_terminal'""",
                (stamp, *ids),
            )
            return con.execute("SELECT changes()").fetchone()[0]

    def skip(
        self, entry_ids: Iterable[int], reason: str, *, now: str | None = None
    ) -> int:
        ids = [int(item) for item in entry_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self.session() as con:
            con.execute(
                f"UPDATE entries SET state='skipped', skip_reason=?, completed_at=? WHERE id IN ({placeholders}) AND state IN ('discovered', 'queued', 'retry_wait')",
                (reason[:240], now or now_iso(), *ids),
            )
            return con.execute("SELECT changes()").fetchone()[0]

    def reclaim_expired_claims(self, *, now: str | None = None) -> int:
        stamp = parse_iso(now or now_iso())
        stale_before = (stamp - timedelta(seconds=CLAIM_STALE_SECONDS)).isoformat()
        with self.session() as con:
            con.execute(
                "UPDATE entries SET state='retry_wait', next_retry_at=?, last_error_code='lease_expired', last_error='previous entry claim expired' WHERE state='ingesting' AND COALESCE(heartbeat_at, claimed_at) < ?",
                (stamp.isoformat(), stale_before),
            )
            return con.execute("SELECT changes()").fetchone()[0]

    def heartbeat(self, entry_id: int, token: str, *, now: str | None = None) -> bool:
        if not token:
            return False
        with self.session() as con:
            con.execute(
                "UPDATE entries SET heartbeat_at=? WHERE id=? AND claim_token=? AND state='ingesting'",
                (now or now_iso(), entry_id, token),
            )
            return con.execute("SELECT changes()").fetchone()[0] == 1

    def claim_entries(
        self,
        limit: int,
        *,
        subscription_id: str | None = None,
        include_retry: bool = False,
        now: str | None = None,
    ) -> list[dict[str, Any]]:
        stamp = now or now_iso()
        retry_clause = ""
        params: list[Any] = []
        if include_retry:
            retry_clause = (
                " OR (state IN ('retry_wait', 'index_retry') AND next_retry_at <= ?)"
            )
            params.append(stamp)
        filter_sql = ""
        if subscription_id:
            filter_sql = " AND subscription_id = ?"
            params.append(subscription_id)
        params.append(limit)
        with self.session() as con:
            rows = con.execute(
                f"SELECT * FROM entries WHERE (state='queued'{retry_clause}) {filter_sql} ORDER BY queued_at ASC, id ASC LIMIT ?",
                tuple(params),
            ).fetchall()
            claimed = []
            for row in rows:
                attempt = int(row["attempt_count"]) + 1
                token = uuid.uuid4().hex
                con.execute(
                    "UPDATE entries SET state='ingesting', claimed_at=?, heartbeat_at=?, claim_token=?, attempt_count=? WHERE id=? AND state IN ('queued','retry_wait','index_retry')",
                    (stamp, stamp, token, attempt, row["id"]),
                )
                if con.execute("SELECT changes()").fetchone()[0]:
                    con.execute(
                        "INSERT INTO entry_attempts(entry_id, attempt_no, started_at, outcome) VALUES (?, ?, ?, 'running')",
                        (row["id"], attempt, stamp),
                    )
                    updated = dict(row)
                    updated["attempt_count"] = attempt
                    updated["state_before_claim"] = row["state"]
                    updated["claim_token"] = token
                    claimed.append(updated)
        return claimed

    def finish_entry(
        self,
        entry_id: int,
        *,
        outcome: str,
        run_id: str = "",
        output_path: str = "",
        error_code: str = "",
        error: str = "",
        now: str | None = None,
    ) -> None:
        stamp = parse_iso(now or now_iso())
        with self.session() as con:
            row = con.execute(
                "SELECT attempt_count FROM entries WHERE id = ?", (entry_id,)
            ).fetchone()
            if not row:
                return
            attempts = int(row["attempt_count"])
            if outcome == "succeeded":
                state, next_retry = "succeeded", None
            elif outcome == "index_retry":
                state, next_retry = "index_retry", stamp.isoformat()
            elif attempts >= 3:
                state, next_retry = "failed_terminal", None
            else:
                state = "retry_wait"
                next_retry = (
                    stamp + timedelta(minutes=15 * (2 ** (attempts - 1)))
                ).isoformat()
            con.execute(
                "UPDATE entries SET state=?, completed_at=?, next_retry_at=?, last_run_id=?, output_path=COALESCE(NULLIF(?, ''), output_path), last_error_code=?, last_error=?, claim_token=NULL, heartbeat_at=NULL WHERE id=?",
                (
                    state,
                    stamp.isoformat()
                    if state in {"succeeded", "failed_terminal"}
                    else None,
                    next_retry,
                    run_id or None,
                    output_path,
                    error_code or None,
                    error[:800] or None,
                    entry_id,
                ),
            )
            con.execute(
                "UPDATE entry_attempts SET finished_at=?, outcome=?, run_id=?, error_code=?, error=? WHERE entry_id=? AND attempt_no=?",
                (
                    stamp.isoformat(),
                    outcome,
                    run_id or None,
                    error_code or None,
                    error[:800] or None,
                    entry_id,
                    attempts,
                ),
            )

    def retry_index_succeeded(
        self, entry_id: int, *, error: str = "", now: str | None = None
    ) -> None:
        self.finish_entry(entry_id, outcome="succeeded", error=error, now=now)

    def list_entries(
        self, *, state: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        if state and state not in ENTRY_STATES:
            raise SubscriptionError(f"unknown entry state: {state}")
        query = "SELECT * FROM entries"
        params: list[Any] = []
        if state:
            query += " WHERE state = ?"
            params.append(state)
        query += " ORDER BY discovered_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self.session() as con:
            return [dict(row) for row in con.execute(query, params).fetchall()]

    def status_rows(
        self, subscriptions: Iterable[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        source_map = {source["id"]: source for source in subscriptions}
        since = (
            (datetime.now(UTC) - timedelta(days=7)).replace(microsecond=0).isoformat()
        )
        with self.session() as con:
            states = {
                row["subscription_id"]: dict(row)
                for row in con.execute("SELECT * FROM source_state").fetchall()
            }
            counts = {
                row["subscription_id"]: int(row["count"])
                for row in con.execute(
                    "SELECT subscription_id, COUNT(*) AS count FROM entries WHERE state IN ('queued', 'discovered', 'retry_wait', 'index_retry') GROUP BY subscription_id"
                ).fetchall()
            }
            check_counts = {
                row["subscription_id"]: dict(row)
                for row in con.execute(
                    "SELECT subscription_id, COUNT(*) AS checks_7d, SUM(CASE WHEN outcome = 'error' THEN 1 ELSE 0 END) AS error_checks_7d FROM source_checks WHERE checked_at >= ? GROUP BY subscription_id",
                    (since,),
                ).fetchall()
            }
            latest_checks = {}
            for row in con.execute(
                "SELECT * FROM source_checks ORDER BY subscription_id ASC, id DESC"
            ).fetchall():
                latest_checks.setdefault(row["subscription_id"], dict(row))
        rows = []
        for item_id, subscription in source_map.items():
            state = states.get(item_id, {})
            checks = check_counts.get(item_id, {})
            latest = latest_checks.get(item_id, {})
            rows.append(
                {
                    "id": item_id,
                    "name": subscription["name"],
                    "kind": subscription["kind"],
                    "provider": subscription["provider"],
                    "enabled": subscription["enabled"],
                    "mode": subscription["mode"],
                    "pending": counts.get(item_id, 0),
                    "next_due_at": state.get("next_due_at", ""),
                    "last_success_at": state.get("last_success_at", ""),
                    "error_streak": state.get("error_streak", 0),
                    "last_error_code": state.get("last_error_code", ""),
                    "last_error": state.get("last_error", ""),
                    "checks_7d": int(checks.get("checks_7d", 0)),
                    "error_checks_7d": int(checks.get("error_checks_7d", 0)),
                    "last_check_outcome": latest.get("outcome", ""),
                    "last_http_status": latest.get("http_status"),
                }
            )
        return rows
