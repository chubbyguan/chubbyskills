import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import chubby


class PipelineReuseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = dict(
            chubby.DEFAULT_CONFIG,
            output_dir=str(self.root / "output"),
            state_file=str(self.root / "runs.jsonl"),
            report_dir=str(self.root / "reports"),
        )
        self.args = types.SimpleNamespace(
            output=None,
            vault=None,
            skill="youtube",
            enrich=False,
            dry_run=False,
            refresh=False,
            timeout=None,
            extra=[],
        )
        self.source = "https://www.youtube.com/watch?v=aircAruvnKk"
        self.calls = 0

    def adapter(self, cmd, **kwargs):
        self.calls += 1
        output = Path(cmd[cmd.index("--output") + 1])
        output.mkdir(parents=True, exist_ok=True)
        path = output / f"note-{self.calls}.md"
        path.write_text(
            "---\ntitle: Note\ntype: note\nplatform: youtube\nsource: "
            + self.source
            + "\ncreated: 2026-09-17\n---\n\n# Note\n\nA transcript.\n"
        )
        return types.SimpleNamespace(returncode=0, stdout=str(path) + "\n", stderr="")

    def run_capture(self, source=None):
        with patch.object(chubby.subprocess, "run", side_effect=self.adapter):
            record = chubby.run_ingest_source(
                source or self.source, self.args, self.config
            )
        chubby.append_record(self.config, record)
        return record

    def test_normalized_source_reuses_valid_output_without_restamping_user_edit(self):
        first = self.run_capture()
        path = Path(first["output_path"])
        path.write_text(path.read_text() + "\nUser addition.\n")
        before = path.read_text()
        second = self.run_capture("https://youtu.be/aircAruvnKk?si=share")
        self.assertEqual(self.calls, 1)
        self.assertEqual(second["reused_from"], first["run_id"])
        self.assertEqual(second["status"], "success")
        self.assertEqual(path.read_text(), before)

    def test_refresh_recollects(self):
        first = self.run_capture()
        self.args.refresh = True
        second = self.run_capture()
        self.assertEqual(self.calls, 2)
        self.assertNotEqual(first["output_path"], second["output_path"])
        self.assertTrue(Path(first["output_path"]).exists())

    def test_failed_refresh_blocks_older_successful_cache_on_retry_and_rerun(self):
        first = self.run_capture()
        self.args.extra = ["--resubmit"]
        with patch.object(chubby.subprocess, "run", return_value=types.SimpleNamespace(
                returncode=1, stdout="", stderr="new task pending; polling timed out")):
            failed = chubby.run_ingest_source(self.source, self.args, self.config)
        chubby.append_record(self.config, failed)
        self.assertEqual(first["execution_hash"], failed["execution_hash"])
        retry_args, retry_config = chubby.retry_arguments(failed, self.args, self.config)
        retry_args.extra = []
        with patch.object(chubby.subprocess, "run", side_effect=self.adapter):
            retried = chubby.run_ingest_source(self.source, retry_args, retry_config)
        self.assertFalse(retried["reused"])
        self.args.extra = []
        rerun = self.run_capture()
        self.assertFalse(rerun["reused"])
        self.assertEqual(self.calls, 3)

    def test_missing_or_invalid_output_does_not_reuse(self):
        first = self.run_capture()
        Path(first["output_path"]).unlink()
        second = self.run_capture()
        self.assertEqual(self.calls, 2)
        Path(second["output_path"]).write_text("# invalid")
        self.run_capture()
        self.assertEqual(self.calls, 3)

    def test_changed_destination_or_processing_args_does_not_reuse(self):
        self.run_capture()
        self.args.extra = ["--no-translate"]
        self.run_capture()
        self.args.output = str(self.root / "elsewhere")
        self.run_capture()
        self.assertEqual(self.calls, 3)

    def test_changed_local_input_does_not_reuse(self):
        local = self.root / "recording.mp3"
        local.write_bytes(b"first")
        self.run_capture(str(local))
        local.write_bytes(b"second")
        self.run_capture(str(local))
        self.assertEqual(self.calls, 2)

    def test_queue_duplicate_reuses_earlier_record(self):
        self.args.sources = [self.source, "https://youtu.be/aircAruvnKk"]
        self.args.queue = None
        self.args.limit = None
        with patch.object(chubby.subprocess, "run", side_effect=self.adapter):
            self.assertEqual(chubby.command_run(self.args, self.config), 0)
        self.assertEqual(self.calls, 1)

    def test_success_and_reuse_sync_index_without_hiding_capture_success(self):
        self.args.vault = str(self.root / "vault")
        Path(self.args.vault).mkdir()
        with patch.object(
            chubby.vault_index, "sync_vault", return_value={"notes": 1}, create=True
        ) as sync:
            first = self.run_capture()
            second = self.run_capture()
        self.assertEqual(sync.call_count, 2)
        self.assertEqual(first["index_status"], "success")
        self.assertEqual(second["index_status"], "success")
        self.assertEqual(self.calls, 1)

    def test_index_failure_keeps_success_record_and_makes_cli_fail(self):
        self.args.vault = str(self.root / "vault")
        Path(self.args.vault).mkdir()
        self.args.source = self.source
        with (
            patch.object(
                chubby.vault_index,
                "sync_vault",
                side_effect=RuntimeError("index locked"),
                create=True,
            ),
            patch.object(chubby.subprocess, "run", side_effect=self.adapter),
        ):
            self.assertEqual(chubby.command_ingest(self.args, self.config), 1)
        record = chubby.load_records(self.config)[-1]
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["index_status"], "failed")
        self.assertIn("index locked", record["index_error"])


class UnifiedCliTest(unittest.TestCase):
    def test_init_vault_persists_root_inbox_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "chubby.yaml"
            vault = root / "My Vault"
            self.assertEqual(
                chubby.main(
                    ["--config", str(config_path), "init", "--vault", str(vault)]
                ),
                0,
            )
            config = chubby.load_config(str(config_path))
            self.assertEqual(Path(config["vault_root"]), vault.resolve())
            self.assertEqual(Path(config["vault_dir"]), vault.resolve() / "00_Inbox")
            self.assertEqual(
                Path(config["index_db"]), vault.resolve() / ".chubby/index.sqlite"
            )
            self.assertTrue((vault / "00_Inbox").is_dir())

    def test_explicit_destination_outside_configured_vault_owns_its_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configured = root / "original"
            different = root / "other"
            config = dict(
                chubby.DEFAULT_CONFIG,
                vault_root=str(configured),
                vault_dir=str(configured / "00_Inbox"),
                index_db=str(configured / ".chubby/index.sqlite"),
            )
            actual_root, database = chubby.index_context(str(different), config)
            self.assertEqual(Path(actual_root), different.resolve())
            self.assertEqual(
                Path(database), different.resolve() / ".chubby/index.sqlite"
            )

    def test_keyword_and_lite_search_sync_before_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = dict(chubby.DEFAULT_CONFIG, vault_root=tmp)
            for mode in ("keyword", "lite"):
                args = types.SimpleNamespace(
                    vault=None,
                    db=None,
                    query="creator",
                    limit=5,
                    platform=None,
                    tag=None,
                    mode=mode,
                    json=True,
                )
                query = "search" if mode == "keyword" else "semantic_search"
                with (
                    patch.object(chubby.vault_index, "sync_vault") as sync,
                    patch.object(chubby.vault_index, query, return_value=[]) as search,
                ):
                    self.assertEqual(chubby.command_search(args, config), 0)
                    sync.assert_called_once()
                    search.assert_called_once()

    def test_doctor_forwards_selected_platform(self):
        with patch.object(
            chubby.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)
        ) as run:
            self.assertEqual(chubby.main(["doctor", "--platform", "youtube"]), 0)
        self.assertEqual(run.call_args.args[0][-2:], ["--platform", "youtube"])


class ExistingWorkspaceInitTest(unittest.TestCase):
    def test_explicit_vault_updates_existing_config_without_resetting_other_settings(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "chubby.yaml"
            vault = root / "New Vault"
            config_path.write_text(
                "output_dir: preserved-output\ntimeout_seconds: 47\n"
                "vault_root: old\nvault_dir: old/00_Inbox\nindex_db: old/index.sqlite\n"
            )
            with patch.object(chubby, "ROOT", root):
                self.assertEqual(
                    chubby.main(
                        ["--config", str(config_path), "init", "--vault", str(vault)]
                    ),
                    0,
                )
            config = chubby.load_config(str(config_path))
            self.assertEqual(config["output_dir"], "preserved-output")
            self.assertEqual(config["timeout_seconds"], "47")
            self.assertEqual(Path(config["vault_root"]), vault.resolve())
            self.assertEqual(Path(config["vault_dir"]), vault.resolve() / "00_Inbox")
            self.assertEqual(
                Path(config["index_db"]), vault.resolve() / ".chubby/index.sqlite"
            )


class FileOptionFingerprintTest(unittest.TestCase):
    def test_inline_file_option_includes_file_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual.txt"
            path.write_text("first")
            execution = {"extra": [f"--fallback-text={path}"]}
            first = chubby.execution_fingerprint(execution)
            path.write_text("second")
            self.assertNotEqual(first, chubby.execution_fingerprint(execution))


class ArtifactContractTest(unittest.TestCase):
    def test_comma_and_brackets_in_asset_directory_do_not_prevent_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "Hello, [World].md"
            output.write_text(
                "---\ntitle: Note\ntype: note\nplatform: x\n"
                "source: https://x.com/example/status/123\ncreated: 2026-09-17\n---\n\n# Note\n"
            )
            output.with_suffix(".assets").mkdir()
            config = dict(
                chubby.DEFAULT_CONFIG,
                output_dir=tmp,
                state_file=str(root / "state.jsonl"),
            )
            args = types.SimpleNamespace(
                output=None,
                vault=None,
                skill="x",
                enrich=False,
                dry_run=False,
                extra=[],
            )
            proc = types.SimpleNamespace(
                returncode=0, stdout=str(output) + "\n", stderr=""
            )
            with patch.object(chubby.subprocess, "run", return_value=proc) as run:
                first = chubby.run_ingest_source(
                    "https://x.com/example/status/123", args, config
                )
                chubby.append_record(config, first)
                second = chubby.run_ingest_source(
                    "https://x.com/example/status/123", args, config
                )
            self.assertTrue(second["reused"])
            self.assertEqual(run.call_count, 1)

    def test_explicit_working_output_does_not_stamp_unrelated_historical_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            working = root / "working"
            vault = root / "vault"
            working.mkdir()
            vault.mkdir()
            original = working / "Note--2.md"
            original.write_text("User historical edit")
            new_working = working / "Note.md"
            new_vault = vault / "Note--2.md"
            content = (
                "---\ntitle: Note\ntype: note\nplatform: x\nsource: https://x.com/u/status/123\n"
                "created: 2026-09-17\n---\n\n# Note\n"
            )
            new_working.write_text(content)
            new_vault.write_text(content)
            config = dict(
                chubby.DEFAULT_CONFIG,
                output_dir=str(working),
                vault_dir=str(vault),
                state_file=str(root / "state.jsonl"),
            )
            args = types.SimpleNamespace(
                output=None,
                vault=None,
                skill="x",
                enrich=False,
                dry_run=False,
                extra=[],
            )
            proc = types.SimpleNamespace(
                returncode=0,
                stdout=str(new_vault) + "\n",
                stderr=f"Output: {new_working}\n",
            )
            with patch.object(chubby.subprocess, "run", return_value=proc):
                record = chubby.run_ingest_source(
                    "https://x.com/u/status/123", args, config
                )
            self.assertEqual(record["status"], "success", record)
            self.assertEqual(len(record["output_paths"]), 2)
            self.assertEqual(original.read_text(), "User historical edit")


class MissingAttachmentTest(unittest.TestCase):
    def test_missing_image_invalidates_successful_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "Note.md"
            assets = output.with_suffix(".assets")
            assets.mkdir()
            image = assets / "image.png"
            image.write_bytes(b"image")
            output.write_text(
                "---\ntitle: Note\ntype: note\nplatform: x\nsource: https://x.com/u/status/123\n"
                "created: 2026-09-17\n---\n\n# Note\n![image](Note.assets/image.png)\n"
            )
            config = dict(
                chubby.DEFAULT_CONFIG,
                output_dir=tmp,
                state_file=str(root / "state.jsonl"),
            )
            args = types.SimpleNamespace(
                output=None,
                vault=None,
                skill="x",
                enrich=False,
                dry_run=False,
                extra=[],
            )
            proc = types.SimpleNamespace(
                returncode=0, stdout=str(output) + "\n", stderr=""
            )
            with patch.object(chubby.subprocess, "run", return_value=proc) as run:
                first = chubby.run_ingest_source(
                    "https://x.com/u/status/123", args, config
                )
                chubby.append_record(config, first)
                second = chubby.run_ingest_source(
                    "https://x.com/u/status/123", args, config
                )
                chubby.append_record(config, second)
                self.assertTrue(second["reused"])
                image.unlink()
                third = chubby.run_ingest_source(
                    "https://x.com/u/status/123", args, config
                )
            self.assertFalse(third["reused"])
            self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
