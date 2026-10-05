import getpass
import tempfile
from datetime import timedelta
import types
import unittest
from pathlib import Path

from tools import chubby, subscription_site, subscription_store, subscriptions


def _entry(external_id, title, url, published, **extra):
    data = {
        "external_id": external_id,
        "url": url,
        "title": title,
        "author": "author",
        "published_at": published,
        "updated_at": "",
        "content_html": "<p>full body must never reach the site</p>",
        "summary_html": "secret summary",
        "enclosure_url": "",
        "content_kind": "article",
        "raw": {},
    }
    data.update(extra)
    return data


class SubscriptionSiteTest(unittest.TestCase):
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
                        "kind": "youtube_channel",
                        "enabled": True,
                        "mode": "discover_only",
                        "config": {"channel_id": "UCYO_jab_esuFRV4b17AJtAw"},
                    },
                ],
            }
        )
        self.store.ensure_sources(self.document["subscriptions"])
        self.now = subscription_store.now_iso()
        self.output = self.root / "site"

    def args(self, **overrides):
        base = dict(days=7, output=str(self.output), site_name="测试情报站", base_url="")
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def add_entry(self, source, external_id, title, *, state="discovered", published=None, url=None):
        published = published or self.now
        entry_id, _ = self.store.insert_entry(
            source,
            _entry(external_id, title, url or f"https://{source}.example/{external_id}", published),
            state=state,
            now=published,
        )
        return entry_id

    def build(self, **overrides):
        return subscription_site.build_site(
            self.args(**overrides), self.config, self.document, self.store
        )

    def all_html(self):
        return "\n".join(
            path.read_text(encoding="utf-8") for path in self.output.rglob("*.html")
        )

    def all_public_output(self):
        """Every file the site publishes, HTML plus the agent-facing exits."""
        return self.all_html() + "\n" + "\n".join(
            (self.output / name).read_text(encoding="utf-8")
            for name in ("feed.xml", "llms.txt")
        )

    def test_build_renders_all_pages_and_css(self):
        self.add_entry("feed-a", "n1", "OpenAI releases GPT-6")
        self.add_entry("feed-b", "n2", "OpenAI releases GPT-6 today")
        self.add_entry("feed-a", "n3", "Bakery wins award", published="2020-01-01T00:00:00+00:00")
        code = self.build()
        self.assertEqual(code, 0)
        for name in ("index.html", "sources.html", "about.html", "style.css", "archive/index.html"):
            self.assertTrue((self.output / name).is_file(), name)
        day = self.now[:10]
        self.assertTrue((self.output / "archive" / f"{day}.html").is_file())
        index = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn("OpenAI releases GPT-6", index)
        self.assertIn("🔥 ×2", index)  # two sources clustered into one event
        self.assertIn('class="chip"', index)  # per-source colored chip
        self.assertIn('class="day-title"', index)  # date grouping header
        month, day = int(self.now[5:7]), int(self.now[8:10])
        self.assertIn(f"{month}月{day}日 · 2 条", index)
        self.assertIn("https://feed-a.example/n1", index)
        self.assertIn("测试情报站", index)
        self.assertIn("Generated by", index)
        # The 2020 entry is outside the window everywhere.
        self.assertNotIn("Bakery wins award", self.all_html())

    def test_single_entry_cluster_shows_title_once(self):
        self.add_entry("feed-a", "n1", "Solo headline", url="https://a.example/solo")
        self.add_entry("feed-a", "n2", "OpenAI releases GPT-6", url="https://a.example/gpt6-a")
        self.add_entry("feed-b", "n3", "OpenAI releases GPT-6 today", url="https://b.example/gpt6-b")
        self.build()
        index = (self.output / "index.html").read_text(encoding="utf-8")
        # Solo cluster: one linked title, no entries list, no duplicated text.
        self.assertEqual(index.count("Solo headline"), 1)
        self.assertIn(
            '<h3 class="card-title"><a href="https://a.example/solo" rel="noopener">Solo headline</a></h3>',
            index,
        )
        # Multi-entry cluster keeps representative title + entries list.
        self.assertIn('<ul class="entries">', index)
        self.assertIn("https://b.example/gpt6-b", index)
        self.assertIn("🔥 ×2", index)

    def test_css_uses_relative_paths_that_work_over_file_protocol(self):
        self.add_entry("feed-a", "n1", "Item")
        self.build()
        index = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="./style.css"', index)
        self.assertNotIn('href="/style.css"', index)
        day_page = (self.output / "archive" / f"{self.now[:10]}.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="../style.css"', day_page)
        self.assertIn('href="../sources.html"', day_page)
        archive_index = (self.output / "archive" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="../style.css"', archive_index)
        self.assertIn(f'href="./{self.now[:10]}.html"', archive_index)

    def test_public_site_never_leaks_local_data(self):
        note = self.vault / "00_Inbox" / "private-note.md"
        note.parent.mkdir(parents=True)
        note.write_text("secret", encoding="utf-8")
        self.add_entry(
            "feed-a", "n1", '<img onerror="x">"Quoted" title',
            url="https://a.example/n1",
        )
        # An ingested entry carries local state that must stay out of the site.
        entry_id = self.add_entry("feed-a", "n2", "Processed item")
        with self.store.session() as con:
            con.execute(
                "UPDATE entries SET state='succeeded', output_path=? WHERE id=?",
                (str(note), entry_id),
            )
        self.build()
        blob = self.all_public_output()
        self.assertNotIn(str(self.vault), blob)
        self.assertNotIn("00_Inbox", blob)
        self.assertNotIn("private-note", blob)
        self.assertNotIn(getpass.getuser(), blob)
        self.assertNotIn("full body must never reach the site", blob)
        self.assertNotIn("secret summary", blob)
        self.assertNotIn('<img onerror="x">', blob)
        self.assertIn("&lt;img onerror=", blob)  # titles are HTML-escaped

    def test_feed_and_llms_txt_are_emitted_for_agents(self):
        an_hour_ago = (
            subscription_store.parse_iso(self.now) - timedelta(hours=1)
        ).isoformat()
        self.add_entry("feed-a", "one", "OpenAI releases GPT-6 model", published=an_hour_ago)
        self.add_entry("feed-b", "two", "OpenAI releases GPT-6 model today", published=self.now)
        self.build(site_name="测试情报站")

        feed = (self.output / "feed.xml").read_text(encoding="utf-8")
        self.assertIn('<rss version="2.0"', feed)
        self.assertIn("<language>zh-CN</language>", feed)
        self.assertIn('<guid isPermaLink="false">', feed)
        self.assertIn("<pubDate>", feed)
        # 同一事件跨两个来源聚合为一条 item；最新一条代表事件本身
        self.assertEqual(feed.count("<item>"), 1)
        self.assertIn("<title>OpenAI releases GPT-6 model today</title>", feed)
        self.assertIn("<link>https://feed-b.example/two</link>", feed)
        self.assertIn("Feed A、Feed B", feed)
        self.assertIn("热度 2", feed)
        self.assertEqual(feed.count("<category>"), 2)
        # 没有绝对 --base-url 时不谎报自我地址
        self.assertNotIn("atom:link", feed)

        llms = (self.output / "llms.txt").read_text(encoding="utf-8")
        self.assertTrue(llms.startswith("# 测试情报站\n"))
        for section in ("## 最近事件", "## 订阅源", "## 内容边界"):
            self.assertIn(section, llms)
        self.assertIn("[OpenAI releases GPT-6 model today](https://feed-b.example/two)", llms)
        self.assertIn("Feed A、Feed B", llms)

    def test_feed_advertises_itself_only_with_an_absolute_base_url(self):
        self.add_entry("feed-a", "one", "Solo item", published=self.now)
        self.build(site_name="测试情报站", base_url="https://example.github.io/digest/")
        feed = (self.output / "feed.xml").read_text(encoding="utf-8")
        self.assertIn(
            '<atom:link href="https://example.github.io/digest/feed.xml" '
            'rel="self" type="application/rss+xml"/>',
            feed,
        )
        self.assertIn("<link>https://example.github.io/digest/</link>", feed)
        layout = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="https://example.github.io/digest/feed.xml"', layout)

    def test_expired_events_lose_their_heat_badge(self):
        """A week-old three-source story must not outrank today's reporting."""
        old_stamp = (
            subscription_store.parse_iso(self.now) - timedelta(hours=96)
        ).isoformat()
        self.add_entry("feed-a", "old-a", "Old story about chips", published=old_stamp)
        self.add_entry("feed-b", "old-b", "Old story about chips today", published=old_stamp)
        self.build()
        index = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("heat-badge", index)

    def test_source_health_counts_checks(self):
        for outcome in ("success", "success", "unchanged", "error"):
            self.store.record_source_check(
                "feed-a", provider="generic_byo", outcome=outcome, http_status=200
            )
        self.store.record_source_check(
            "feed-a",
            provider="generic_byo",
            outcome="success",
            http_status=200,
            now="2020-01-01T00:00:00+00:00",
        )
        rows = subscription_site.compute_source_health(
            self.store, self.document, now=self.now
        )
        feed_a = next(row for row in rows if row["id"] == "feed-a")
        self.assertEqual(feed_a["checks"], 4)
        self.assertEqual(feed_a["errors"], 1)
        self.assertEqual(feed_a["success_rate"], 75.0)
        feed_b = next(row for row in rows if row["id"] == "feed-b")
        self.assertEqual(feed_b["checks"], 0)
        self.assertIsNone(feed_b["success_rate"])
        self.add_entry("feed-a", "n1", "Item")
        self.build()
        sources = (self.output / "sources.html").read_text(encoding="utf-8")
        self.assertIn("Feed A", sources)
        self.assertIn("75.0%", sources)

    def test_base_url_prefixes_all_internal_links(self):
        self.add_entry("feed-a", "n1", "Item")
        self.build(base_url="/my-repo")
        index = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/my-repo/style.css"', index)
        self.assertIn('href="/my-repo/sources.html"', index)
        archive = (self.output / "archive" / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'href="/my-repo/archive/{self.now[:10]}.html"', archive)
        # External entry links stay untouched.
        self.assertIn('href="https://feed-a.example/n1"', index)

    def test_empty_window_still_renders_friendly_pages(self):
        code = self.build()
        self.assertEqual(code, 0)
        index = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn("没有订阅更新", index)
        sources = (self.output / "sources.html").read_text(encoding="utf-8")
        self.assertIn("Feed A", sources)
        self.assertIn("—", sources)  # no checks yet: success rate stays blank

    def test_command_dispatch_site_build(self):
        self.add_entry("feed-a", "n1", "Item")
        subscription_store.save_document(self.root / "subscriptions.json", self.document)
        args = types.SimpleNamespace(
            subscribe_command="site",
            site_command="build",
            subscriptions=str(self.root / "subscriptions.json"),
            days=7,
            output=str(self.output),
            site_name="",
            base_url="",
        )
        code = subscriptions.command_subscribe(args, self.config)
        self.assertEqual(code, 0)
        self.assertTrue((self.output / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
