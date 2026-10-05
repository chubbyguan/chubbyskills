import importlib.util
import json
import os
import tempfile
import time
import unittest
import unittest.mock

from tools import validate_outputs


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "x-ingest", "scripts", "fetch_tweet.py")
SPEC = importlib.util.spec_from_file_location("x_ingest_fetch_tweet", SCRIPT)
fetch_tweet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_tweet)


class XIngestFallbackTest(unittest.TestCase):
    def test_maps_current_xquik_lookup_response(self):
        data = fetch_tweet.build_json_fallback_data(
            {
                "tweet": {
                    "text": "Current Xquik response #agents",
                    "createdAt": "2026-07-18T12:00:00Z",
                    "likeCount": 11,
                    "replyCount": 4,
                },
                "author": {"name": "Ada", "username": "ada"},
            },
            None,
        )

        self.assertEqual(data["text"], "Current Xquik response #agents")
        self.assertEqual(data["author"], "Ada")
        self.assertEqual(data["screen_name"], "ada")
        self.assertEqual(data["created"], "2026-07-18")
        self.assertEqual(data["likes"], 11)
        self.assertEqual(data["replies"], 4)
        self.assertEqual(data["tags"], ["agents"])

    def test_maps_first_tweet_from_paginated_xquik_response(self):
        data = fetch_tweet.build_json_fallback_data(
            {"data": {"tweets": [{"text": "First result", "likeCount": 0}]}},
            None,
        )

        self.assertEqual(data["text"], "First result")
        self.assertEqual(data["likes"], 0)

    def test_maps_wrapped_structured_tweet(self):
        data = fetch_tweet.build_json_fallback_data(
            {
                "data": {
                    "text": "A useful update #research",
                    "author": {"name": "Ada", "username": "@ada"},
                    "created_at": "2026-07-17T12:00:00Z",
                    "public_metrics": {"like_count": 7, "reply_count": 2},
                }
            },
            None,
        )

        self.assertEqual(data["text"], "A useful update #research")
        self.assertEqual(data["author"], "Ada")
        self.assertEqual(data["screen_name"], "ada")
        self.assertEqual(data["created"], "2026-07-17")
        self.assertEqual(data["likes"], 7)
        self.assertEqual(data["replies"], 2)
        self.assertEqual(data["tags"], ["research"])

    def test_rejects_structured_tweet_without_text(self):
        with self.assertRaisesRegex(ValueError, "does not contain tweet text"):
            fetch_tweet.build_json_fallback_data({"data": {"id": "1"}}, None)

    def test_generated_frontmatter_quotes_user_controlled_scalars(self):
        data = fetch_tweet.build_fallback_data("Public text", None)
        markdown = fetch_tweet.build_markdown(
            data,
            "https://x.com/example/status/1?label=a:b",
            'Update: "quoted" #topic',
            [],
        )

        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as output:
            output.write(markdown)
            output.flush()
            errors = [
                problem
                for problem in validate_outputs.validate_file(output.name)
                if problem["level"] == "error"
            ]

        self.assertIn('title: "Update: \\"quoted\\" #topic"', markdown)
        self.assertIn('source: "https://x.com/example/status/1?label=a:b"', markdown)
        self.assertEqual(errors, [])

    def test_generated_frontmatter_rejects_metric_and_date_injection(self):
        data = fetch_tweet.build_json_fallback_data(
            {
                "text": "Public text",
                "createdAt": "bad\nadmin: true",
                "likeCount": "1\nadmin: true",
                "replyCount": -2,
            },
            None,
        )
        markdown = fetch_tweet.build_markdown(
            data, "https://x.com/example/status/1", "Safe title", []
        )

        self.assertNotIn("admin: true", markdown)
        self.assertRegex(markdown, r"created: \d{4}-\d{2}-\d{2}")
        self.assertIn("likes: \n", markdown)
        self.assertIn("replies: \n", markdown)


class XArticleTest(unittest.TestCase):
    def test_syndication_article_matches_golden_output(self):
        fixture = os.path.join(ROOT, "fixtures", "golden", "x-article-syndication.json")
        golden = os.path.join(ROOT, "fixtures", "golden", "x-article-preview.md")
        with open(fixture, encoding="utf-8") as source:
            data = fetch_tweet.parse_tweet(json.load(source))
        title = fetch_tweet.compute_title(data)
        image_refs = [("url", url) for url in data["photos"]]
        actual = fetch_tweet.build_markdown(
            data, "https://x.com/example/status/2102982854732922880", title, image_refs
        )

        with open(golden, encoding="utf-8") as expected:
            self.assertEqual(actual, expected.read())

    def test_parse_syndication_article_marks_preview(self):
        tw = {
            "user": {"name": "Ada", "screen_name": "ada"},
            "text": "https://t.co/abc",
            "article": {
                "title": "Long post",
                "preview_text": "First bullets only",
                "rest_id": 2102982854732922880,
                "cover_media": {"media_info": {"original_img_url": "https://img"}},
            },
        }
        data = fetch_tweet.parse_tweet(tw)

        self.assertEqual(data["note_type"], "article")
        self.assertEqual(data["article_title"], "Long post")
        self.assertEqual(data["article_rest_id"], "2102982854732922880")
        self.assertTrue(data["article_is_preview"])
        self.assertEqual(data["text"], "First bullets only")

        markdown = fetch_tweet.build_markdown(
            data, "https://x.com/ada/status/1", "Long post", []
        )
        self.assertIn("以下为预览", markdown)

    def test_extract_article_text_prefers_plain_text(self):
        result = {
            "article": {
                "article_results": {
                    "result": {
                        "title": "Long post",
                        "plain_text": "Full body here",
                        "content_state": {"blocks": [{"text": "ignored"}]},
                    }
                }
            }
        }
        title, text = fetch_tweet.extract_article_text(result)
        self.assertEqual((title, text), ("Long post", "Full body here"))

    def test_extract_article_text_falls_back_to_content_state_blocks(self):
        result = {
            "article": {
                "article_results": {
                    "result": {
                        "title": "Long post",
                        "content_state": {
                            "blocks": [
                                {"text": "Para one"},
                                {"text": "  "},
                                {"text": "Para two"},
                            ]
                        },
                    }
                }
            }
        }
        title, text = fetch_tweet.extract_article_text(result)
        self.assertEqual((title, text), ("Long post", "Para one\n\nPara two"))

    def test_extract_article_text_handles_missing_article(self):
        self.assertEqual(fetch_tweet.extract_article_text(None), ("", ""))
        self.assertEqual(fetch_tweet.extract_article_text({}), ("", ""))

    def test_load_cookies_from_string_and_file(self):
        auth, ct0 = fetch_tweet.load_cookies("auth_token=aaa; ct0=bbb")
        self.assertEqual((auth, ct0), ("aaa", "bbb"))
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", encoding="utf-8", delete=False
        ) as f:
            f.write("ct0=t2\nauth_token=a2\n")
            path = f.name
        try:
            self.assertEqual(fetch_tweet.load_cookies(path), ("a2", "t2"))
        finally:
            os.unlink(path)

    def test_load_cookies_rejects_missing_keys(self):
        with self.assertRaisesRegex(ValueError, "auth_token"):
            fetch_tweet.load_cookies("foo=bar")


class XQueryIdDiscoveryTest(unittest.TestCase):
    BUNDLE_JS = (
        'x.exports={queryId:"AbCdEfGhIjKlMnOpQrSt-U",operationName:'
        '"TweetResultByRestId",operationType:"query",metadata:{}};'
        'y.exports={queryId:"AbCdEfGhIjKlMnOpQrSt-U",operationName:'
        '"TweetResultByRestId"};z.exports={queryId:"short",operationName:'
        '"TweetResultByRestId"};w.exports={queryId:"OtherOpQueryId1234567",'
        'operationName:"UserByScreenName"};'
    )

    def _cache(self, tmpdir, ids, fetched_at):
        path = os.path.join(tmpdir, "cache", "qids.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"query_ids": ids, "fetched_at": fetched_at}, f)
        return path

    def test_extract_query_ids_from_js_dedupes_and_filters(self):
        self.assertEqual(
            fetch_tweet.extract_query_ids_from_js(self.BUNDLE_JS),
            ["AbCdEfGhIjKlMnOpQrSt-U"],
        )
        self.assertEqual(fetch_tweet.extract_query_ids_from_js(""), [])
        self.assertEqual(fetch_tweet.extract_query_ids_from_js(None), [])

    def test_fresh_cache_short_circuits_discovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._cache(tmpdir, ["CachedQueryId12345678"], time.time())
            with unittest.mock.patch.object(
                fetch_tweet, "discover_query_ids", side_effect=AssertionError("net")
            ):
                self.assertEqual(
                    fetch_tweet.get_query_ids(cache_path=path),
                    ["CachedQueryId12345678"],
                )

    def test_stale_cache_triggers_discovery_and_rewrites_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._cache(
                tmpdir, ["StaleQueryId123456789"], time.time() - 48 * 3600
            )
            with unittest.mock.patch.object(
                fetch_tweet, "discover_query_ids", return_value=["NewQueryId1234567890"]
            ) as discover:
                ids = fetch_tweet.get_query_ids(cache_path=path)
            self.assertEqual(ids, ["NewQueryId1234567890"])
            discover.assert_called_once()
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["query_ids"], ["NewQueryId1234567890"])

    def test_discovery_failure_falls_back_to_stale_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._cache(
                tmpdir, ["StaleQueryId123456789"], time.time() - 48 * 3600
            )
            with unittest.mock.patch.object(
                fetch_tweet, "discover_query_ids", return_value=[]
            ):
                self.assertEqual(
                    fetch_tweet.get_query_ids(cache_path=path),
                    ["StaleQueryId123456789"],
                )

    def test_discovery_failure_without_cache_falls_back_to_builtin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "missing", "qids.json")
            with unittest.mock.patch.object(
                fetch_tweet, "discover_query_ids", side_effect=RuntimeError("boom")
            ):
                self.assertEqual(
                    fetch_tweet.get_query_ids(cache_path=path),
                    list(fetch_tweet._TWEET_RESULT_QUERY_IDS),
                )

    def test_discover_query_ids_parses_bundle_from_homepage(self):
        homepage = (
            '<script src="https://abs.twimg.com/responsive-web/client-web/'
            'main.abcdef0123456789a.js"></script>'
        )
        fetched = {}

        def fake_fetch(url, cookies=None, timeout=20):
            fetched[url] = True
            if url == "https://x.com/home":
                return homepage
            return self.BUNDLE_JS

        with unittest.mock.patch.object(
            fetch_tweet, "_fetch_url_text", side_effect=fake_fetch
        ):
            ids = fetch_tweet.discover_query_ids(cookies="auth_token=a; ct0=b")
        self.assertEqual(ids, ["AbCdEfGhIjKlMnOpQrSt-U"])
        self.assertIn("https://x.com/home", fetched)


if __name__ == "__main__":
    unittest.main()

def _timeline_tweet(tweet_id, *, parent="", author="ada", author_id="1",
                    conversation="", text="", likes=None, replies=None):
    """A syndication-shaped tweet. `parent` sets the self-reply edge."""
    tweet = {
        "id_str": str(tweet_id),
        "user": {"name": author.title(), "screen_name": author, "id_str": author_id},
        "text": text or f"tweet {tweet_id}",
        "created_at": "Wed Oct 05 00:00:00 +0000 2026",
    }
    if parent:
        tweet["in_reply_to_status_id_str"] = str(parent)
    if conversation:
        tweet["conversation_id_str"] = str(conversation)
    if likes is not None:
        tweet["favorite_count"] = likes
    if replies is not None:
        tweet["conversation_count"] = replies
    return tweet


def _timeline_html(payload):
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></body></html>"
    )


def _timeline_page(entries):
    return _timeline_html({"props": {"pageProps": {"timeline": {"entries": entries}}}})


class XIngestThreadTimelineTest(unittest.TestCase):
    """Parsing the anonymous profile timeline that `--thread` depends on."""

    def test_extracts_tweets_in_page_order(self):
        html = _timeline_page([
            {"content": {"tweet": _timeline_tweet(2)}},
            {"content": {"tweet": _timeline_tweet(1)}},
        ])
        tweets = fetch_tweet.parse_syndication_timeline(html)
        self.assertEqual([t["id_str"] for t in tweets], ["2", "1"])

    def test_missing_next_data_is_a_clear_error(self):
        with self.assertRaises(ValueError) as caught:
            fetch_tweet.parse_syndication_timeline("<html><body>nothing</body></html>")
        self.assertIn("__NEXT_DATA__", str(caught.exception))

    def test_unexpected_shape_is_a_clear_error(self):
        html = _timeline_html({"props": {"pageProps": {"timeline": {"entries": "nope"}}}})
        with self.assertRaises(ValueError) as caught:
            fetch_tweet.parse_syndication_timeline(html)
        self.assertIn("shape", str(caught.exception))

    def test_entries_without_a_tweet_object_are_skipped(self):
        html = _timeline_page([
            {"content": {"tweet": _timeline_tweet(2)}},
            {"content": {}},
            {"content": {"tweet": "not a dict"}},
        ])
        self.assertEqual(len(fetch_tweet.parse_syndication_timeline(html)), 1)


class XIngestThreadCollectionTest(unittest.TestCase):
    """Following the author's direct self-reply chain."""

    def collect(self, root, *timeline):
        return fetch_tweet.collect_thread_tweets(str(root["id_str"]), root, list(timeline))

    def test_follows_the_direct_reply_chain_in_order(self):
        root = _timeline_tweet(100, conversation="100")
        timeline = [
            _timeline_tweet(102, parent="101", conversation="100"),
            _timeline_tweet(101, parent="100", conversation="100"),
            root,
        ]
        thread = self.collect(root, *timeline)
        self.assertEqual([t["id_str"] for t in thread], ["100", "101", "102"])

    def test_other_users_replies_are_never_included(self):
        root = _timeline_tweet(100, conversation="100")
        timeline = [
            _timeline_tweet(101, parent="100", conversation="100"),
            _timeline_tweet(200, parent="101", author="bob", author_id="2", conversation="100"),
            _timeline_tweet(201, parent="200", author="bob", author_id="2", conversation="100"),
        ]
        thread = self.collect(root, *timeline)
        self.assertEqual([t["id_str"] for t in thread], ["100", "101"])

    def test_replies_pointing_outside_the_chain_are_ignored(self):
        root = _timeline_tweet(100, conversation="100")
        timeline = [
            _timeline_tweet(101, parent="100", conversation="100"),
            # The author's own reply, but to a different branch of their timeline.
            _timeline_tweet(900, parent="800", conversation="800"),
        ]
        thread = self.collect(root, *timeline)
        self.assertEqual([t["id_str"] for t in thread], ["100", "101"])

    def test_no_self_replies_returns_the_root_alone(self):
        root = _timeline_tweet(100, conversation="100")
        self.assertEqual([t["id_str"] for t in self.collect(root)], ["100"])

    def test_a_cycle_terminates_instead_of_hanging(self):
        root = _timeline_tweet(100, conversation="100")
        timeline = [
            _timeline_tweet(101, parent="100", conversation="100"),
            _timeline_tweet(100, conversation="100"),
        ]
        self.assertEqual([t["id_str"] for t in self.collect(root, *timeline)], ["100", "101"])

    def test_a_candidate_from_another_conversation_is_dropped(self):
        """The guard matters because the upstream timeline may be inconsistent.

        X's conversation id always matches for a real direct reply, but the
        syndication endpoint is documented as possibly stale or incomplete — so
        a tweet that merely *points* at the root is not enough to include it.
        """
        root = _timeline_tweet(100, conversation="100")
        timeline = [_timeline_tweet(101, parent="100", conversation="777")]
        self.assertEqual([t["id_str"] for t in self.collect(root, *timeline)], ["100"])


class XIngestThreadMarkdownTest(unittest.TestCase):
    """Rendering the collected thread as one note."""

    def section(self, tweet_id, *, text="", likes=None, replies=None, **extra):
        data = fetch_tweet.parse_tweet(
            _timeline_tweet(tweet_id, text=text, likes=likes, replies=replies)
        )
        data.update(extra)
        return {"data": data, "image_refs": [], "transcript": None}

    def test_frontmatter_records_the_thread_and_aggregates_engagement(self):
        sections = [
            self.section(100, text="first", likes=10, replies=2),
            self.section(101, text="second", likes=5, replies=1),
        ]
        markdown = fetch_tweet.build_thread_markdown(
            sections, "https://x.com/ada/status/100", "标题"
        )
        self.assertIn("note_type: thread", markdown)
        self.assertIn("thread_count: 2", markdown)
        self.assertIn('thread_ids: ["100", "101"]', markdown)
        self.assertIn("likes: 15", markdown)
        self.assertIn("replies: 3", markdown)

    def test_each_tweet_gets_its_own_section(self):
        sections = [self.section(100, text="first"), self.section(101, text="second")]
        markdown = fetch_tweet.build_thread_markdown(
            sections, "https://x.com/ada/status/100", "标题"
        )
        self.assertIn("## 推文 1", markdown)
        self.assertIn("## 推文 2", markdown)
        self.assertLess(markdown.index("## 推文 1"), markdown.index("## 推文 2"))
        self.assertIn("first", markdown)
        self.assertIn("second", markdown)

    def test_missing_engagement_stays_empty_rather_than_zero(self):
        sections = [self.section(100, text="first"), self.section(101, text="second")]
        markdown = fetch_tweet.build_thread_markdown(
            sections, "https://x.com/ada/status/100", "标题"
        )
        self.assertIn("likes: \n", markdown)
        self.assertIn("replies: \n", markdown)

    def test_transcripts_and_image_refs_render_per_section(self):
        first = self.section(100, text="first")
        first["transcript"] = "视频文字稿内容"
        second = self.section(101, text="second")
        second["image_refs"] = [("local", "img_00_1.jpg"), ("url", "https://img/2.jpg")]
        markdown = fetch_tweet.build_thread_markdown(
            [first, second], "https://x.com/ada/status/100", "标题"
        )
        self.assertIn("### 视频文字稿", markdown)
        self.assertIn("视频文字稿内容", markdown)
        self.assertIn("![](img_00_1.jpg)", markdown)
        self.assertIn("- https://img/2.jpg", markdown)

    def test_saved_thread_note_is_written_as_markdown(self):
        sections = [self.section(100, text="first"), self.section(101, text="second")]
        with tempfile.TemporaryDirectory() as folder:
            path = fetch_tweet.save_thread_markdown(
                sections, "https://x.com/ada/status/100", folder, "标题"
            )
            markdown = open(path, encoding="utf-8").read()
        self.assertTrue(path.endswith(".md"))
        self.assertIn("note_type: thread", markdown)
