import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_identity import normalize_source, source_digest


class SourceIdentityTest(unittest.TestCase):
    def test_youtube_variants_share_a_video_identity(self):
        for source in (
            "https://www.youtube.com/watch?v=aircAruvnKk&list=PL123&t=20",
            "https://youtu.be/aircAruvnKk?si=tracking",
            "https://m.youtube.com/shorts/aircAruvnKk",
            "https://www.youtube.com/embed/aircAruvnKk#t=10",
        ):
            with self.subTest(source=source):
                self.assertEqual(normalize_source(source), "youtube:aircAruvnKk")

    def test_bilibili_bv_and_default_part_share_identity(self):
        for source in (
            "BV1mw4m1r7Su",
            "https://www.bilibili.com/video/BV1mw4m1r7Su/",
            "https://m.bilibili.com/video/BV1mw4m1r7Su?p=1&vd_source=tracking",
        ):
            with self.subTest(source=source):
                self.assertEqual(normalize_source(source), "bilibili:BV1mw4m1r7Su:p1")
        self.assertEqual(
            normalize_source("https://www.bilibili.com/video/BV1mw4m1r7Su/?p=2"),
            "bilibili:BV1mw4m1r7Su:p2",
        )

    def test_x_and_twitter_status_variants_share_identity(self):
        for source in (
            "https://x.com/OpenAI/status/1663696190960173056?s=20",
            "https://twitter.com/OpenAI/status/1663696190960173056",
            "https://mobile.twitter.com/OpenAI/status/1663696190960173056/photo/1",
            "https://x.com/i/web/status/1663696190960173056",
        ):
            with self.subTest(source=source):
                self.assertEqual(normalize_source(source), "x:1663696190960173056")

    def test_untrusted_hosts_and_ambiguous_platform_urls_stay_distinct(self):
        sources = (
            "https://youtube.com.evil.test/watch?v=aircAruvnKk",
            "https://evil.test/youtu.be/aircAruvnKk",
            "https://x.com.evil.test/OpenAI/status/1663696190960173056",
            "https://x.com@evil.test/OpenAI/status/1663696190960173056",
            "https://user:pass@x.com/OpenAI/status/1663696190960173056",
            "https://x.com:8443/OpenAI/status/1663696190960173056",
            "https://bilibili.com.evil.test/video/BV1mw4m1r7Su/",
            "https://www.youtube.com/watch?v=aircAruvnKk&v=dQw4w9WgXcQ",
            "https://www.bilibili.com/video/BV1mw4m1r7Su/?p=2&p=3",
            "https://www.bilibili.com/video/BV1mw4m1r7Su/?p=0",
            "https://www.bilibili.com/video/BV1mw4m1r7Su/?p=unknown",
            "https://youtu.be/not-a-video-id",
            "https://x.com/OpenAI/status/123/unknown",
            "https://[broken.example/",
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(normalize_source(source), source)

    def test_other_urls_preserve_query_fragment_and_case(self):
        source = "https://Example.test/Article?a=1&a=2&token=Example#Part-2"
        self.assertEqual(normalize_source(source), source)
        self.assertNotEqual(source_digest(source), source_digest(source + "-different"))

    def test_local_relative_absolute_and_symlink_paths_share_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "音频 sample.wav"
            source.write_bytes(b"first audio contents")
            alias = root / "alias.wav"
            alias.symlink_to(source)
            expected = normalize_source(str(source))
            self.assertEqual(normalize_source(source.name, base_dir=root), expected)
            self.assertEqual(normalize_source(str(alias)), expected)
            self.assertIn(str(source.resolve()), expected)
            self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest(), expected)

    def test_changed_local_contents_change_identity_even_at_the_same_size(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.wav"
            source.write_bytes(b"first")
            before = source_digest(str(source))
            source.write_bytes(b"other")
            self.assertNotEqual(source_digest(str(source)), before)

    def test_missing_files_and_directories_preserve_original_input(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(normalize_source("missing.wav", base_dir=directory), "missing.wav")
            self.assertEqual(normalize_source(directory), directory)

    def test_digest_is_normalized_identity_sha256_prefix(self):
        source = "https://youtu.be/aircAruvnKk"
        expected = hashlib.sha256(b"youtube:aircAruvnKk").hexdigest()[:16]
        self.assertEqual(source_digest(source), expected)
        self.assertRegex(source_digest(source), r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
