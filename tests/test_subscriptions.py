import tempfile
import types
import unittest
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
            self.assertNotIn("alert(1)", text)

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
