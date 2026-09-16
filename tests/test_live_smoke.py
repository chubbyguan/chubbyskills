import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import platform_smoke


class LiveSmokeTest(unittest.TestCase):
    def test_command_names_do_not_override_real_error_type(self):
        self.assertEqual(platform_smoke.classify_failure("yt-dlp exited with HTTP 403"), "auth_or_cookie")
        self.assertEqual(platform_smoke.classify_failure("❌ 缺少 Python 依赖 `funasr`"), "missing_dependency")

    def test_timeout_retains_partial_process_log(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            platform_smoke, "run_process",
            side_effect=subprocess.TimeoutExpired(["python"], 150, output=b"partial output", stderr=b"partial error"),
        ):
            result = platform_smoke.pipeline_smoke(
                {"id": "x"}, "https://x.com/example/status/123", [], "live", artifacts_dir=tmpdir)
            log = Path(result["evidence_path"]).with_name("process.log").read_text()
            self.assertIn("partial output", log)
            self.assertIn("partial error", log)
            self.assertEqual(result["failure_kind"], "network")

    def test_require_live_rejects_empty_or_skipped_evidence(self):
        self.assertTrue(platform_smoke.has_failures([], require_live=True))
        self.assertTrue(platform_smoke.has_failures(
            [{"mode": "offline", "status": "passed"}], require_live=True))
        self.assertTrue(platform_smoke.has_failures(
            [{"mode": "live", "status": "skipped"}], require_live=True))

    def test_selected_platform_requires_a_source(self):
        with patch.dict(os.environ, {}, clear=True):
            results = platform_smoke.run_matrix(mode="live", platform_ids=["x"])
        self.assertEqual([item["platform"] for item in results], ["x"])
        self.assertEqual(results[0]["status"], "skipped")
        self.assertTrue(platform_smoke.has_failures(results, require_live=True))
        with self.assertRaises(ValueError):
            platform_smoke.run_matrix(mode="live", platform_ids=["typo"])

    def test_fallback_output_survives_and_has_traceable_metadata(self):
        platform = next(p for p in platform_smoke.load_platforms(
            platform_smoke.platform_health.DEFAULT_PLATFORM_DIR) if p["id"] == "x")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = platform_smoke.pipeline_smoke(
                platform, "https://x.com/example/status/1234567890",
                ["--fallback-only", "--fallback-text", str(platform_smoke.FALLBACK_TEXT)],
                "fallback", artifacts_dir=tmpdir)
            self.assertEqual(result["status"], "passed", result)
            self.assertTrue(Path(result["output_path"]).is_file())
            evidence = json.loads(Path(result["evidence_path"]).read_text())
            self.assertEqual(evidence["source"], "https://x.com/example/status/1234567890")
            self.assertEqual(len(evidence["output_sha256"]), 64)
            self.assertGreater(evidence["body_chars"], 0)
            self.assertFalse(evidence["human_verified"])
            self.assertIn("python", evidence["runtime"])

    def test_failed_run_retains_error_evidence(self):
        platform = {"id": "x", "name": "X"}
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            platform_smoke, "run_process",
            return_value=subprocess.CompletedProcess([], 1, "", "HTTP Error 403: Forbidden"),
        ):
            result = platform_smoke.pipeline_smoke(
                platform, "https://x.com/example/status/123", [], "live", artifacts_dir=tmpdir)
            evidence = json.loads(Path(result["evidence_path"]).read_text())
            self.assertEqual(evidence["status"], "failed")
            self.assertEqual(evidence["failure_kind"], "auth_or_cookie")
            self.assertFalse(evidence["human_verified"])


if __name__ == "__main__":
    unittest.main()
