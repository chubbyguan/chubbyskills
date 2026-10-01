"""Execution bridge from subscription queue entries to existing Chubby pipelines."""

from __future__ import annotations

import re
import tempfile
import types
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, ClassVar


class _TextExtractor(HTMLParser):
    BLOCK: ClassVar[set[str]] = {
        "p",
        "div",
        "br",
        "li",
        "h1",
        "h2",
        "h3",
        "blockquote",
        "pre",
    }
    DROP: ClassVar[set[str]] = {"script", "style", "form", "iframe", "object", "embed"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.DROP:
            self.drop_depth += 1
        if not self.drop_depth and tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.DROP and self.drop_depth:
            self.drop_depth -= 1
        if not self.drop_depth and tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.drop_depth:
            self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    parser.close()
    lines = [
        re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines()
    ]
    return "\n\n".join(line for line in lines if line)


def _chubby():
    try:
        from tools import chubby
    except ModuleNotFoundError:
        import chubby
    return chubby


def _subscription_fields(
    chubby, subscription: dict[str, Any], entry: dict[str, Any]
) -> dict[str, str]:
    return {
        "subscription_id": chubby.yaml_quote(subscription["id"]),
        "subscription_name": chubby.yaml_quote(subscription["name"]),
        "subscription_entry_id": str(entry["id"]),
        "source_feed": chubby.yaml_quote(_source_url(subscription)),
    }


def _source_url(subscription: dict[str, Any]) -> str:
    if subscription["kind"] == "youtube_channel":
        channel = subscription["config"]["channel_id"]
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel}"
    return subscription["config"]["feed_url"]


def _process_args(args: Any, skill: str):
    return types.SimpleNamespace(
        output=None,
        vault=None,
        skill=skill,
        enrich=None,
        dry_run=bool(getattr(args, "dry_run", False)),
        refresh=False,
        timeout=getattr(args, "timeout", None),
        extra=[],
    )


def _record_error(
    chubby, entry: dict[str, Any], message: str, batch_id: str
) -> dict[str, Any]:
    started = chubby.now_iso()
    source = (
        entry.get("canonical_url")
        or entry.get("enclosure_url")
        or "subscription-entry:" + str(entry["id"])
    )
    return {
        "run_id": chubby.make_run_id(),
        "batch_id": batch_id,
        "source": source,
        "source_hash": chubby.source_hash(source),
        "skill": "subscription",
        "status": "failed",
        "started_at": started,
        "finished_at": chubby.now_iso(),
        "error": message,
        "output_path": "",
        "output_paths": [],
        "content_type": "note",
        "subscription_entry_id": entry["id"],
    }


def _retry_index(
    chubby, entry: dict[str, Any], config: dict[str, Any], batch_id: str
) -> dict[str, Any]:
    started = chubby.now_iso()
    output = entry.get("output_path") or ""
    record = {
        "run_id": chubby.make_run_id(),
        "batch_id": batch_id,
        "source": entry.get("canonical_url")
        or "subscription-entry:" + str(entry["id"]),
        "source_hash": chubby.source_hash(
            entry.get("canonical_url") or "subscription-entry:" + str(entry["id"])
        ),
        "skill": "subscription-index",
        "status": "success",
        "started_at": started,
        "finished_at": chubby.now_iso(),
        "output_path": output,
        "output_paths": [output] if output else [],
        "content_type": "note",
        "subscription_entry_id": entry["id"],
    }
    if not output or not Path(output).is_file():
        record["status"] = "failed"
        record["error"] = "cannot retry index because captured Markdown is missing"
        return record
    vault = config.get("vault_dir")
    index_vault, index_db = chubby.index_context(vault, config)
    record["index_vault"] = index_vault
    record["index_db"] = index_db
    return chubby.finish_record(record)


def _materialize_feed_entry(
    chubby,
    subscription: dict[str, Any],
    entry: dict[str, Any],
    config: dict[str, Any],
    batch_id: str,
) -> dict[str, Any]:
    started = chubby.now_iso()
    source = (
        entry.get("canonical_url")
        or entry.get("enclosure_url")
        or _source_url(subscription)
    )
    content_html = entry.get("content_html") or ""
    summary_html = entry.get("summary_html") or ""
    if (
        len(content_html.encode("utf-8")) > 256 * 1024
        or len(summary_html.encode("utf-8")) > 256 * 1024
    ):
        return _record_error(
            chubby,
            entry,
            "feed content exceeds the 256 KiB P0 materialization limit",
            batch_id,
        )
    content = html_to_text(content_html) or html_to_text(summary_html)
    completeness = "full" if content_html else "summary"
    if not content:
        content = "来源未提供可保存的正文或摘要。"
        completeness = "summary"
    created = (entry.get("published_at") or started)[:10]
    title = str(entry.get("title") or "Untitled feed entry")
    output_dir = chubby.resolve_path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = {
        "title": chubby.yaml_quote(title),
        "type": "note",
        "platform": "rss",
        "source": chubby.yaml_quote(source),
        "created": created,
        "source_feed": chubby.yaml_quote(_source_url(subscription)),
        "subscription_id": chubby.yaml_quote(subscription["id"]),
        "subscription_name": chubby.yaml_quote(subscription["name"]),
        "subscription_entry_id": str(entry["id"]),
        "content_completeness": completeness,
    }
    body = f"# {title}\n\n"
    if completeness == "summary":
        body += f"> 来源仅提供摘要；完整内容请打开原文链接：<{source}>\n\n"
    body += content + "\n"
    try:
        with tempfile.TemporaryDirectory(prefix="chubby-feed-") as temp:
            staged = Path(temp) / "feed-entry.md"
            staged.write_text(
                "---\n"
                + "\n".join(f"{key}: {value}" for key, value in fields.items())
                + "\n---\n\n"
                + body,
                encoding="utf-8",
            )
            published = chubby.chubby_ingest.publish_bundle(
                staged, output_dir, source=source
            )
        final = published
        vault = config.get("vault_dir")
        if vault:
            final = chubby.chubby_ingest.copy_into_vault(published, vault)
        record = {
            "run_id": chubby.make_run_id(),
            "batch_id": batch_id,
            "source": source,
            "source_hash": chubby.source_hash(source),
            "skill": "rss",
            "status": "success",
            "started_at": started,
            "finished_at": chubby.now_iso(),
            "content_type": "article",
            "output_path": final,
            "output_paths": [published] if final == published else [published, final],
            "output_dir": str(output_dir),
            "vault_dir": str(vault or ""),
            "subscription_entry_id": entry["id"],
        }
        index_vault, index_db = chubby.index_context(vault, config)
        record["index_vault"] = index_vault
        record["index_db"] = index_db
        chubby.stamp_all_outputs(record)
        return chubby.finish_record(record)
    # This is the outer materialization boundary. Any filesystem, validation,
    # or index failure must become a durable queue failure instead of crashing
    # the scheduled worker.
    except Exception as exc:  # noqa: BLE001
        return _record_error(chubby, entry, str(exc), batch_id)


def execute_entry(
    subscription: dict[str, Any],
    entry: dict[str, Any],
    config: dict[str, Any],
    args: Any,
    batch_id: str,
) -> dict[str, Any]:
    """Run one claimed entry; caller persists its result in store and JSONL."""

    chubby = _chubby()
    if entry.get("state_before_claim") == "index_retry":
        return _retry_index(chubby, entry, config, batch_id)
    profile = subscription["policy"]["content_profile"]
    if profile == "auto":
        profile = (
            "video"
            if subscription["kind"] == "youtube_channel"
            else ("podcast" if entry.get("enclosure_url") else "article")
        )
    if profile == "video":
        source = entry.get("canonical_url") or ""
        if not source:
            return _record_error(
                chubby, entry, "video entry has no public URL", batch_id
            )
        record = chubby.run_ingest_source(
            source,
            _process_args(args, "youtube"),
            config,
            batch_id=batch_id,
            skill="youtube",
        )
    elif profile == "podcast":
        source = entry.get("enclosure_url") or entry.get("canonical_url") or ""
        if not source:
            return _record_error(
                chubby, entry, "podcast entry has no enclosure or episode URL", batch_id
            )
        record = chubby.run_ingest_source(
            source,
            _process_args(args, "podcast"),
            config,
            batch_id=batch_id,
            skill="podcast",
        )
    else:
        return _materialize_feed_entry(chubby, subscription, entry, config, batch_id)
    record["subscription_entry_id"] = entry["id"]
    record["subscription_id"] = subscription["id"]
    record["source_feed"] = _source_url(subscription)
    for output in record.get("output_paths") or [record.get("output_path")]:
        if output:
            chubby.upsert_frontmatter(
                Path(output), _subscription_fields(chubby, subscription, entry)
            )
    return record
