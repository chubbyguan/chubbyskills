import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "douyin-transcribe" / "scripts" / "download_douyin_audio.py"
SPEC = importlib.util.spec_from_file_location("douyin_download", SCRIPT)
douyin_download = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = douyin_download
SPEC.loader.exec_module(douyin_download)


class DouyinDownloadFallbackTest(unittest.TestCase):
    def test_spider_shell_page_falls_back_to_ytdlp(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = __import__("subprocess").CompletedProcess([], 0, "<html></html>", "")
            with patch.object(
                douyin_download.subprocess, "run", return_value=completed
            ), patch.object(
                douyin_download, "_download_with_ytdlp", return_value=("/tmp/a.mp3", "标题")
            ) as fallback, patch.object(douyin_download.deps, "ensure_ffmpeg"):
                path, title = douyin_download.download_audio("7660416997045357850", tmp)
            self.assertEqual((path, title), ("/tmp/a.mp3", "标题"))
            fallback.assert_called_once()
            self.assertIn(
                "www.douyin.com/video/7660416997045357850", fallback.call_args[0][0]
            )

    def test_valid_share_page_does_not_fallback(self):
        html = (
            '<script>window._ROUTER_DATA = {"loaderData": {"video_(id)/page":'
            ' {"videoInfoRes": {"item_list": [{"desc": "正常标题",'
            ' "video": {"play_addr": {"url_list": ["https://playwm.example/v"]}}}]}}}}'
            "</script>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            completed_download = __import__("subprocess").CompletedProcess([], 0, "", "")
            calls = []

            def fake_run(command, **kwargs):
                calls.append(command)
                if "curl" in command[0] and "-o" not in command:
                    return __import__("subprocess").CompletedProcess([], 0, html, "")
                if "-o" in command:  # video download
                    Path(command[command.index("-o") + 1]).write_bytes(b"v")
                elif command[0] == "ffmpeg":  # audio extraction
                    Path(command[-1]).write_bytes(b"a")
                return completed_download

            with patch.object(
                douyin_download.subprocess, "run", side_effect=fake_run
            ), patch.object(douyin_download.deps, "ensure_ffmpeg"), patch.object(
                douyin_download, "_download_with_ytdlp"
            ) as fallback:
                path, title = douyin_download.download_audio("123", tmp)
            self.assertEqual(title, "正常标题")
            fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
