"""Exercise the real CLI and local manual-import path without platform requests."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import evidence_brief


ROOT = Path(__file__).resolve().parents[1]


class CreatorFlowTest(unittest.TestCase):
    def test_capture_reuse_search_refresh_and_citations_through_real_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "中文 素材库"
            config = base / "chubby.yaml"

            def cli(*args):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools/chubby.py"), "--config", str(config), *args],
                    cwd=ROOT, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            cli("init", "--vault", str(vault))
            # Keep run state and working files in this test's isolated directory.
            text = config.read_text()
            replacements = {
                "output_dir": str(base / "working"), "state_file": str(base / "runs.jsonl"),
                "report_dir": str(base / "reports"), "queue_file": str(base / "links.txt"),
            }
            config.write_text("\n".join(
                f"{line.split(':', 1)[0]}: {json.dumps(replacements[line.split(':', 1)[0]], ensure_ascii=False)}"
                if line.split(":", 1)[0] in replacements else line for line in text.splitlines()
            ) + "\n")
            body = base / "manual.txt"
            body.write_text("电商选品要关注利润和退货率，这是离线测试素材。\n")
            sources = [f"https://x.com/example/status/{number}" for number in (111, 222, 333)]
            args = ("run", *sources, "--no-enrich", "--fallback-only", "--fallback-text", str(body))
            cli(*args)
            originals = {str(path): path.read_bytes() for path in vault.rglob("*.md")}
            self.assertEqual(len(originals), 3)
            cli(*args)
            records = [json.loads(line) for line in (base / "runs.jsonl").read_text().splitlines()]
            self.assertTrue(all(row["reused"] for row in records[-3:]))
            self.assertEqual(originals, {str(path): path.read_bytes() for path in vault.rglob("*.md")})
            found = json.loads(cli("search", "选品", "--json").stdout)
            self.assertEqual(len(found), 3)
            self.assertTrue(all(row["source"] in sources for row in found))
            brief = base / "research.md"
            cli("brief", "--topic", "选品", "--output", str(brief))
            bundle = json.loads(brief.with_suffix(".json").read_text())
            self.assertEqual(len(bundle["documents"]), 3)
            self.assertEqual(evidence_brief.validate_brief(bundle, vault), [])
            body.write_text("电商选品新增独立关键词 inventoryprobe，用来验证新素材立刻可检索。\n")
            cli("ingest", sources[0], "--refresh", "--no-enrich", "--fallback-only", "--fallback-text", str(body))
            for path, original in originals.items():
                self.assertEqual(Path(path).read_bytes(), original)
            self.assertTrue(json.loads(cli("search", "inventoryprobe", "--json").stdout))


if __name__ == "__main__":
    unittest.main()
