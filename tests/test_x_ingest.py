import importlib.util
import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
