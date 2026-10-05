import importlib.util
import io
import os
import tempfile
import unittest
from io import BytesIO
from unittest import mock

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


class XThreadTest(unittest.TestCase):
    def test_parse_syndication_timeline_extracts_tweet_entries(self):
        payload = {
            "props": {
                "pageProps": {
                    "timeline": {
                        "entries": [
                            {"content": {"tweet": {"id_str": "2", "text": "Reply"}}},
                            {"content": {"tweet": {"id_str": "3", "text": "Next"}}},
                            {"content": {"other": {"id_str": "ignored"}}},
                        ]
                    }
                }
            }
        }
        html = (
            '<script id="__NEXT_DATA__" type="application/json">'
            + fetch_tweet.json.dumps(payload)
            + "</script>"
        )

        self.assertEqual(
            fetch_tweet.parse_syndication_timeline(html),
            [{"id_str": "2", "text": "Reply"}, {"id_str": "3", "text": "Next"}],
        )
        with self.assertRaisesRegex(ValueError, "__NEXT_DATA__"):
            fetch_tweet.parse_syndication_timeline("<html></html>")

    def test_fetch_author_timeline_uses_public_replies_enabled_endpoint(self):
        html = (
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"timeline":{"entries":[]}}}}'
            "</script>"
        )
        with (
            mock.patch.object(fetch_tweet.time, "sleep") as sleep,
            mock.patch.object(
                fetch_tweet.urllib.request,
                "urlopen",
                return_value=BytesIO(html.encode()),
            ) as urlopen,
        ):
            tweets = fetch_tweet.fetch_author_timeline("ada")

        self.assertEqual(tweets, [])
        self.assertIn("showReplies=true", urlopen.call_args.args[0].full_url)
        sleep.assert_called_once_with(fetch_tweet.THREAD_REQUEST_DELAY_SECONDS)

    def test_collect_thread_follows_only_same_author_direct_replies(self):
        root = {
            "id_str": "100",
            "user": {"id_str": "ada-id", "screen_name": "ada"},
        }
        timeline = [
            {
                "id_str": "102",
                "conversation_id_str": "100",
                "in_reply_to_status_id_str": "101",
                "user": {"id_str": "ada-id", "screen_name": "ada"},
            },
            {
                "id_str": "101",
                "conversation_id_str": "100",
                "in_reply_to_status_id_str": "100",
                "user": {"id_str": "ada-id", "screen_name": "ada"},
            },
            {
                "id_str": "103",
                "conversation_id_str": "100",
                "in_reply_to_status_id_str": "100",
                "user": {"id_str": "other-id", "screen_name": "other"},
            },
            {
                "id_str": "104",
                "conversation_id_str": "999",
                "in_reply_to_status_id_str": "101",
                "user": {"id_str": "ada-id", "screen_name": "ada"},
            },
        ]

        thread = fetch_tweet.collect_thread_tweets("100", root, timeline)

        self.assertEqual([tweet["id_str"] for tweet in thread], ["100", "101", "102"])

    def test_thread_markdown_has_thread_frontmatter_and_ordered_media_sections(self):
        first = fetch_tweet.parse_tweet(
            {
                "id_str": "100",
                "user": {"name": "Ada", "screen_name": "ada"},
                "text": "First #research",
                "favorite_count": 3,
                "conversation_count": 1,
                "photos": [{"url": "https://img.example/first.jpg"}],
            }
        )
        second = fetch_tweet.parse_tweet(
            {
                "id_str": "101",
                "user": {"name": "Ada", "screen_name": "ada"},
                "text": "Second #video",
                "favorite_count": 4,
                "conversation_count": 2,
                "video": {
                    "variants": [
                        {
                            "type": "video/mp4",
                            "bitrate": 100,
                            "src": "https://video.example/clip.mp4",
                        }
                    ]
                },
            }
        )
        markdown = fetch_tweet.build_thread_markdown(
            [
                {
                    "data": first,
                    "image_refs": [("local", "Thread.assets/tweet_01_img_1.jpg")],
                    "transcript": None,
                },
                {
                    "data": second,
                    "image_refs": [],
                    "transcript": "Video words",
                },
            ],
            "https://x.com/ada/status/100",
            "Thread title",
        )

        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as output:
            output.write(markdown)
            output.flush()
            errors = [
                problem
                for problem in validate_outputs.validate_file(output.name)
                if problem["level"] == "error"
            ]

        self.assertIn("note_type: thread", markdown)
        self.assertIn("thread_count: 2", markdown)
        self.assertIn('thread_ids: ["100", "101"]', markdown)
        self.assertIn("likes: 7", markdown)
        self.assertIn("replies: 3", markdown)
        self.assertLess(markdown.index("First #research"), markdown.index("Second #video"))
        self.assertIn("![](Thread.assets/tweet_01_img_1.jpg)", markdown)
        self.assertIn("### 视频文字稿\n\nVideo words", markdown)
        self.assertEqual(errors, [])

    def test_thread_cli_processes_each_tweet_media_and_saves_one_markdown(self):
        root = {
            "id_str": "100",
            "user": {"name": "Ada", "screen_name": "ada"},
            "text": "First post",
            "photos": [{"url": "https://img.example/first.jpg"}],
        }
        reply = {
            "id_str": "101",
            "conversation_id_str": "100",
            "in_reply_to_status_id_str": "100",
            "user": {"name": "Ada", "screen_name": "ada"},
            "text": "Second post",
            "video": {
                "variants": [
                    {
                        "type": "video/mp4",
                        "bitrate": 100,
                        "src": "https://video.example/clip.mp4",
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as output_dir:
            with (
                mock.patch.object(
                    fetch_tweet,
                    "fetch_tweet",
                    return_value=root,
                ),
                mock.patch.object(
                    fetch_tweet,
                    "fetch_author_timeline",
                    return_value=[reply],
                ),
                mock.patch.object(
                    fetch_tweet,
                    "download_images",
                    return_value=[("local", "First-post.assets/tweet_01_img_1.jpg")],
                ) as download_images,
                mock.patch.object(
                    fetch_tweet, "transcribe_video", return_value="Video words"
                ) as transcribe_video,
                mock.patch(
                    "sys.argv",
                    [
                        "fetch_tweet.py",
                        "https://x.com/ada/status/100",
                        "--output",
                        output_dir,
                        "--thread",
                    ],
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO),
            ):
                fetch_tweet.main()

            output_path = os.path.join(output_dir, "First-post.md")
            with open(output_path, encoding="utf-8") as saved:
                markdown = saved.read()

        self.assertIn("thread_count: 2", markdown)
        self.assertIn("## 推文 2", markdown)
        self.assertIn("![](First-post.assets/tweet_01_img_1.jpg)", markdown)
        self.assertIn("### 视频文字稿\n\nVideo words", markdown)
        download_images.assert_called_once()
        self.assertEqual(download_images.call_args.args[3], "tweet_01_")
        transcribe_video.assert_called_once_with("https://video.example/clip.mp4")


if __name__ == "__main__":
    unittest.main()
