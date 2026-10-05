import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chubby_common import ytdlp
from chubby_common.config import PlatformConfig


FAIL = "import sys; sys.stderr.write('ERROR: HTTP Error 412: Precondition Failed'); sys.exit(7)"
SUCCEED = "from pathlib import Path; import sys; Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes(b'audio')"


class YtdlpFailureTest(unittest.TestCase):
    def setUp(self):
        self.cfg = PlatformConfig(
            id="bilibili", name="Bilibili", tag="B站", default_title="视频", max_retry=2
        )
        self.run_process = subprocess.run
        ensure = patch.object(ytdlp.deps, "ensure_ytdlp")
        ensure.start()
        self.addCleanup(ensure.stop)

    def child(self, script):
        # Exercise subprocess exit handling without yt-dlp or network access.
        def run(cmd, **kwargs):
            return self.run_process([sys.executable, "-c", script, *cmd], **kwargs)

        return run

    def test_captured_failure_raises_with_exit_code_and_stderr(self):
        with patch.object(ytdlp.subprocess, "run", side_effect=self.child(FAIL)):
            with self.assertRaises(subprocess.CalledProcessError) as ctx:
                ytdlp.run_ydl(self.cfg, ["https://example.invalid/video"], timeout=10)
        self.assertEqual(ctx.exception.returncode, 7)
        self.assertIn("HTTP Error 412", ctx.exception.stderr)

    def test_uncaptured_failure_still_raises(self):
        with patch.object(ytdlp.subprocess, "run", side_effect=self.child("raise SystemExit(7)")):
            with self.assertRaises(subprocess.CalledProcessError) as ctx:
                ytdlp.run_ydl(self.cfg, [], timeout=10, capture=False)
        self.assertEqual(ctx.exception.returncode, 7)

    def test_captured_success_keeps_stdout(self):
        with patch.object(ytdlp.subprocess, "run", side_effect=self.child("print('video title')")):
            result = ytdlp.run_ydl(self.cfg, [], timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "video title")

    def test_download_retries_then_returns_file(self):
        with tempfile.TemporaryDirectory() as folder:
            scripts = iter((FAIL, SUCCEED))

            def run(cmd, **kwargs):
                return self.child(next(scripts))(cmd, **kwargs)

            with patch.object(ytdlp.subprocess, "run", side_effect=run) as process, patch.object(
                ytdlp.time, "sleep"
            ) as sleep:
                result = ytdlp.download_audio(self.cfg, "https://example.invalid/video", folder)
            self.assertEqual(result, os.path.join(folder, "audio.mp3"))
            self.assertEqual(Path(result).read_bytes(), b"audio")
            self.assertEqual(process.call_count, 2)
            sleep.assert_called_once_with(2)

    def test_exhausted_retries_report_real_failure(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
            ytdlp.subprocess, "run", side_effect=self.child(FAIL)
        ) as process, patch.object(ytdlp.time, "sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                ytdlp.download_audio(self.cfg, "https://example.invalid/video", folder)
        message = str(ctx.exception)
        self.assertEqual(process.call_count, self.cfg.max_retry)
        self.assertIn("退出码 7", message)
        self.assertIn("HTTP Error 412: Precondition Failed", message)
        self.assertNotIn("退出成功", message)

    def test_failure_without_stderr_still_reports_exit_code(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
            ytdlp.subprocess, "run", side_effect=self.child("raise SystemExit(9)")
        ), patch.object(ytdlp.time, "sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                ytdlp.download_audio(self.cfg, "https://example.invalid/video", folder)
        self.assertIn("退出码 9", str(ctx.exception))
        self.assertNotIn("退出成功", str(ctx.exception))

    def test_zero_exit_without_file_keeps_missing_file_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
            ytdlp.subprocess, "run", side_effect=self.child("pass")
        ) as process:
            with self.assertRaisesRegex(RuntimeError, "退出成功但未产出音频文件"):
                ytdlp.download_audio(self.cfg, "https://example.invalid/video", folder)
        self.assertEqual(process.call_count, 1)


if __name__ == "__main__":
    unittest.main()
