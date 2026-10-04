import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import chubby, subscription_digest, subscription_store, subscriptions, vault_index


def _entry(external_id, title, url, published, **extra):
    data = {
        "external_id": external_id,
        "url": url,
        "title": title,
        "author": "author",
        "published_at": published,
        "updated_at": "",
        "content_html": "",
        "summary_html": "",
        "enclosure_url": "",
        "content_kind": "article",
        "raw": {},
    }
    data.update(extra)
    return data


class SubscriptionDigestTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.config = dict(
            chubby.DEFAULT_CONFIG,
            vault_root=str(self.vault),
            vault_dir=str(self.vault / "00_Inbox"),
            index_db=str(self.vault / ".chubby" / "index.sqlite"),
            state_file=str(self.root / "runs.jsonl"),
            report_dir=str(self.root / "reports"),
            output_dir=str(self.root / "output"),
        )
        self.store = subscription_store.SubscriptionStore(
            self.vault / ".chubby" / "subscriptions.sqlite"
        )
        self.store.migrate()
        self.document = subscription_store.validate_document(
            {
                "schema_version": 1,
                "defaults": {
                    "poll_minutes": 60,
                    "max_new_per_sync": 3,
                    "mode": "discover_only",
                    "process_limit_per_tick": 3,
                },
                "subscriptions": [
                    {
                        "id": "feed-a",
                        "name": "Feed A",
                        "kind": "feed",
                        "enabled": True,
                        "mode": "discover_only",
                        "config": {"feed_url": "https://a.example/feed.xml", "format": "rss"},
                    },
                    {
                        "id": "feed-b",
                        "name": "Feed B",
                        "kind": "feed",
                        "enabled": True,
                        "mode": "discover_only",
                        "config": {"feed_url": "https://b.example/feed.xml", "format": "rss"},
                    },
                ],
            }
        )
        self.store.ensure_sources(self.document["subscriptions"])
        self.now = subscription_store.now_iso()

    def args(self, **overrides):
        base = dict(
            days=1,
            output="",
            enrich=False,
            no_vault_links=False,
            cluster_threshold=0.5,
        )
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def add_entry(self, source, external_id, title, *, state, published, output_path="", url=None):
        entry_id, _ = self.store.insert_entry(
            source,
            _entry(
                external_id,
                title,
                url or f"https://{source}.example/{external_id}",
                published,
            ),
            state=state,
            now=published,
        )
        if output_path:
            with self.store.session() as con:
                con.execute(
                    "UPDATE entries SET output_path = ? WHERE id = ?",
                    (output_path, entry_id),
                )
        return entry_id

    def test_window_filters_by_state_and_time(self):
        self.add_entry("feed-a", "new-1", "Fresh item", state="discovered", published=self.now)
        self.add_entry("feed-a", "old-1", "Old item", state="discovered", published="2020-01-01T00:00:00+00:00")
        self.add_entry("feed-a", "seen-1", "Baseline item", state="seen", published=self.now)
        self.add_entry("feed-a", "skip-1", "Skipped item", state="skipped", published=self.now)
        rows = subscription_digest.collect_window_entries(self.store, 1, now=self.now)
        titles = {row["title"] for row in rows}
        self.assertEqual(titles, {"Fresh item"})
        with self.assertRaises(subscription_digest.DigestError):
            subscription_digest.collect_window_entries(self.store, 0, now=self.now)

    def test_clustering_groups_same_event_across_sources(self):
        entries = [
            {"title": "OpenAI releases GPT-6 model", "subscription_id": "feed-a",
             "published_at": self.now, "discovered_at": self.now},
            {"title": "OpenAI releases GPT-6 model today", "subscription_id": "feed-b",
             "published_at": self.now, "discovered_at": self.now},
            {"title": "Local bakery wins bread award", "subscription_id": "feed-a",
             "published_at": self.now, "discovered_at": self.now},
        ]
        clusters = subscription_digest.cluster_entries(entries, threshold=0.5)
        self.assertEqual(len(clusters), 2)
        hot = clusters[0]
        self.assertEqual(hot["heat"], 2)
        self.assertEqual(len(hot["entries"]), 2)
        strict = subscription_digest.cluster_entries(entries, threshold=1.0)
        self.assertEqual(len(strict), 3)

    def test_succeeded_entry_links_local_note_and_frontmatter_counts(self):
        note = self.vault / "10_Sources" / "note.md"
        note.parent.mkdir(parents=True)
        note.write_text("---\ntitle: note\n---\n\nbody\n", encoding="utf-8")
        self.add_entry(
            "feed-a", "done-1", "Processed item", state="succeeded",
            published=self.now, output_path=str(note),
        )
        self.add_entry("feed-b", "disc-1", "Pending item", state="discovered", published=self.now)
        with patch.object(subscription_digest, "attach_vault_links"):
            code = subscription_digest.run_digest(
                self.args(), self.config, self.document, self.store
            )
        self.assertEqual(code, 0)
        outputs = list((self.vault / "30_Output").glob("subscription-digest-*.md"))
        self.assertEqual(len(outputs), 1)
        text = outputs[0].read_text(encoding="utf-8")
        self.assertIn("10_Sources/note.md", text)
        self.assertIn("https://feed-b.example/disc-1", text)
        self.assertIn("source_count: 2", text)
        self.assertIn("entry_count: 2", text)
        self.assertIn("enriched: false", text)

    def test_empty_window_is_friendly_and_writes_nothing(self):
        code = subscription_digest.run_digest(
            self.args(), self.config, self.document, self.store
        )
        self.assertEqual(code, 0)
        self.assertFalse((self.vault / "30_Output").exists())

    def test_existing_output_is_not_overwritten(self):
        self.add_entry("feed-a", "new-1", "Fresh item", state="discovered", published=self.now)
        with patch.object(subscription_digest, "attach_vault_links"):
            subscription_digest.run_digest(self.args(), self.config, self.document, self.store)
            subscription_digest.run_digest(self.args(), self.config, self.document, self.store)
        outputs = list((self.vault / "30_Output").glob("subscription-digest-*.md"))
        self.assertEqual(len(outputs), 2)
        explicit = self.root / "digest.md"
        explicit.write_text("keep me", encoding="utf-8")
        with self.assertRaises(subscription_digest.DigestError):
            subscription_digest.run_digest(
                self.args(output=str(explicit)), self.config, self.document, self.store
            )
        self.assertEqual(explicit.read_text(encoding="utf-8"), "keep me")

    def test_enrich_without_api_key_fails_in_chinese(self):
        self.add_entry("feed-a", "new-1", "Fresh item", state="discovered", published=self.now)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(subscription_digest.DigestError) as ctx:
                subscription_digest.run_digest(
                    self.args(enrich=True), self.config, self.document, self.store
                )
        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))
        self.assertIn("零 LLM", str(ctx.exception))

    def test_prompts_load_from_templates(self):
        prompts = subscription_digest.load_prompts()
        self.assertEqual(set(prompts), {"prescreen", "score", "summary"})
        self.assertIn("JSON", prompts["summary"])
        with self.assertRaises(subscription_digest.DigestError):
            subscription_digest.load_prompts(self.root / "no-such-dir")

    def test_enrich_marks_model_content_and_keeps_links(self):
        self.add_entry("feed-a", "n1", "OpenAI releases GPT-6", state="discovered", published=self.now)
        self.add_entry("feed-b", "n2", "OpenAI releases GPT-6 today", state="discovered", published=self.now)
        calls = []

        def fake_deepseek(system, user, api_key):
            calls.append(system)
            if "预筛" in system:
                return {"keep": [1, 2]}
            if "评分" in system:
                return {"scores": {"1": 9, "2": 8}}
            return {"headline": "OpenAI 发布 GPT-6", "summary": "模型厂商发布新一代旗舰。"}

        clusters = subscription_digest.cluster_entries(
            subscription_digest.collect_window_entries(self.store, 1, now=self.now)
        )
        with patch.object(subscription_digest, "call_deepseek", side_effect=fake_deepseek):
            enriched = subscription_digest.enrich_clusters(clusters, "test-key")
        self.assertEqual(enriched, 1)
        self.assertEqual(clusters[0]["llm_headline"], "OpenAI 发布 GPT-6")
        self.assertEqual(clusters[0]["llm_score"], 9)
        self.assertEqual(len(calls), 3)

        with patch.object(subscription_digest, "call_deepseek", side_effect=fake_deepseek), \
                patch.object(subscription_digest, "attach_vault_links"), \
                patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=True):
            code = subscription_digest.run_digest(
                self.args(enrich=True), self.config, self.document, self.store
            )
        self.assertEqual(code, 0)
        text = next((self.vault / "30_Output").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("🤖", text)
        self.assertIn("enriched: true", text)
        self.assertIn("https://feed-a.example/n1", text)
        self.assertIn("评分 9/10", text)

    def test_vault_links_count_related_notes(self):
        notes = self.vault / "notes"
        notes.mkdir()
        (notes / "gpt.md").write_text(
            "---\ntitle: GPT-6 深度评测\n---\n\nOpenAI releases GPT-6 model analysis\n",
            encoding="utf-8",
        )
        index_db = self.vault / ".chubby" / "index.sqlite"
        vault_index.index_vault(notes, db_path=index_db)
        self.add_entry("feed-a", "n1", "OpenAI releases GPT-6 model", state="discovered", published=self.now)
        code = subscription_digest.run_digest(
            self.args(), self.config, self.document, self.store
        )
        self.assertEqual(code, 0)
        text = next((self.vault / "30_Output").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("知识库已有", text)
        self.assertIn("GPT-6 深度评测", text)

        # --no-vault-links skips the lookup entirely.
        code = subscription_digest.run_digest(
            self.args(no_vault_links=True), self.config, self.document, self.store
        )
        self.assertEqual(code, 0)
        texts = sorted((self.vault / "30_Output").glob("*.md"), key=lambda p: p.stat().st_mtime)
        self.assertNotIn("知识库已有", texts[-1].read_text(encoding="utf-8"))

    def test_command_subscribe_digest_dispatch(self):
        self.add_entry("feed-a", "n1", "Fresh item", state="discovered", published=self.now)
        args = types.SimpleNamespace(
            subscribe_command="digest",
            subscriptions=str(self.root / "subscriptions.json"),
            days=1,
            output="",
            enrich=False,
            no_vault_links=True,
            cluster_threshold=0.5,
        )
        subscription_store.save_document(
            self.root / "subscriptions.json", self.document
        )
        code = subscriptions.command_subscribe(args, self.config)
        self.assertEqual(code, 0)
        self.assertTrue((self.vault / "30_Output").exists())


if __name__ == "__main__":
    unittest.main()
