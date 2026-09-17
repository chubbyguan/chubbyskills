import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools import install_skill


ROOT = Path(__file__).resolve().parents[1]


class PortableSkillInstallTest(unittest.TestCase):
    def test_every_skill_imports_after_its_installed_directory_is_moved(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            destination = base / "installed"
            installed = install_skill.install_skills(sorted(install_skill.SUPPORTED_SKILLS), destination)
            self.assertEqual(len(installed), 14)
            self.assertEqual(set(install_skill.SUPPORTED_SKILLS), {path.parent.name for path in ROOT.glob("*/SKILL.md")})
            # Do not leave siblings or the original repository on Python's path.
            for skill in installed:
                with self.subTest(skill=skill.name):
                    moved = base / "portable" / skill.name
                    moved.parent.mkdir(exist_ok=True)
                    shutil.move(str(skill), moved)
                    for script in sorted((moved / "scripts").glob("*.py")):
                        code = (
                            "import runpy, sys; "
                            "m = runpy.run_path(sys.argv[1], run_name='installed_skill_probe'); "
                            "assert 'VAULT_INDEX_ERROR' not in m or m['vault_index'] is not None, "
                            "m.get('VAULT_INDEX_ERROR')"
                        )
                        result = subprocess.run(
                            [sys.executable, "-I", "-c", code, str(script)],
                            cwd=base, capture_output=True, text=True, timeout=15,
                        )
                        self.assertEqual(result.returncode, 0, f"{script}: {result.stderr}")
                    shutil.rmtree(moved)

    def test_installed_manual_capture_and_kb_search_work_without_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            destination = base / "skills"
            install_skill.install_skills(["x-ingest", "xiaohongshu-ingest", "knowledge-base-management"], destination)
            body = base / "body.txt"
            body.write_text("Portable Agent capture sample for local search.", encoding="utf-8")
            vault = base / "vault"
            for name, script, source in (
                ("x-ingest", "fetch_tweet.py", "https://x.com/example/status/1"),
                ("xiaohongshu-ingest", "fetch_note.py", "https://www.xiaohongshu.com/explore/example"),
            ):
                result = subprocess.run(
                    [sys.executable, "-I", str(destination / name / "scripts" / script), source,
                     "--fallback-only", "--fallback-text", str(body), "--output", str(vault)],
                    cwd=base, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreaterEqual(len(list(vault.glob("*.md"))), 1)
            code = (
                "import runpy, sys; m = runpy.run_path(sys.argv[1]); "
                "result = m['search'](sys.argv[2], 'Portable'); "
                "assert '索引不可用' not in result and '.md' in result, result"
            )
            result = subprocess.run(
                [sys.executable, "-I", "-c", code,
                 str(destination / "knowledge-base-management" / "scripts" / "mcp_server.py"), str(vault)],
                cwd=base, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            # Documented local indexing/curation CLIs are also bundled.
            for tool in ("vault_index.py", "vault_curator.py", "evidence_brief.py"):
                result = subprocess.run(
                    [sys.executable, "-I", str(destination / "knowledge-base-management" / "tools" / tool), "--help"],
                    cwd=base, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(
                [sys.executable, "-I", str(destination / "knowledge-base-management" / "tools" / "evidence_brief.py"),
                 "--vault", str(vault), "--topic", "Portable", "--output", str(base / "brief.md")],
                cwd=base, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Portable Agent capture sample", (base / "brief.md").read_text())

    def test_existing_skill_aborts_entire_install_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            existing = destination / "x-ingest"
            existing.mkdir()
            sentinel = existing / "SKILL.md"
            sentinel.write_text("user edited skill", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                install_skill.install_skills(["bilibili-transcribe", "x-ingest"], destination)
            self.assertEqual(sentinel.read_text(), "user edited skill")
            self.assertFalse((destination / "bilibili-transcribe").exists())

    def test_path_traversal_and_symlink_targets_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "skills"
            destination.mkdir()
            for name in ("../x-ingest", "/tmp/x-ingest", "unknown-skill"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    install_skill.install_skills([name], destination)
            outside = Path(temporary) / "outside"
            outside.mkdir()
            (destination / "x-ingest").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(FileExistsError):
                install_skill.install_skills(["x-ingest"], destination)
            root_link = Path(temporary) / "root-link"
            root_link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                install_skill.install_skills(["x-ingest"], root_link)
            self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlinks_are_rejected_and_local_env_is_not_copied(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repo"
            skill = repo / "x-ingest"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("skill")
            (skill / ".env.local").write_text("private=value")
            (repo / "LICENSE").write_text("license")
            (repo / "VERSION").write_text("test")
            (skill / "linked.txt").symlink_to(repo / "LICENSE")
            with self.assertRaises(ValueError):
                install_skill.install_skills(["x-ingest"], base / "bad", repo_root=repo)
            self.assertFalse((base / "bad").exists())
            (skill / "linked.txt").unlink()
            install_skill.install_skills(["x-ingest"], base / "good", repo_root=repo)
            self.assertFalse((base / "good" / "x-ingest" / ".env.local").exists())
            with self.assertRaises(ValueError):
                install_skill.install_skills(["x-ingest"], skill / "recursive", repo_root=repo)


class SetupDependencyRoutingTest(unittest.TestCase):
    def run_setup(self, arguments, missing=()):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            binary = base / "bin"
            binary.mkdir()
            log = base / "calls.log"
            for name in ("python3", "ffmpeg", "curl", "yt-dlp"):
                if name in missing:
                    continue
                stub = binary / name
                stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CHUBBY_SETUP_TEST_LOG"\n')
                stub.chmod(0o755)
            (binary / "dirname").symlink_to(shutil.which("dirname"))
            env = dict(os.environ, PATH=str(binary), CHUBBY_SETUP_TEST_LOG=str(log))
            result = subprocess.run(
                [shutil.which("bash"), str(ROOT / "setup.sh"), *arguments],
                cwd=base, env=env, capture_output=True, text=True, timeout=15,
            )
            return result, log.read_text() if log.exists() else ""

    def test_full_names_route_to_expected_dependencies(self):
        for name in sorted(install_skill.SUPPORTED_SKILLS):
            with self.subTest(name=name):
                result, calls = self.run_setup([name])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if name in {"douyin-transcribe", "bilibili-transcribe", "youtube-transcribe", "tiktok-transcribe", "weibo-transcribe", "zhihu-transcribe"}:
                    self.assertIn("pip install funasr", calls)
                elif name == "podcast-transcribe":
                    self.assertIn("pip install faster-whisper", calls)
                elif name == "wechat-article-ingest":
                    self.assertIn("pip install beautifulsoup4", calls)
                else:
                    self.assertNotIn("pip install", calls)

    def test_light_skills_do_not_require_optional_media_commands(self):
        result, calls = self.run_setup(["x-ingest", "xiaohongshu-ingest", "content-enrich"], missing=("ffmpeg", "curl", "yt-dlp"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("pip install", calls)

    def test_unknown_target_and_required_curl_fail_before_install(self):
        for arguments, missing in ((["unknown-skill"], ()), (["douyin-transcribe"], ("curl",))):
            with self.subTest(arguments=arguments):
                result, calls = self.run_setup(arguments, missing)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("pip install", calls)


if __name__ == "__main__":
    unittest.main()
