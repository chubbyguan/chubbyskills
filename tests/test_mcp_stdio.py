import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "knowledge-base-management" / "scripts" / "mcp_server.py"
SMOKE = ROOT / "tools" / "mcp_smoke.py"


class McpCliTest(unittest.TestCase):
    def test_help_works_without_sdk_or_vault(self):
        env = {key: value for key, value in os.environ.items() if key != "VAULT_DIR"}
        for path in (SERVER, SMOKE):
            with self.subTest(script=path.name):
                result = subprocess.run(
                    [sys.executable, "-S", str(path), "--help"],
                    env=env, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout.lower())

    def test_server_reports_missing_sdk_without_traceback(self):
        with tempfile.TemporaryDirectory() as vault:
            env = dict(os.environ, VAULT_DIR=vault)
            result = subprocess.run(
                [sys.executable, "-S", str(SERVER)],
                env=env, capture_output=True, text=True, timeout=10,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirements-mcp.txt", result.stderr)
        self.assertIn("mcp==1.30.0", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")


@unittest.skipUnless(importlib.util.find_spec("mcp"), "Install knowledge-base-management/requirements-mcp.txt")
class McpStdioTest(unittest.TestCase):
    def test_real_entrypoint_handshake_search_and_read(self):
        result = subprocess.run(
            [sys.executable, str(SMOKE), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["server"], "chubby-kb")
        self.assertEqual(len(report["tools"]), 6)
        self.assertEqual(report["search"], "passed")
        self.assertEqual(report["read"], "passed")


if __name__ == "__main__":
    unittest.main()
