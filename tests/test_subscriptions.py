import gc
import io
import http.client
import json
import os
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import (
    chubby,
    subscription_adapters,
    subscription_executor,
    subscription_store,
    subscriptions,
    validate_outputs,
)

RSS_FIXTURE = b"""<?xml version='1.0'?>
<rss version='2.0' xmlns:content='http://purl.org/rss/1.0/modules/content/'>
 <channel><title>Example</title>
  <item><guid>old-guid</guid><title>Old entry</title><link>https://example.com/old?utm_source=test</link><pubDate>Wed, 01 Oct 2026 01:00:00 +0000</pubDate><description>Old summary</description></item>
  <item><guid>new-guid</guid><title>New entry</title><link>https://example.com/new</link><pubDate>Wed, 01 Oct 2026 02:00:00 +0000</pubDate><content:encoded>New full body</content:encoded></item>
 </channel>
</rss>"""


class SubscriptionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / "vault"
        self.inbox = self.vault / "00_Inbox"
        self.config = dict(
            chubby.DEFAULT_CONFIG,
            output_dir=str(self.root / "output"),
            vault_root=str(self.vault),
            vault_dir=str(self.inbox),
            index_db=str(self.vault / ".chubby" / "index.sqlite"),
            state_file=str(self.root / "runs.jsonl"),
            report_dir=str(self.root / "reports"),
        )
        self.subscriptions_path = self.root / "subscriptions.json"
        self.args = types.SimpleNamespace(
            subscriptions=str(self.subscriptions_path),
            backfill=0,
            dry_run=False,
            due=False,
            all=False,
            limit=3,
            subscription=None,
            retry_failed=False,
            timeout=None,
        )

    def document(self, *, mode="discover_only", initial_sync="from_now"):
        return {
            "schema_version": 1,
            "defaults": {
                "poll_minutes": 60,
                "max_new_per_sync": 3,
                "mode": "discover_only",
                "process_limit_per_tick": 3,
            },
            "subscriptions": [
                {
                    "id": "example-feed",
                    "name": "Example",
                    "kind": "feed",
                    "enabled": True,
                    "mode": mode,
                    "config": {
                        "feed_url": "https://example.com/feed.xml",
                        "format": "rss",
                    },
                    "policy": {
                        "poll_minutes": 60,
                        "max_new_per_sync": 3,
                        "content_profile": "article",
                        "initial_sync": initial_sync,
                        "include_title_regex": [],
                        "exclude_title_regex": [],
                    },
                }
            ],
        }

    def write_document(self, **kwargs):
        return subscription_store.save_document(
            self.subscriptions_path, self.document(**kwargs)
        )

    def fetched(self, entries):
        return (
            subscription_adapters.FetchResult(
                200, b"", '"test"', "", "https://example.com/feed.xml"
            ),
            entries,
        )

    def entry(self, item_id, title, hour):
        return subscription_adapters.DiscoveredEntry(
            external_id=item_id,
            url=f"https://example.com/{item_id}?utm_source=test",
            title=title,
            author="Author",
            published_at=f"2026-10-01T0{hour}:00:00+00:00",
            updated_at="",
            content_html=f"<p>{title} body</p>",
            summary_html="",
            enclosure_url="",
            raw={"id": item_id},
        )

    def store(self):
        return subscription_store.SubscriptionStore(
            subscription_store.state_path(self.vault)
        )

    def test_parses_rss_atom_and_json_feed(self):
        rss = subscription_adapters.parse_feed(RSS_FIXTURE)
        self.assertEqual([item.external_id for item in rss], ["old-guid", "new-guid"])
        self.assertEqual(rss[1].content_html, "New full body")
        atom = subscription_adapters.parse_feed(
            b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry><id>a</id><title>Atom</title><link href='https://example.com/a'/><updated>2026-10-01T02:00:00Z</updated></entry></feed>"""
        )
        self.assertEqual(atom[0].url, "https://example.com/a")
        json_feed = subscription_adapters.parse_feed(
            b'{"version":"https://jsonfeed.org/version/1.1","items":[{"id":"j","title":"JSON","url":"https://example.com/j","content_text":"hello"}]}'
        )
        self.assertEqual(json_feed[0].content_html, "hello")

    def test_config_rejects_credential_url_and_unknown_keys(self):
        data = self.document()
        data["subscriptions"][0]["config"]["feed_url"] = (
            "https://example.com/feed.xml?token=nope"
        )
        with self.assertRaises(subscription_store.SubscriptionError):
            subscription_store.validate_document(data)
        data = self.document()
        data["unexpected"] = True
        with self.assertRaises(subscription_store.SubscriptionError):
            subscription_store.validate_document(data)

    def test_legacy_config_gets_provider_defaults_and_digest_stays_stable(self):
        legacy = self.document()
        legacy_source = legacy["subscriptions"][0]
        original_digest = subscription_store.config_digest(legacy_source)
        normalized = subscription_store.validate_document(legacy)
        source = normalized["subscriptions"][0]
        self.assertEqual(source["provider"], "generic_byo")
        self.assertEqual(subscription_store.config_digest(source), original_digest)

        youtube = self.document()
        youtube["subscriptions"][0].update(
            {
                "kind": "youtube_channel",
                "config": {"channel_id": "UCYO_jab_esuFRV4b17AJtAw"},
            }
        )
        self.assertEqual(
            subscription_store.validate_document(youtube)["subscriptions"][0][
                "provider"
            ],
            "native",
        )

    def test_provider_validation_is_kind_aware(self):
        data = self.document()
        data["subscriptions"][0]["provider"] = "unknown"
        with self.assertRaises(subscription_store.SubscriptionError):
            subscription_store.validate_document(data)

        data = self.document()
        data["subscriptions"][0].update(
            {
                "kind": "youtube_channel",
                "provider": "rsshub_byo",
                "config": {"channel_id": "UCYO_jab_esuFRV4b17AJtAw"},
            }
        )
        with self.assertRaises(subscription_store.SubscriptionError):
            subscription_store.validate_document(data)

    def test_provider_change_does_not_reset_source_cursor(self):
        subscription = self.write_document()["subscriptions"][0]
        store = self.store()
        store.migrate()
        store.ensure_sources([subscription], now="2026-10-01T00:00:00+00:00")
        store.mark_source_success(
            subscription,
            etag='"cursor"',
            last_modified="Wed, 01 Oct 2026 00:00:00 GMT",
            now="2026-10-01T01:00:00+00:00",
        )
        changed = dict(subscription)
        changed["provider"] = "rsshub_byo"
        store.ensure_sources([changed], now="2026-10-01T02:00:00+00:00")
        state = store.state_for(subscription["id"])
        self.assertEqual(state["etag"], '"cursor"')
        # next_due carries deterministic jitter within 10% of the poll interval.
        due = subscription_store.parse_iso(state["next_due_at"])
        base = subscription_store.parse_iso("2026-10-01T01:00:00+00:00")
        self.assertLessEqual(3600, (due - base).total_seconds())
        self.assertGreaterEqual(3600 * 1.1, (due - base).total_seconds())

    def test_classifies_provider_http_errors(self):
        cases = {
            401: ("http_401", True),
            403: ("http_403", True),
            404: ("http_404", True),
            429: ("http_429", False),
            500: ("http_5xx", False),
            503: ("http_5xx", False),
            418: ("http_4xx", True),
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertEqual(
                    subscription_adapters.classify_http_error(status), expected
                )

    def test_public_feed_user_agent_matches_the_actual_urllib_client(self):
        self.assertRegex(subscription_adapters.USER_AGENT, r"^Python-urllib/\d+\.\d+$")

    def test_fake_ip_proxy_dns_is_allowed_but_private_network_is_rejected(self):
        fake_ip = [(2, 1, 6, "", ("198.18.0.3", 443))]
        with patch.object(
            subscription_adapters.socket, "getaddrinfo", return_value=fake_ip
        ):
            subscription_adapters._validate_public_https("https://example.com/feed.xml")
        private_ip = [(2, 1, 6, "", ("127.0.0.1", 443))]
        with (
            patch.object(
                subscription_adapters.socket, "getaddrinfo", return_value=private_ip
            ),
            self.assertRaises(subscription_adapters.AdapterError) as raised,
        ):
            subscription_adapters._validate_public_https("https://example.com/feed.xml")
        self.assertEqual(raised.exception.code, "unsafe_url")

    def test_initial_sync_creates_seen_baseline_then_discovers_only_new_item(self):
        self.write_document()
        baseline = [self.entry("old", "Old", 1)]
        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=self.fetched(baseline),
        ):
            code, summary = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(code, 0)
        self.assertEqual(summary[0]["baseline"], 1)
        rows = self.store().list_entries(limit=10)
        self.assertEqual(rows[0]["state"], "seen")
        updated = [baseline[0], self.entry("new", "New", 2)]
        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=self.fetched(updated),
        ):
            code, summary = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(code, 0)
        self.assertEqual(summary[0]["new"], 1)
        states = {
            row["title"]: row["state"] for row in self.store().list_entries(limit=10)
        }
        self.assertEqual(states["New"], "discovered")
        self.assertEqual(states["Old"], "seen")

    def test_explicit_backfill_queues_only_requested_bound(self):
        self.write_document(mode="auto_ingest")
        self.args.backfill = 2
        entries = [
            self.entry("a", "A", 1),
            self.entry("b", "B", 2),
            self.entry("c", "C", 3),
        ]
        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=self.fetched(entries),
        ):
            code, summary = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(code, 0)
        self.assertEqual(summary[0]["queued"], 2)
        rows = self.store().list_entries(limit=10)
        self.assertEqual(sum(row["state"] == "queued" for row in rows), 2)
        self.assertEqual(sum(row["state"] == "seen" for row in rows), 1)

    def test_claim_failure_and_retry_state(self):
        self.write_document(mode="auto_ingest")
        self.args.backfill = 1
        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=self.fetched([self.entry("a", "A", 1)]),
        ):
            subscriptions.sync_subscriptions(self.args, self.config, force=True)
        claimed = self.store().claim_entries(1)
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["state_before_claim"], "queued")
        self.store().finish_entry(
            claimed[0]["id"], outcome="failed", error_code="network", error="temporary"
        )
        row = self.store().list_entries(limit=1)[0]
        self.assertEqual(row["state"], "retry_wait")
        self.assertEqual(row["attempt_count"], 1)

    def test_process_queue_materializes_feed_entry_and_records_pipeline_run(self):
        self.write_document(mode="auto_ingest")
        self.args.backfill = 1
        entry = self.entry("queued", "Queued article", 2)
        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=self.fetched([entry]),
        ):
            subscriptions.sync_subscriptions(self.args, self.config, force=True)
        with patch.object(chubby.vault_index, "sync_vault", return_value={"notes": 1}):
            code, records = subscriptions.process_entries(self.args, self.config)
        self.assertEqual(code, 0)
        self.assertEqual(records[0]["status"], "success")
        self.assertEqual(self.store().list_entries(limit=1)[0]["state"], "succeeded")
        self.assertTrue(Path(records[0]["output_path"]).is_file())
        self.assertIn(
            "subscription_entry_id", Path(self.config["state_file"]).read_text()
        )

    def test_feed_materializer_writes_schema_v1_markdown_and_indexes(self):
        subscription = self.write_document()["subscriptions"][0]
        entry = {
            "id": 9,
            "canonical_url": "https://example.com/article",
            "enclosure_url": "",
            "title": "Article title",
            "published_at": "2026-10-01T02:00:00+00:00",
            "content_html": "<p>Hello <strong>world</strong></p><script>alert(1)</script>",
            "summary_html": "",
            "state_before_claim": "queued",
        }
        record = subscription_executor.execute_entry(
            subscription, entry, self.config, self.args, "batch"
        )
        self.assertEqual(record["status"], "success", record)
        self.assertEqual(record["index_status"], "success", record)
        for output in record["output_paths"]:
            self.assertEqual(
                validate_outputs.validate_file(output, require_schema_v1=True), []
            )
            text = Path(output).read_text(encoding="utf-8")
            self.assertIn('subscription_id: "example-feed"', text)
            self.assertIn('subscription_provider: "generic_byo"', text)
            self.assertNotIn("alert(1)", text)

    def test_sync_records_success_duplicate_and_http_error_checks(self):
        self.write_document()
        baseline = [self.entry("old", "Old", 1)]
        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=self.fetched(baseline),
        ):
            code, summary = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(code, 0)
        self.assertEqual(summary[0]["parsed"], 1)
        self.assertEqual(summary[0]["baseline"], 1)

        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=self.fetched(baseline),
        ):
            _, summary = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(summary[0]["duplicates"], 1)

        error = subscription_adapters.AdapterError(
            "http_429",
            "feed request returned HTTP 429",
            retry_after=60,
            http_status=429,
        )
        with patch.object(
            subscriptions.subscription_adapters, "fetch_entries", side_effect=error
        ):
            code, summary = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(code, 1)
        self.assertEqual(summary[0]["error_code"], "http_429")
        self.assertIn("限流", summary[0]["error_action"])

        with self.store().connect() as con:
            checks = [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM source_checks ORDER BY id ASC"
                ).fetchall()
            ]
        self.assertEqual(
            [row["outcome"] for row in checks], ["success", "success", "error"]
        )
        self.assertEqual(checks[1]["duplicate_entries"], 1)
        self.assertEqual(checks[2]["http_status"], 429)
        self.assertEqual(checks[2]["error_code"], "http_429")
        row = self.store().status_rows(self.write_document()["subscriptions"])[0]
        self.assertEqual(row["checks_7d"], 3)
        self.assertEqual(row["error_checks_7d"], 1)
        self.assertEqual(row["last_http_status"], 429)
        status_args = types.SimpleNamespace(
            subscribe_command="status",
            subscriptions=str(self.subscriptions_path),
            json=True,
        )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(
                subscriptions.command_subscribe(status_args, self.config), 0
            )
        status_json = json.loads(stdout.getvalue())
        self.assertEqual(status_json[0]["last_error_code"], "http_429")
        self.assertIn("限流", status_json[0]["error_action"])

    def test_not_modified_sync_records_unchanged_check(self):
        self.write_document()
        unchanged = subscription_adapters.FetchResult(
            304, b"", '"test"', "", "https://example.com/feed.xml", not_modified=True
        )
        with patch.object(
            subscriptions.subscription_adapters,
            "fetch_entries",
            return_value=(unchanged, []),
        ):
            code, summary = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(code, 0)
        self.assertEqual(summary[0]["status"], "unchanged")
        with self.store().connect() as con:
            check = con.execute("SELECT * FROM source_checks").fetchone()
        self.assertEqual(check["outcome"], "unchanged")
        self.assertEqual(check["http_status"], 304)

    def test_v1_database_migrates_to_v2_without_losing_source_state(self):
        store = self.store()
        with store.connect() as con:
            con.executescript(
                """
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
                  id INTEGER PRIMARY KEY
                );
                INSERT INTO source_state(subscription_id, config_hash, next_due_at, etag)
                  VALUES ('legacy', 'hash', '2026-10-01T00:00:00+00:00', '"old"');
                PRAGMA user_version = 1;
                """
            )
        store.migrate()
        with store.connect() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            legacy = con.execute(
                "SELECT etag FROM source_state WHERE subscription_id = 'legacy'"
            ).fetchone()
            checks_table = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='source_checks'"
            ).fetchone()
        self.assertEqual(version, subscription_store.DATABASE_SCHEMA_VERSION)
        self.assertEqual(legacy["etag"], '"old"')
        self.assertIsNotNone(checks_table)
        with store.connect() as con:
            con.execute("PRAGMA user_version = 1")
        store.migrate()
        with store.connect() as con:
            self.assertEqual(
                con.execute("PRAGMA user_version").fetchone()[0],
                subscription_store.DATABASE_SCHEMA_VERSION,
            )
            columns = {
                row["name"]
                for row in con.execute("PRAGMA table_info(entries)").fetchall()
            }
        self.assertIn("claim_token", columns)
        self.assertIn("heartbeat_at", columns)

    def test_heartbeat_keeps_claim_alive_and_stale_claim_is_reclaimed(self):
        document = self.write_document()
        store = self.store()
        store.migrate()
        store.ensure_sources(document["subscriptions"])
        entry_id, _ = store.insert_entry(
            "example-feed",
            subscriptions.asdict(self.entry("e1", "Long episode", 1)),
            state="queued",
        )
        claimed = store.claim_entries(1, now="2026-10-01T00:00:00+00:00")
        token = claimed[0]["claim_token"]
        self.assertTrue(token)

        store.heartbeat(entry_id, token, now="2026-10-01T01:00:00+00:00")
        # A long transcription with heartbeats is never reclaimed.
        self.assertEqual(
            store.reclaim_expired_claims(now="2026-10-01T05:00:00+00:00"), 0
        )
        # A crashed worker stops heartbeating and is reclaimed after the threshold.
        self.assertEqual(
            store.reclaim_expired_claims(now="2026-10-01T07:01:00+00:00"), 1
        )
        row = next(r for r in store.list_entries() if r["id"] == entry_id)
        self.assertEqual(row["state"], "retry_wait")
        # Finishing clears the claim token and heartbeat.
        store.finish_entry(entry_id, outcome="succeeded")
        self.assertFalse(store.heartbeat(entry_id, token))

    def test_jitter_spreads_due_times_deterministically(self):
        document = self.document()
        second = dict(document["subscriptions"][0])
        second["id"] = "other-feed"
        second["config"] = {"feed_url": "https://other.example/feed.xml", "format": "rss"}
        document["subscriptions"].append(second)
        saved = subscription_store.save_document(self.subscriptions_path, document)
        store = self.store()
        store.migrate()
        store.ensure_sources(saved["subscriptions"], now="2026-10-01T00:00:00+00:00")
        first_due = subscription_store.parse_iso(store.state_for("example-feed")["next_due_at"])
        second_due = subscription_store.parse_iso(store.state_for("other-feed")["next_due_at"])
        self.assertNotEqual(first_due, second_due)
        base = subscription_store.parse_iso("2026-10-01T00:00:00+00:00")
        for due in (first_due, second_due):
            self.assertLessEqual(0, (due - base).total_seconds())
            self.assertGreaterEqual(3600, (due - base).total_seconds())
        # Re-ensuring with the same config keeps the original schedule.
        store.ensure_sources(saved["subscriptions"], now="2026-10-01T00:05:00+00:00")
        self.assertEqual(store.state_for("example-feed")["next_due_at"], first_due.isoformat())

    def test_resolve_youtube_channel_id(self):
        html = b'<html><script>{"channelId":"UCYO_jab_esuFRV4b17AJtAw"}</script></html>'
        result = subscription_adapters.FetchResult(
            200, html, "", "", "https://www.youtube.com/@3blue1brown"
        )
        with patch.object(
            subscription_adapters, "fetch_public_feed", return_value=result
        ):
            self.assertEqual(
                subscription_adapters.resolve_youtube_channel_id("@3blue1brown"),
                "UCYO_jab_esuFRV4b17AJtAw",
            )
        self.assertEqual(
            subscription_adapters.resolve_youtube_channel_id("UCYO_jab_esuFRV4b17AJtAw"),
            "UCYO_jab_esuFRV4b17AJtAw",
        )
        with self.assertRaises(subscription_adapters.AdapterError):
            subscription_adapters.resolve_youtube_channel_id("not-a-channel")
        empty = subscription_adapters.FetchResult(
            200, b"<html>no id here</html>", "", "", "https://www.youtube.com/@x"
        )
        with patch.object(
            subscription_adapters, "fetch_public_feed", return_value=empty
        ):
            with self.assertRaises(subscription_adapters.AdapterError):
                subscription_adapters.resolve_youtube_channel_id("@x")

    def test_user_agent_override_is_forwarded_to_fetch(self):
        document = self.document()
        document["subscriptions"][0]["policy"]["user_agent"] = "my-reader/1.0"
        saved = subscription_store.save_document(self.subscriptions_path, document)
        captured = {}

        def fake_fetch(url, **kwargs):
            captured.update(kwargs)
            return subscription_adapters.FetchResult(200, RSS_FIXTURE, "", "", url)

        with patch.object(
            subscription_adapters, "fetch_public_feed", side_effect=fake_fetch
        ):
            subscription_adapters.fetch_entries(saved["subscriptions"][0], {})
        self.assertEqual(captured.get("user_agent"), "my-reader/1.0")

    def test_process_respects_lock_but_tick_processes_while_holding_it(self):
        document = self.write_document()
        store = self.store()
        store.migrate()
        store.ensure_sources(document["subscriptions"])
        entry_id, _ = store.insert_entry(
            "example-feed",
            subscriptions.asdict(self.entry("e1", "Queued episode", 1)),
            state="queued",
        )
        token = store.acquire_lock("tick", seconds=3600)
        # A manual process is refused while the scheduler lock is held.
        code, records = subscriptions.process_entries(self.args, self.config)
        self.assertEqual((code, records), (0, []))
        # The tick itself still processes while holding that same lock.
        record = {
            "run_id": "r1",
            "status": "success",
            "output_path": "",
            "output_paths": [],
            "error": "",
            "source": "https://example.com/e1",
            "source_hash": "h",
            "skill": "rss",
            "content_type": "article",
        }
        with patch.object(
            subscriptions.subscription_executor,
            "execute_entry",
            return_value=dict(record),
        ):
            code, records = subscriptions.process_entries(
                self.args, self.config, holds_lock=True
            )
        self.assertEqual(code, 0)
        self.assertEqual(len(records), 1)
        row = next(r for r in store.list_entries() if r["id"] == entry_id)
        self.assertEqual(row["state"], "succeeded")
        store.release_lock("tick", token)

    def test_truncated_feed_response_maps_to_network_error(self):
        class Boom:
            def open(self, request, timeout=20):
                raise http.client.IncompleteRead(b"partial")

        with patch.object(
            subscription_adapters.urllib.request, "build_opener", return_value=Boom()
        ), patch.object(
            subscription_adapters.socket,
            "getaddrinfo",
            return_value=[(None, None, None, None, ("93.184.216.34", 443))],
        ):
            with self.assertRaises(subscription_adapters.AdapterError) as ctx:
                subscription_adapters.fetch_public_feed("https://example.com/feed.xml")
        self.assertEqual(ctx.exception.code, "network")

    def test_one_broken_source_does_not_abort_the_batch(self):
        document = self.document()
        second = dict(document["subscriptions"][0])
        second["id"] = "healthy-feed"
        second["config"] = {"feed_url": "https://healthy.example/feed.xml", "format": "rss"}
        document["subscriptions"].append(second)
        subscription_store.save_document(self.subscriptions_path, document)

        def flaky(subscription, state):
            if subscription["id"] == "example-feed":
                raise RuntimeError("boom")
            return self.fetched([self.entry("n1", "New", 3)])

        with patch.object(
            subscriptions.subscription_adapters, "fetch_entries", side_effect=flaky
        ):
            code, summaries = subscriptions.sync_subscriptions(
                self.args, self.config, force=True
            )
        self.assertEqual(code, 1)
        by_id = {item["id"]: item for item in summaries}
        self.assertEqual(by_id["example-feed"]["status"], "error")
        self.assertEqual(by_id["example-feed"]["error_code"], "unexpected")
        self.assertEqual(by_id["healthy-feed"]["status"], "healthy")

    def test_repeated_operations_do_not_leak_connections(self):
        document = self.write_document()
        store = self.store()
        store.migrate()
        store.ensure_sources(document["subscriptions"])
        entry_id, _ = store.insert_entry(
            "example-feed",
            subscriptions.asdict(self.entry("e1", "Long episode", 1)),
            state="queued",
        )
        token = store.claim_entries(1)[0]["claim_token"]

        def fd_count():
            gc.collect()
            return len(os.listdir("/dev/fd"))

        baseline = fd_count()
        for _ in range(200):
            store.heartbeat(entry_id, token)
        self.assertLess(fd_count() - baseline, 50)

    def test_locks_are_exclusive_and_releasable(self):
        self.write_document()
        store = self.store()
        store.migrate()
        first = store.acquire_lock("tick", seconds=60)
        self.assertTrue(first)
        self.assertIsNone(store.acquire_lock("tick", seconds=60))
        store.release_lock("tick", first)
        self.assertTrue(store.acquire_lock("tick", seconds=60))


if __name__ == "__main__":
    unittest.main()
