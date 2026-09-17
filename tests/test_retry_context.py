import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import chubby


class RetryContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = dict(
            chubby.DEFAULT_CONFIG,
            state_file=str(self.root / "state.jsonl"),
            report_dir=str(self.root / "reports"),
        )
        self.args = types.SimpleNamespace(
            output=None,
            vault=None,
            skill=None,
            enrich=None,
            dry_run=False,
            refresh=False,
            timeout=None,
            extra=[],
            run_id=None,
            all_failed=False,
            source=None,
        )
        self.target = dict(
            run_id="failed-1",
            source="https://youtu.be/aircAruvnKk",
            status="failed",
            source_hash="abcdef123456abcd",
            skill="youtube",
            output_dir=str(self.root / "old-output"),
            vault_dir=str(self.root / "old-vault"),
            enrich=True,
            execution={
                "output_dir": str(self.root / "old-output"),
                "vault_dir": str(self.root / "old-vault"),
                "enrich": True,
                "skill": "youtube",
                "extra": ["--no-translate"],
                "timeout_seconds": 73,
                "vault_root": "",
                "index_db": "",
            },
        )

    def test_retry_restores_original_execution_and_explicit_overrides(self):
        chubby.append_record(self.config, self.target)

        def fake(source, args, config, **kwargs):
            self.assertEqual(args.output, self.target["output_dir"])
            self.assertEqual(args.vault, str(self.root / "new-vault"))
            self.assertIs(args.enrich, True)
            self.assertEqual(args.extra, ["--no-translate", "--no-subtitle"])
            self.assertEqual(args.timeout, 73)
            return dict(self.target, status="success", error="", output_path="")

        self.args.vault = str(self.root / "new-vault")
        self.args.extra = ["--no-subtitle"]
        with patch.object(chubby, "run_ingest_source", side_effect=fake):
            self.assertEqual(chubby.command_retry(self.args, self.config), 0)

    def test_secret_not_written_to_state_and_retry_requires_resupply(self):
        self.args.extra = ["--api-key", "TOP-SECRET-123"]
        self.args.skill = "youtube"
        proc = types.SimpleNamespace(
            returncode=1, stdout="", stderr="failed TOP-SECRET-123"
        )
        with patch.object(chubby.subprocess, "run", return_value=proc):
            record = chubby.run_ingest_source(
                self.target["source"], self.args, self.config
            )
        chubby.append_record(self.config, record)
        chubby.write_report(self.config, [record], "test")
        self.assertNotIn("TOP-SECRET-123", json.dumps(record))
        self.assertNotIn("TOP-SECRET-123", Path(self.config["state_file"]).read_text())
        self.assertIn("--api-key", record["retry_requires"])
        self.args.extra = []
        with patch.object(chubby, "run_ingest_source") as run:
            self.assertEqual(chubby.command_retry(self.args, self.config), 1)
            run.assert_not_called()

    def test_resupplied_secret_replaces_redaction(self):
        target = dict(self.target, retry_requires=["--api-key"])
        target["execution"] = dict(
            target["execution"], extra=["--api-key", "[REDACTED]"]
        )
        chubby.append_record(self.config, target)
        self.args.extra = ["--api-key=NEW-SECRET"]

        def fake(source, args, config, **kwargs):
            self.assertEqual(args.extra, ["--api-key=NEW-SECRET"])
            return dict(self.target, status="success", error="", output_path="")

        with patch.object(chubby, "run_ingest_source", side_effect=fake):
            self.assertEqual(chubby.command_retry(self.args, self.config), 0)


class SecretUrlTest(unittest.TestCase):
    def test_source_url_credentials_redacted_from_error_and_retry_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = dict(
                chubby.DEFAULT_CONFIG, state_file=str(Path(tmp) / "state.jsonl")
            )
            args = types.SimpleNamespace(
                output=None,
                vault=None,
                skill="youtube",
                enrich=False,
                dry_run=False,
                refresh=False,
                timeout=None,
                extra=[],
            )
            source = "https://example.com/video?token=SIGNED-SECRET"
            proc = types.SimpleNamespace(
                returncode=1, stdout="", stderr="failed " + source
            )
            with patch.object(chubby.subprocess, "run", return_value=proc):
                record = chubby.run_ingest_source(source, args, config)
            self.assertNotIn("SIGNED-SECRET", json.dumps(record))
            self.assertIn("--source", record["retry_requires"])


class RedactionBoundaryTest(unittest.TestCase):
    def run_failure(self, source, extra, stderr):
        with tempfile.TemporaryDirectory() as tmp:
            config = dict(
                chubby.DEFAULT_CONFIG, state_file=str(Path(tmp) / "state.jsonl")
            )
            args = types.SimpleNamespace(
                output=None,
                vault=None,
                skill="youtube",
                enrich=False,
                dry_run=False,
                refresh=False,
                timeout=None,
                extra=extra,
            )
            proc = types.SimpleNamespace(returncode=1, stdout="", stderr=stderr)
            with patch.object(chubby.subprocess, "run", return_value=proc):
                return chubby.run_ingest_source(source, args, config)

    def test_encoded_url_secret_is_not_written_to_log(self):
        source = "https://example.com/video?token=TOP%2FSECRET%2B123"
        record = self.run_failure(
            source, [], "failed " + source + " decoded TOP/SECRET+123"
        )
        self.assertNotIn("TOP%2FSECRET%2B123", json.dumps(record))
        self.assertNotIn("TOP/SECRET+123", json.dumps(record))

    def test_short_secret_does_not_corrupt_status_or_fingerprint(self):
        record = self.run_failure(
            "https://youtu.be/aircAruvnKk", ["--api-key=a"], "secret a"
        )
        self.assertEqual(record["status"], "failed")
        self.assertEqual(len(record["execution_hash"]), 64)
        self.assertEqual(record["execution"]["extra"], ["--api-key=[REDACTED]"])


class LegacyRetryTest(unittest.TestCase):
    def test_previous_version_command_preserves_nonsecret_platform_options(self):
        target = {
            "output_dir": "old-output",
            "vault_dir": "old-vault",
            "enrich": False,
            "skill": "youtube",
            "command": [
                "python",
                "chubby_ingest.py",
                "https://youtu.be/aircAruvnKk",
                "--output",
                "old-output",
                "--vault",
                "old-vault",
                "--skill",
                "youtube",
                "--no-translate",
            ],
        }
        args = types.SimpleNamespace(
            output=None,
            vault=None,
            enrich=None,
            skill=None,
            timeout=None,
            extra=[],
            source=None,
        )
        restored, _ = chubby.retry_arguments(target, args, chubby.DEFAULT_CONFIG)
        self.assertEqual(restored.extra, ["--no-translate"])
        self.assertEqual(restored.output, "old-output")

    def test_previous_version_plaintext_credential_requires_resupply(self):
        target = {
            "command": [
                "python",
                "chubby_ingest.py",
                "https://youtu.be/aircAruvnKk",
                "--api-key",
                "old-secret",
            ]
        }
        args = types.SimpleNamespace(
            output=None,
            vault=None,
            enrich=None,
            skill=None,
            timeout=None,
            extra=[],
            source=None,
        )
        with self.assertRaisesRegex(ValueError, "--api-key"):
            chubby.retry_arguments(target, args, chubby.DEFAULT_CONFIG)


if __name__ == "__main__":
    unittest.main()
