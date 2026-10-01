"""Subscribe command handlers for Chubby Skills P0."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

try:
    from tools import subscription_adapters, subscription_executor, subscription_store
except ModuleNotFoundError:
    import subscription_adapters
    import subscription_executor
    import subscription_store


class SubscribeCommandError(RuntimeError):
    pass


def _chubby():
    try:
        from tools import chubby
    except ModuleNotFoundError:
        import chubby
    return chubby


def _paths(args: Any, config: dict[str, Any]) -> tuple[Path, Path]:
    chubby = _chubby()
    subscription_path = subscription_store.config_path(
        chubby.ROOT, getattr(args, "subscriptions", None)
    )
    root_value = config.get("vault_root")
    if not root_value:
        raise SubscribeCommandError(
            "订阅功能需要已配置知识库：先运行 chubby init --vault <知识库根目录>"
        )
    return subscription_path, subscription_store.state_path(
        chubby.resolve_path(root_value)
    )


def _context(args: Any, config: dict[str, Any]):
    document_path, database_path = _paths(args, config)
    document = subscription_store.load_document(document_path)
    store = subscription_store.SubscriptionStore(database_path)
    store.migrate()
    store.ensure_sources(document["subscriptions"])
    return document_path, document, store


def _print_table(headers: list[str], rows: list[list[Any]]) -> None:
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print(
            "| "
            + " | ".join(
                str(value or "").replace("|", "\\|").replace("\n", " ") for value in row
            )
            + " |"
        )


def _entry_from_adapter(
    item: subscription_adapters.DiscoveredEntry, subscription: dict[str, Any]
) -> dict[str, Any]:
    data = asdict(item)
    profile = subscription["policy"]["content_profile"]
    if profile == "auto":
        profile = (
            "video"
            if subscription["kind"] == "youtube_channel"
            else ("podcast" if item.enclosure_url else "article")
        )
    data["content_kind"] = profile
    return data


def _matches_policy(subscription: dict[str, Any], entry: dict[str, Any]) -> str:
    title = entry["title"]
    policy = subscription["policy"]
    includes = [re.compile(item) for item in policy["include_title_regex"]]
    excludes = [re.compile(item) for item in policy["exclude_title_regex"]]
    if includes and not any(pattern.search(title) for pattern in includes):
        return "title_not_included"
    if any(pattern.search(title) for pattern in excludes):
        return "title_excluded"
    return ""


def _sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda entry: (
            entry.get("published_at") or "",
            entry.get("updated_at") or "",
            entry.get("external_id") or "",
        ),
        reverse=True,
    )


def _sync_one(
    store: subscription_store.SubscriptionStore,
    subscription: dict[str, Any],
    *,
    backfill: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    state = store.state_for(subscription["id"])
    lease = store.acquire_source_lease(subscription["id"])
    summary = {
        "id": subscription["id"],
        "status": "skipped",
        "new": 0,
        "queued": 0,
        "discovered": 0,
        "skipped": 0,
        "baseline": 0,
        "unchanged": 0,
        "error": "",
    }
    if not lease:
        summary["status"] = "busy"
        return summary
    try:
        result, found = subscription_adapters.fetch_entries(subscription, state)
        if result.not_modified:
            if not dry_run:
                store.mark_source_success(
                    subscription,
                    etag=result.etag,
                    last_modified=result.last_modified,
                    not_modified=True,
                )
            summary.update(status="unchanged", unchanged=1)
            return summary
        first_sync = not bool(state.get("initialized_at"))
        queue_budget = (
            backfill
            if first_sync and backfill
            else subscription["policy"]["max_new_per_sync"]
        )
        eligible = 0
        for entry in _sort_entries(
            [_entry_from_adapter(item, subscription) for item in found]
        ):
            if store.has_entry(subscription["id"], entry):
                continue
            if (
                first_sync
                and not backfill
                and subscription["policy"]["initial_sync"] == "from_now"
            ):
                planned_state, reason = "seen", "initial_baseline"
            else:
                reason = _matches_policy(subscription, entry)
                if reason:
                    planned_state = "skipped"
                elif first_sync and backfill:
                    planned_state = "queued" if eligible < queue_budget else "seen"
                    reason = "" if planned_state == "queued" else "backfill_limit"
                    eligible += 1
                elif subscription["mode"] == "discover_only":
                    planned_state = "discovered"
                else:
                    planned_state = (
                        "queued" if eligible < queue_budget else "discovered"
                    )
                    reason = "" if planned_state == "queued" else "max_new_per_sync"
                    eligible += 1
            if dry_run:
                summary["new"] += 1
                summary["baseline"] += planned_state == "seen"
                summary["queued"] += planned_state == "queued"
                summary["discovered"] += planned_state == "discovered"
                summary["skipped"] += planned_state == "skipped"
                continue
            _, created = store.insert_entry(
                subscription["id"], entry, state=planned_state, skip_reason=reason
            )
            if created:
                summary["new"] += 1
                summary["baseline"] += planned_state == "seen"
                summary["queued"] += planned_state == "queued"
                summary["discovered"] += planned_state == "discovered"
                summary["skipped"] += planned_state == "skipped"
        if not dry_run:
            store.mark_source_success(
                subscription, etag=result.etag, last_modified=result.last_modified
            )
        summary["status"] = "healthy"
        return summary
    except subscription_adapters.AdapterError as exc:
        if not dry_run:
            store.mark_source_error(
                subscription["id"],
                exc.code,
                str(exc),
                retry_after=exc.retry_after,
                pause=exc.code
                in {"auth", "invalid_config", "parse", "unsafe_url", "invalid_url"},
            )
        summary.update(status="error", error=f"{exc.code}: {exc}")
        return summary
    finally:
        store.release_source_lease(subscription["id"], lease)


def sync_subscriptions(
    args: Any, config: dict[str, Any], *, due: bool = False, force: bool = False
) -> tuple[int, list[dict[str, Any]]]:
    _, document, store = _context(args, config)
    backfill = int(getattr(args, "backfill", 0) or 0)
    if backfill < 0 or backfill > 10:
        raise SubscribeCommandError("--backfill must be between 1 and 10")
    candidates = store.due_subscriptions(
        document["subscriptions"], force=force or not due
    )
    summaries = [
        _sync_one(
            store,
            subscription,
            backfill=backfill,
            dry_run=bool(getattr(args, "dry_run", False)),
        )
        for subscription in candidates
    ]
    healthy = sum(item["status"] == "healthy" for item in summaries)
    unchanged = sum(item["status"] == "unchanged" for item in summaries)
    errors = sum(item["status"] == "error" for item in summaries)
    print(
        f"同步完成：due={len(candidates)} healthy={healthy} unchanged={unchanged} errors={errors}"
    )
    if summaries:
        _print_table(
            ["id", "status", "new", "queued", "discovered", "baseline", "error"],
            [
                [
                    item["id"],
                    item["status"],
                    item["new"],
                    item["queued"],
                    item["discovered"],
                    item["baseline"],
                    item["error"],
                ]
                for item in summaries
            ],
        )
    return (1 if errors else 0), summaries


def process_entries(
    args: Any, config: dict[str, Any], *, limit: int | None = None
) -> tuple[int, list[dict[str, Any]]]:
    _, document, store = _context(args, config)
    requested = (
        limit
        if limit is not None
        else int(
            getattr(args, "limit", 0) or document["defaults"]["process_limit_per_tick"]
        )
    )
    if requested < 1 or requested > 10:
        raise SubscribeCommandError("--limit must be between 1 and 10")
    store.reclaim_expired_claims()
    entries = store.claim_entries(
        requested,
        subscription_id=getattr(args, "subscription", None),
        include_retry=bool(getattr(args, "retry_failed", False)),
    )
    if not entries:
        print("待处理队列为空。")
        return 0, []
    by_id = {item["id"]: item for item in document["subscriptions"]}
    chubby = _chubby()
    batch_id = chubby.make_run_id()
    records = []
    for entry in entries:
        subscription = by_id.get(entry["subscription_id"])
        if not subscription:
            store.finish_entry(
                entry["id"],
                outcome="failed",
                error_code="missing_subscription",
                error="subscription no longer exists",
            )
            continue
        record = subscription_executor.execute_entry(
            subscription, entry, config, args, batch_id
        )
        record["subscription_id"] = subscription["id"]
        record["subscription_entry_id"] = entry["id"]
        chubby.append_record(config, record)
        records.append(record)
        if record.get("status") == "success" and record.get("index_status") != "failed":
            store.finish_entry(
                entry["id"],
                outcome="succeeded",
                run_id=record["run_id"],
                output_path=record.get("output_path", ""),
            )
        elif record.get("status") == "success":
            store.finish_entry(
                entry["id"],
                outcome="index_retry",
                run_id=record["run_id"],
                output_path=record.get("output_path", ""),
                error_code="index_failed",
                error=record.get("index_error", ""),
            )
        else:
            store.finish_entry(
                entry["id"],
                outcome="failed",
                run_id=record.get("run_id", ""),
                output_path=record.get("output_path", ""),
                error_code="capture_failed",
                error=record.get("error", ""),
            )
    report = chubby.write_report(config, records, "subscribe process")
    chubby.print_run_summary(records, report)
    failed = any(
        record.get("status") != "success" or record.get("index_status") == "failed"
        for record in records
    )
    return (1 if failed else 0), records


def _add(args: Any, config: dict[str, Any]) -> int:
    path, document, _ = _context(args, config)
    kind = args.kind
    source_config = (
        {"feed_url": args.feed, "format": args.format}
        if kind == "feed"
        else {"channel_id": args.channel_id}
    )
    item = {
        "id": args.id,
        "name": args.name,
        "kind": kind,
        "enabled": True,
        "mode": args.mode or document["defaults"]["mode"],
        "config": source_config,
        "policy": {
            "poll_minutes": args.poll_minutes,
            "max_new_per_sync": args.max_new_per_sync,
            "content_profile": args.content_profile,
            "initial_sync": "backfill" if args.backfill else "from_now",
            "include_title_regex": args.include_title or [],
            "exclude_title_regex": args.exclude_title or [],
        },
    }
    document["subscriptions"].append(item)
    subscription_store.save_document(path, document)
    print(
        f"✅ 已添加订阅：{args.id}（默认 {item['mode']}，首次 {'回填' if args.backfill else '只建立基线'}）"
    )
    return 0


def _toggle(args: Any, config: dict[str, Any], enabled: bool) -> int:
    path, document, _ = _context(args, config)
    target = next(
        (item for item in document["subscriptions"] if item["id"] == args.id), None
    )
    if not target:
        raise SubscribeCommandError(f"subscription not found: {args.id}")
    target["enabled"] = enabled
    subscription_store.save_document(path, document)
    print(f"✅ 已{'恢复' if enabled else '暂停'}订阅：{args.id}")
    return 0


def command_subscribe(args: Any, config: dict[str, Any]) -> int:
    try:
        action = args.subscribe_command
        if action == "init":
            path, _, store = _context(args, config)
            subscription_store.save_document(
                path, subscription_store.default_document()
            ) if not path.exists() else None
            store.migrate()
            print(f"✅ 已准备订阅配置：{path}")
            print(f"✅ 已准备订阅状态：{store.path}")
            return 0
        if action == "add":
            return _add(args, config)
        if action == "validate":
            path, document, store = _context(args, config)
            print(f"✅ 订阅配置有效：{path}（{len(document['subscriptions'])} 个来源）")
            print(f"✅ 订阅状态可用：{store.path}")
            return 0
        if action == "list":
            _, document, _ = _context(args, config)
            _print_table(
                ["id", "name", "kind", "enabled", "mode", "poll(min)"],
                [
                    [
                        item["id"],
                        item["name"],
                        item["kind"],
                        item["enabled"],
                        item["mode"],
                        item["policy"]["poll_minutes"],
                    ]
                    for item in document["subscriptions"]
                ],
            )
            return 0
        if action == "status":
            _, document, store = _context(args, config)
            rows = store.status_rows(document["subscriptions"])
            if getattr(args, "json", False):
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                _print_table(
                    [
                        "id",
                        "enabled",
                        "mode",
                        "pending",
                        "next due",
                        "streak",
                        "last error",
                    ],
                    [
                        [
                            row["id"],
                            row["enabled"],
                            row["mode"],
                            row["pending"],
                            row["next_due_at"],
                            row["error_streak"],
                            row["last_error"],
                        ]
                        for row in rows
                    ],
                )
            return 0
        if action == "test":
            _, document, store = _context(args, config)
            subscription = next(
                (item for item in document["subscriptions"] if item["id"] == args.id),
                None,
            )
            if not subscription:
                raise SubscribeCommandError(f"subscription not found: {args.id}")
            result, items = subscription_adapters.fetch_entries(
                subscription, store.state_for(subscription["id"])
            )
            print(f"✅ HTTP {result.status_code}; parsed {len(items)} entries")
            _print_table(
                ["title", "url", "published", "enclosure"],
                [
                    [item.title, item.url, item.published_at, item.enclosure_url]
                    for item in items[:5]
                ],
            )
            return 0
        if action == "sync":
            return sync_subscriptions(args, config, due=args.due, force=args.all)[0]
        if action == "pending":
            _, _, store = _context(args, config)
            rows = store.list_entries(state=args.state, limit=args.limit)
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                _print_table(
                    ["id", "source", "state", "title", "published", "reason"],
                    [
                        [
                            row["id"],
                            row["subscription_id"],
                            row["state"],
                            row["title"],
                            row["published_at"],
                            row["skip_reason"] or row["last_error"],
                        ]
                        for row in rows
                    ],
                )
            return 0
        if action == "promote":
            _, _, store = _context(args, config)
            print(f"✅ 已入队 {store.promote(args.entry_ids)} 条。")
            return 0
        if action == "skip":
            _, _, store = _context(args, config)
            print(f"✅ 已跳过 {store.skip(args.entry_ids, args.reason)} 条。")
            return 0
        if action == "process":
            return process_entries(args, config)[0]
        if action == "tick":
            _, document, store = _context(args, config)
            token = store.acquire_lock("tick", seconds=1800)
            if not token:
                print("已有订阅任务执行中，当前 tick 跳过。")
                return 0
            try:
                sync_code, _ = sync_subscriptions(args, config, due=True)
                if args.no_process:
                    return sync_code
                # A scheduled tick owns recovery; manual `process` keeps an
                # explicit --retry-failed switch for safer ad-hoc use.
                args.retry_failed = True
                process_code, _ = process_entries(
                    args,
                    config,
                    limit=args.process_limit
                    or document["defaults"]["process_limit_per_tick"],
                )
                return 1 if sync_code or process_code else 0
            finally:
                store.release_lock("tick", token)
        if action == "pause":
            return _toggle(args, config, False)
        if action == "resume":
            return _toggle(args, config, True)
        raise SubscribeCommandError(f"unknown subscribe command: {action}")
    except (
        SubscribeCommandError,
        subscription_store.SubscriptionError,
        subscription_adapters.AdapterError,
        ValueError,
    ) as exc:
        print(f"❌ 订阅操作失败：{exc}", file=sys.stderr)
        return 1
