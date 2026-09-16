import importlib.util
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import chubby, validate_outputs


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "youtube_transcribe_regressions", ROOT / "youtube-transcribe/scripts/transcribe.py"
)
youtube = importlib.util.module_from_spec(spec)
spec.loader.exec_module(youtube)
SOURCE = "https://www.youtube.com/watch?v=aircAruvnKk"


class YouTubeMetadataTest(unittest.TestCase):
    def test_metadata_can_be_read_without_downloadable_formats(self):
        result = subprocess.CompletedProcess([], 0, "Neural networks explained\n19:13\n", "")
        with patch.object(youtube.ytdlp, "run_ydl", return_value=result) as run:
            self.assertEqual(youtube.get_video_info(SOURCE), {
                "title": "Neural networks explained", "duration": "19:13"
            })
        command = run.call_args.args[1]
        self.assertIn("--skip-download", command)
        self.assertIn("--ignore-no-formats-error", command)

    def test_empty_metadata_has_nonempty_default_title(self):
        for stdout in ("", "\n", "  \n19:13\n", "NA\nNA\n"):
            with self.subTest(stdout=stdout):
                result = subprocess.CompletedProcess([], 0, stdout, "")
                with patch.object(youtube.ytdlp, "run_ydl", return_value=result):
                    self.assertEqual(youtube.get_video_info(SOURCE)["title"], youtube.CFG.default_title)

    def test_metadata_exception_falls_back(self):
        with patch.object(youtube.ytdlp, "run_ydl", side_effect=RuntimeError("network unavailable")):
            self.assertEqual(youtube.get_video_info(SOURCE), {
                "title": youtube.CFG.default_title, "duration": ""
            })


class IngestOutputAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "note.md"
        self.config = dict(chubby.DEFAULT_CONFIG, output_dir=self.tmp.name)
        self.args = types.SimpleNamespace(
            output=None, vault=None, enrich=False, skill="youtube", dry_run=False, extra=[]
        )

    def write_note(self, path=None, title="Neural networks explained"):
        path = path or self.output
        path.write_text(
            f'---\ntitle: "{title}"\ntype: note\nplatform: youtube\n'
            f"source: {SOURCE}\ncreated: 2026-09-16\n---\n\n# Video\n\nTranscript.\n",
            encoding="utf-8",
        )

    def run_ingest(self, stdout=None, stderr=""):
        stdout = str(self.output) + "\n" if stdout is None else stdout
        result = subprocess.CompletedProcess([], 0, stdout, stderr)
        with patch.object(chubby.subprocess, "run", return_value=result):
            return chubby.run_ingest_source(SOURCE, self.args, self.config)

    def read_status(self, path=None):
        frontmatter, _ = chubby.split_frontmatter((path or self.output).read_text(encoding="utf-8"))
        return validate_outputs.parse_frontmatter(frontmatter)["status"]

    def test_valid_output_is_stamped_and_accepted(self):
        self.write_note()
        record = self.run_ingest()
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["error"], "")
        self.assertEqual(self.read_status(), "success")
        self.assertEqual(validate_outputs.validate_file(self.output, require_schema_v1=True), [])

    def test_empty_title_is_failure_in_record_and_markdown(self):
        self.write_note(title="")
        record = self.run_ingest()
        self.assertEqual(record["status"], "failed")
        self.assertIn("missing required field: title", record["error"])
        self.assertEqual(self.read_status(), "failed")

    def test_real_progress_prefixes_preserve_paths_with_spaces(self):
        self.output = Path(self.tmp.name) / "A video title with spaces.md"
        self.write_note()
        for prefix in ("  Output:", "✅ Saved:", "✅ Saved fallback:", "📥 已入库："):
            with self.subTest(prefix=prefix):
                record = self.run_ingest(stderr=f"{prefix} {self.output}\n")
                self.assertEqual(record["status"], "success", record["error"])
                self.assertEqual(record["output_paths"], [str(self.output)])
                self.assertEqual(self.read_status(), "success")

    def test_unrelated_stderr_markdown_reference_is_not_an_output(self):
        self.write_note()
        record = self.run_ingest(stderr="For more information see docs/help.md\n")
        self.assertEqual(record["status"], "success", record["error"])
        self.assertEqual(record["output_paths"], [str(self.output)])

    def test_long_markdown_title_log_does_not_probe_invalid_filename(self):
        self.write_note()
        record = self.run_ingest(stderr="Title: " + "中" * 300 + ".md\n")
        self.assertEqual(record["status"], "success", record["error"])
        self.assertEqual(record["output_paths"], [str(self.output)])

    def test_declared_invalid_filename_is_recorded_as_failure(self):
        invalid_path = self.output.parent / ("中" * 300 + ".md")
        record = self.run_ingest(stdout=f"{invalid_path}\n")
        self.assertEqual(record["status"], "failed")
        self.assertIn("cannot validate output", record["error"])

    def test_declared_missing_stderr_output_still_fails(self):
        self.write_note()
        record = self.run_ingest(stderr=f"📥 已入库： {self.output.parent / 'missing copy.md'}\n")
        self.assertEqual(record["status"], "failed")
        self.assertIn("missing output file", record["error"])
        self.assertEqual(self.read_status(), "failed")

    def test_missing_file_is_failure_even_if_subprocess_exits_zero(self):
        record = self.run_ingest()
        self.assertEqual(record["status"], "failed")
        self.assertIn("missing output file", record["error"])

    def test_no_reported_output_is_failure(self):
        record = self.run_ingest(stdout="")
        self.assertEqual(record["status"], "failed")
        self.assertIn("no Markdown output", record["error"])

    def test_missing_frontmatter_is_failure(self):
        self.output.write_text("# Video\n\nTranscript.\n", encoding="utf-8")
        record = self.run_ingest()
        self.assertEqual(record["status"], "failed")
        self.assertIn("missing YAML frontmatter", record["error"])

    def test_one_invalid_copy_marks_all_copies_failed(self):
        self.write_note()
        vault_copy = Path(self.tmp.name) / "vault.md"
        self.write_note(vault_copy, title="")
        record = self.run_ingest(stdout=f"{self.output}\n{vault_copy}\n")
        self.assertEqual(record["status"], "failed")
        self.assertEqual(self.read_status(), "failed")
        self.assertEqual(self.read_status(vault_copy), "failed")


class ErrorSummaryTest(unittest.TestCase):
    def test_retains_exception_at_end_of_long_stderr(self):
        reason = "ModuleNotFoundError: No module named 'funasr'"
        stderr = ("Downloading media...\n" * 100) + reason
        summary = chubby.compact_error("Progress output " * 100, stderr)
        self.assertLessEqual(len(summary), 800)
        self.assertTrue(summary.endswith(reason), summary)

    def test_short_error_is_kept(self):
        self.assertEqual(chubby.compact_error("", "  missing funasr\n"), "missing funasr")


if __name__ == "__main__":
    unittest.main()
