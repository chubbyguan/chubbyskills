import importlib.util
import io
import json
import os
import tempfile
import time
import unittest
import unittest.mock   # or: from unittest import mock
from io import BytesIO

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
