import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from chubby_common import deps, llm, markdown, vtt
from chubby_common.config import PlatformConfig


class SanitizeFilenameTest(unittest.TestCase):
    def test_strips_illegal_chars(self):
        self.assertEqual(markdown.sanitize_filename('a/b:c*?"<>|\\'), "abc")

    def test_collapses_whitespace_to_dash(self):
        self.assertEqual(markdown.sanitize_filename("  Hello   World  "), "Hello-World")

    def test_empty_or_none_falls_back(self):
        self.assertEqual(markdown.sanitize_filename("", "默认"), "默认")
        self.assertEqual(markdown.sanitize_filename(None, "note"), "note")
        self.assertEqual(markdown.sanitize_filename("///"), "note")

    def test_truncates_at_50_chars(self):
        self.assertEqual(len(markdown.sanitize_filename("x" * 100)), 50)


class NoteMarkdownTest(unittest.TestCase):
    def test_builds_frontmatter_and_body(self):
        text = markdown.note_markdown(
            "标题",
            "正文",
            {"type": "note", "platform": "x", "tags": "[X]", "source": "https://x.com/1", "author": ""},
            created="2026-08-18",
        )
        self.assertTrue(text.startswith("---\ntitle: 标题\ncreated: 2026-08-18\n"))
        self.assertIn("platform: x", text)
        self.assertIn("# 标题", text)
        self.assertIn("正文", text)
        self.assertTrue(text.rstrip().endswith("正文"))


class ParseJsonResponseTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(llm.parse_json_response('{"a": 1}'), {"a": 1})

    def test_code_fence_wrapped(self):
        raw = '```json\n{"a": 1}\n```'
        self.assertEqual(llm.parse_json_response(raw), {"a": 1})

    def test_surrounding_noise(self):
        raw = '好的，结果如下：{"a": 1} 希望有帮助'
        self.assertEqual(llm.parse_json_response(raw), {"a": 1})

    def test_invalid_json_raises_readable_error(self):
        with self.assertRaises(RuntimeError) as ctx:
            llm.parse_json_response("不是 JSON")
        self.assertIn("合法 JSON", str(ctx.exception))


class SafeIntTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(llm.safe_int("4", 3), 4)
        self.assertEqual(llm.safe_int(2, 3), 2)

    def test_invalid_falls_back(self):
        self.assertEqual(llm.safe_int("很高", 3), 3)
        self.assertEqual(llm.safe_int(None, 3), 3)
        self.assertEqual(llm.safe_int("", 3), 3)


class PlatformConfigTest(unittest.TestCase):
    def test_default_tmp_prefix_uses_id(self):
        cfg = PlatformConfig(id="tiktok", name="TikTok", tag="TikTok", default_title="T")
        self.assertEqual(cfg.tmp_prefix, "tiktok")

    def test_frozen(self):
        cfg = PlatformConfig(id="x", name="X", tag="X", default_title="X")
        with self.assertRaises(Exception):
            cfg.name = "changed"


class VttTest(unittest.TestCase):
    def test_parse_vtt_strips_timestamps_and_tags(self):
        import tempfile

        content = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "第一行<00:00:01.500><c>测试</c>\n\n"
            "00:00:03.000 --> 00:00:04.000\n"
            "第一行\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".vtt", encoding="utf-8", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            text = vtt.parse_vtt(path)
            # 第一行去标签后为「第一行测试」，第二行内容不同所以保留
            self.assertEqual(text, "第一行测试\n第一行")
        finally:
            os.unlink(path)

    def test_pick_subtitle_prefers_priority(self):
        files = ["sub.en.vtt", "sub.zh-cn.vtt", "sub.zh.vtt"]
        chosen = vtt.pick_subtitle(files, ("en", "zh-cn", "zh"))
        self.assertEqual(chosen, "sub.en.vtt")
        chosen_zh = vtt.pick_subtitle(files, ("zh-cn", "zh", "en"))
        self.assertEqual(chosen_zh, "sub.zh-cn.vtt")


class DepsTest(unittest.TestCase):
    def test_check_python_module_missing_exits(self):
        with self.assertRaises(SystemExit):
            deps.check_python_module("chubby_definitely_not_a_module_xyz", "pip install x")


if __name__ == "__main__":
    unittest.main()
