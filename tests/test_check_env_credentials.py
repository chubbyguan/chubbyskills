"""The credentials report must inform without ever echoing a secret.

Scanning tools reprint terminal output, and this report is meant to be pasted
into an issue when someone asks for help — so a leaked value here travels.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_env


class CredentialsReportTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def render(self, *, state_file=None, env=None):
        buffer = io.StringIO()
        with patch.dict("os.environ", env or {}, clear=True):
            with contextlib.redirect_stdout(buffer):
                check_env.credentials_report(state_file)
        return buffer.getvalue()

    def test_secret_values_are_never_printed(self):
        output = self.render(env={"X_COOKIES": "auth_token=SUPERSECRET; ct0=ALSOSECRET"})
        self.assertNotIn("SUPERSECRET", output)
        self.assertNotIn("ALSOSECRET", output)
        self.assertIn("X_COOKIES", output)
        self.assertIn("值不显示", output)

    def test_non_secret_values_are_shown(self):
        output = self.render(env={"YTDLP_COOKIES_FROM_BROWSER": "chrome"})
        self.assertIn("chrome", output)

    def test_missing_credentials_explain_how_to_obtain_them(self):
        output = self.render(env={})
        self.assertIn("未配置", output)
        self.assertIn("auth_token", output)  # the X instructions, not just the name

    def test_api_keys_are_treated_as_secrets_too(self):
        output = self.render(env={"DEEPSEEK_API_KEY": "sk-do-not-print-me"})
        self.assertNotIn("sk-do-not-print-me", output)

    def test_last_real_outcome_is_read_from_the_journal(self):
        journal = self.root / "runs.jsonl"
        journal.write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    {"skill": "x", "status": "success", "started_at": "2026-10-01T10:00:00+08:00"},
                    {"skill": "x", "status": "failed", "started_at": "2026-10-05T11:14:00+08:00", "error": "cookies expired"},
                    {"skill": "youtube", "status": "success", "started_at": "2026-10-04T09:00:00+08:00"},
                )
            )
            + "\n",
            encoding="utf-8",
        )
        output = self.render(state_file=str(journal), env={})
        # The newest row wins, and a failure carries its reason.
        self.assertIn("2026-10-05 11:14", output)
        self.assertNotIn("2026-10-01 10:00", output)
        self.assertIn("cookies expired", output)

    def test_missing_journal_is_reported_not_crashed(self):
        output = self.render(state_file=str(self.root / "absent.jsonl"), env={})
        self.assertIn("还没有记录", output)

    def test_corrupt_journal_lines_are_skipped(self):
        journal = self.root / "runs.jsonl"
        journal.write_text('{"skill": "x", "status": "success", "started_at": "2026-10-05T11:14:00+08:00"}\nnot json\n', encoding="utf-8")
        output = self.render(state_file=str(journal), env={})
        self.assertIn("2026-10-05 11:14", output)


if __name__ == "__main__":
    unittest.main()
