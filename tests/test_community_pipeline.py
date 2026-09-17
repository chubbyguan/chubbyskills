import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tools import chubby, check_env, podcast_options


ROOT = Path(__file__).resolve().parents[1]


class ProviderPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = dict(
            chubby.DEFAULT_CONFIG,
            output_dir=str(self.root / "output"),
            state_file=str(self.root / "runs.jsonl"),
        )
        self.args = types.SimpleNamespace(
            output=None,
            vault=None,
            skill="podcast",
            enrich=False,
            timeout=None,
            dry_run=False,
            refresh=False,
            extra=[],
        )

    def capture(self):
        with patch.object(
            chubby.subprocess,
            "run",
            return_value=types.SimpleNamespace(
                returncode=1, stdout="", stderr="offline failure"
            ),
        ):
            return chubby.run_ingest_source(
                "https://example.com/audio.mp3", self.args, self.config
            )

    def test_effective_environment_provider_is_frozen_in_command_and_retry(self):
        with patch.dict(
            os.environ,
            {"PODCAST_TRANSCRIBE_PROVIDER": "atlas", "ATLAS_API_KEY": "private-key"},
        ):
            first = self.capture()
        extra = first["execution"]["extra"]
        self.assertEqual(extra[extra.index("--provider") + 1], "atlas")
        self.assertEqual(extra[extra.index("--model") + 1], "bytedance/seed-asr-2.0")
        self.assertIn("--base-url", extra)
        self.assertNotIn("private-key", json.dumps(first))
        self.args.skill = None
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "muapi"}):
            restored, config = chubby.retry_arguments(first, self.args, self.config)
            self.assertEqual(
                restored.extra[restored.extra.index("--provider") + 1], "atlas"
            )
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "muapi"}):
            self.args.skill = "podcast"
            second = self.capture()
        self.assertNotEqual(first["execution_hash"], second["execution_hash"])

    def test_explicit_local_wins_and_invalid_provider_does_not_spawn(self):
        self.args.extra = ["--provider=local"]
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "muapi"}):
            result = self.capture()
        extra = result["execution"]["extra"]
        self.assertEqual(extra[extra.index("--provider") + 1], "local")
        self.args.extra = ["--provider=invalid"]
        with patch.object(chubby.subprocess, "run") as run:
            result = chubby.run_ingest_source(
                "https://example.com/audio.mp3", self.args, self.config
            )
        self.assertEqual(result["status"], "failed")
        run.assert_not_called()

    def test_resubmit_is_one_shot_and_not_inherited_by_retry(self):
        self.args.extra = ["--provider", "atlas", "--resubmit"]
        record = self.capture()
        self.assertIn("--resubmit", record["command"])
        self.args.extra = []
        restored, _ = chubby.retry_arguments(record, self.args, self.config)
        self.assertNotIn("--resubmit", restored.extra)

    def test_automatic_language_remains_explicit_empty_argument(self):
        self.args.extra = ["--language", ""]
        record = self.capture()
        extra = record["execution"]["extra"]
        self.assertEqual(extra[extra.index("--language") + 1], "")

    def test_retry_switches_provider_without_inheriting_old_endpoint_or_model(self):
        self.args.extra = ["--provider", "muapi"]
        record = self.capture()
        self.args.extra = ["--provider=atlas"]
        restored, _ = chubby.retry_arguments(record, self.args, self.config)
        _, settings = podcast_options.resolve_extra(restored.extra)
        self.assertEqual(settings["model"], "bytedance/seed-asr-2.0")
        self.assertIn("api.atlascloud.ai", settings["base_url"])
        self.args.extra = ["--provider", "local"]
        restored, _ = chubby.retry_arguments(record, self.args, self.config)
        _, settings = podcast_options.resolve_extra(restored.extra)
        self.assertEqual(settings["model"], "small")
        self.assertEqual(settings["base_url"], "")

    def test_interrupted_parent_keeps_cloud_attempt_and_final_event_replaces_it(self):
        self.args.extra = ["--provider", "atlas"]
        with patch.object(chubby.subprocess, "run", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                chubby.run_ingest_source("https://example.com/audio.mp3", self.args, self.config)
        records = chubby.load_records(self.config)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "running")
        self.assertEqual(chubby.failed_retry_targets(records), records)
        final = dict(records[0], status="success", error="")
        chubby.append_record(self.config, final)
        self.assertEqual(chubby.load_records(self.config), [final])

    def test_older_attempt_finishing_late_does_not_hide_new_cloud_attempt(self):
        common = {"source_hash": "audio", "execution_hash": "settings", "source": "episode.mp3"}
        older = dict(common, run_id="older", status="running")
        newer = dict(common, run_id="newer", status="running")
        final = dict(older, status="success", output_paths=["old.md"])
        for event in (older, newer, final):
            chubby.append_record(self.config, event)
        records = chubby.load_records(self.config)
        self.assertEqual(records, [final, newer])
        self.assertEqual(chubby.failed_retry_targets(records, all_failed=True), [newer])
        with patch.object(chubby, "resolve_path", side_effect=AssertionError("must not inspect old artifact")):
            with patch.object(chubby, "load_records", return_value=records):
                self.assertIsNone(chubby.find_reusable_record(self.config, "audio", "settings"))


class ProviderDoctorTest(unittest.TestCase):
    def test_cloud_does_not_require_local_models_and_never_displays_key(self):
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"MUAPI_API_KEY": "private-key"}),
            patch.object(
                check_env.platform_health,
                "check_dependency",
                return_value=(False, "ffmpeg"),
            ),
            contextlib.redirect_stdout(output),
        ):
            code = check_env.main(
                ["--platform", "podcast", "--provider", "muapi", "--json"]
            )
        self.assertEqual(code, 0)
        self.assertNotIn("private-key", output.getvalue())
        self.assertEqual(
            json.loads(output.getvalue())["platforms"][0]["provider"], "muapi"
        )

    def test_missing_cloud_credentials_fails_without_network(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                check_env.main(["--platform", "podcast", "--provider", "atlas"]), 1
            )


class DocumentPipelineTest(unittest.TestCase):
    def test_real_cli_import_reuses_then_refreshes_changed_attachment_and_exports_brief(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source"
            source.mkdir()
            image = source / "image.png"
            image.write_bytes(b"image-one")
            note = source / "材料.md"
            original = '---\ntitle: "素材例子"\nsource: https://example.com/original\n---\n\n利润库存 evidenceword\n\n![配图](image.png)\n'
            note.write_text(original, encoding="utf-8")
            vault = base / "vault"
            settings = dict(
                chubby.DEFAULT_CONFIG,
                output_dir=str(base / "out"),
                vault_dir=str(vault / "00_Inbox"),
                vault_root=str(vault),
                index_db=str(vault / ".chubby/index.sqlite"),
                state_file=str(base / "state.jsonl"),
                report_dir=str(base / "reports"),
            )
            config = base / "chubby.yaml"
            config.write_text(
                "".join(
                    f"{key}: {json.dumps(value)}\n" for key, value in settings.items()
                )
            )

            def invoke(*args):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools/chubby.py"),
                        "--config",
                        str(config),
                        *args,
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            invoke("import", str(note))
            invoke("import", str(note))
            records = [
                json.loads(line)
                for line in (base / "state.jsonl").read_text().splitlines()
            ]
            self.assertTrue(records[-1]["reused"])
            image.write_bytes(b"image-two")
            invoke("import", str(note))
            records = [
                json.loads(line)
                for line in (base / "state.jsonl").read_text().splitlines()
            ]
            self.assertFalse(records[-1]["reused"])
            self.assertNotEqual(records[-1]["output_path"], records[0]["output_path"])
            self.assertEqual(note.read_text(), original)
            self.assertIn("evidenceword", invoke("search", "evidenceword"))
            brief = base / "brief.md"
            invoke("brief", "--topic", "evidenceword", "--output", str(brief))
            self.assertIn("https://example.com/original", brief.read_text())
            self.assertEqual(len(list((vault / "00_Inbox").glob("*.md"))), 2)


if __name__ == "__main__":
    unittest.main()
