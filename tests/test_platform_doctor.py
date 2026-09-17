from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from tools import check_env


class PlatformDoctorTest(unittest.TestCase):
    def run_doctor(self, platform, available):
        output = io.StringIO()
        with patch.object(check_env.platform_health, "check_dependency", side_effect=lambda dep: (dep in available, dep.split(":", 1)[-1])), redirect_stdout(output):
            result = check_env.main(["--platform", platform, "--json"])
        return result, json.loads(output.getvalue())

    def test_missing_wechat_parser_fails_selected_path(self):
        code, report = self.run_doctor("wechat", set())
        self.assertEqual(code, 1)
        self.assertFalse(report["platforms"][0]["ready"])
        self.assertEqual(report["platforms"][0]["missing_required"], ["bs4"])

    def test_x_text_does_not_require_optional_transcription_stack(self):
        code, report = self.run_doctor("x", set())
        self.assertEqual(code, 0)
        self.assertTrue(report["platforms"][0]["ready"])

    def test_subtitle_path_succeeds_without_funasr(self):
        code, report = self.run_doctor("bilibili", {"cmd:yt-dlp"})
        self.assertEqual(code, 0)
        self.assertTrue(report["platforms"][0]["ready"])
        self.assertIn("funasr", report["platforms"][0]["missing_optional"])

    def test_audio_path_requires_its_own_dependencies(self):
        code, report = self.run_doctor("podcast", {"cmd:ffmpeg"})
        self.assertEqual(code, 1)
        self.assertEqual(report["platforms"][0]["missing_required"], ["faster_whisper"])


if __name__ == "__main__":
    unittest.main()
