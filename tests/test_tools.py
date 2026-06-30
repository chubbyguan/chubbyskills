import os
import shutil
import tempfile
import unittest

from tools import chubby_ingest
from tools import validate_outputs


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DetectSkillTest(unittest.TestCase):
    def test_detects_common_platforms(self):
        cases = {
            "BV1xx411c7mD": "bilibili",
            "https://www.youtube.com/watch?v=abc": "youtube",
            "https://youtu.be/abc": "youtube",
            "https://v.douyin.com/example/": "douyin",
            "https://x.com/example/status/123456": "x",
            "https://twitter.com/example/status/123456": "x",
            "https://www.xiaohongshu.com/explore/abc": "xiaohongshu",
            "https://mp.weixin.qq.com/s/abc": "wechat",
            "https://www.zhihu.com/video/123": "zhihu",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(chubby_ingest.detect_skill(source), expected)

    def test_detects_local_audio_as_podcast(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            self.assertEqual(chubby_ingest.detect_skill(f.name), "podcast")

    def test_detects_local_pdf_as_wechat(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            self.assertEqual(chubby_ingest.detect_skill(f.name), "wechat")


class OutputValidatorTest(unittest.TestCase):
    def test_examples_are_valid(self):
        examples = os.path.join(ROOT, "examples", "outputs")
        for path in validate_outputs.iter_markdown([examples]):
            with self.subTest(path=path):
                errors = [
                    p for p in validate_outputs.validate_file(path) if p["level"] == "error"
                ]
                self.assertEqual(errors, [])

    def test_missing_frontmatter_is_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as f:
            f.write("# Missing\n")
            f.flush()
            problems = validate_outputs.validate_file(f.name)
        self.assertTrue(any(p["level"] == "error" for p in problems))


class WorkflowCopyTest(unittest.TestCase):
    def test_copy_into_same_vault_directory_is_noop(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "note.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Note\n")
            self.assertEqual(chubby_ingest.copy_into_vault(path, tmpdir), path)
            self.assertTrue(os.path.exists(path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
