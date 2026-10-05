"""Behaviour that separates a repository checkout from an installed package.

An editable install and a `pip install .` share the same code but not the same
filesystem layout: without this coverage, user state (config, runs, output)
silently lands in site-packages, which a read-only install cannot even write.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import chubby, chubby_ingest


class ConfigBaseTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # resolve(): macOS hands out /var/... while getcwd() reports /private/var/...
        self.workdir = Path(self.temporary.name).resolve()
        self.addCleanup(setattr, chubby, "CONFIG_BASE", chubby.CONFIG_BASE)

    def test_relative_paths_resolve_next_to_the_config_not_the_package(self):
        config_path = self.workdir / "chubby.yaml"
        config_path.write_text("output_dir: output\nstate_file: .chubby/runs.jsonl\n", encoding="utf-8")

        config = chubby.load_config(str(config_path))

        self.assertEqual(chubby.CONFIG_BASE, self.workdir)
        self.assertEqual(chubby.resolve_path(config["output_dir"]), self.workdir / "output")
        self.assertEqual(chubby.resolve_path("runs"), self.workdir / "runs")
        self.assertNotEqual(chubby.resolve_path("output").parent, chubby.ROOT)

    def test_absolute_paths_are_left_alone(self):
        elsewhere = self.workdir / "elsewhere"
        chubby.CONFIG_BASE = self.workdir
        self.assertEqual(chubby.resolve_path(str(elsewhere)), elsewhere)

    def in_workdir(self):
        """Run the next assertions from a directory with no chubby.yaml."""
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.workdir)

    def test_default_config_prefers_an_existing_local_config(self):
        self.in_workdir()
        local = self.workdir / "chubby.yaml"
        local.write_text("output_dir: output\n", encoding="utf-8")
        self.assertEqual(chubby.default_config_path(), local)

    def test_default_config_falls_back_to_the_package_root_when_present(self):
        self.in_workdir()
        with patch.object(chubby, "ROOT", self.workdir / "site-packages"):
            root_config = self.workdir / "site-packages" / "chubby.yaml"
            root_config.parent.mkdir()
            root_config.write_text("output_dir: output\n", encoding="utf-8")
            self.assertEqual(chubby.default_config_path(), root_config)

    def test_default_config_never_invents_a_package_location(self):
        """The regression: with no config anywhere, `init` must use the cwd."""
        self.in_workdir()
        with patch.object(chubby, "ROOT", self.workdir / "site-packages"):
            self.assertEqual(chubby.default_config_path(), self.workdir / "chubby.yaml")


class VersionTest(unittest.TestCase):
    def test_checkout_reads_the_version_file(self):
        version_file = chubby.ROOT / "VERSION"
        if not version_file.exists():
            self.skipTest("VERSION only exists in a checkout")
        self.assertEqual(chubby.read_version(), version_file.read_text(encoding="utf-8").strip())
        self.assertNotEqual(chubby.read_version(), "0.0.0")

    def test_installed_layout_falls_back_to_distribution_metadata(self):
        with patch.object(chubby, "ROOT", Path(os.devnull).parent / "definitely-not-a-checkout"):
            with patch("importlib.metadata.version", return_value="9.9.9"):
                self.assertEqual(chubby.read_version(), "9.9.9")

    def test_missing_everything_still_reports_a_version_string(self):
        with patch.object(chubby, "ROOT", Path("/nonexistent-checkout")):
            with patch("importlib.metadata.version", side_effect=Exception("no dist-info")):
                self.assertEqual(chubby.read_version(), "0.0.0")


class SkillScriptPathTest(unittest.TestCase):
    def test_missing_skill_script_names_the_checkout_requirement(self):
        """A pip install ships no skill directories; say so instead of a traceback."""
        with patch.object(chubby_ingest, "ROOT", "/nonexistent-install"):
            with self.assertRaises(RuntimeError) as caught:
                chubby_ingest.script_path("youtube")
        message = str(caught.exception)
        self.assertIn("youtube", message)
        self.assertIn("git clone", message)
        self.assertIn("checkout", message)

    def test_present_skill_script_resolves(self):
        path = chubby_ingest.script_path("document")
        self.assertTrue(os.path.isfile(path))

    def test_skill_dir_prefers_the_distributed_name_in_a_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / "bilibili-transcribe").mkdir()
            (root / "bilibili_transcribe").mkdir()
            with patch.object(chubby_ingest, "ROOT", str(root)):
                self.assertEqual(
                    Path(chubby_ingest.skill_dir("bilibili-transcribe")).name,
                    "bilibili-transcribe",
                )

    def test_skill_dir_falls_back_to_the_importable_name_once_installed(self):
        """`bilibili-transcribe` is not a legal package name; the wheel maps it."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / "bilibili_transcribe").mkdir()
            with patch.object(chubby_ingest, "ROOT", str(root)):
                self.assertEqual(
                    Path(chubby_ingest.skill_dir("bilibili-transcribe")).name,
                    "bilibili_transcribe",
                )

    def test_installed_layout_resolves_a_real_entrypoint(self):
        """The whole point of #16: a pip install can run platform capture."""
        path = chubby_ingest.script_path("youtube")
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(path.endswith(os.path.join("scripts", "transcribe.py")))


if __name__ == "__main__":
    unittest.main()
