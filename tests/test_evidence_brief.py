import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import evidence_brief


class EvidenceBriefTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.vault = Path(self.temporary.name) / "中文 素材库"
        self.vault.mkdir()
        self.note = self.vault / "材料 一.md"
        self.note.write_text(
            '---\ntitle: "电商选品"\nplatform: x\n'
            'source: "https://x.com/example/status/1"\n'
            'captured_at: "2026-09-17T10:00:00+08:00"\n---\n\n'
            '# 原始材料\n\n电商选品需要关注利润和退货率。\n不能仅看销售额。\n\n'
            '另一段记录是库存周转。\n', encoding="utf-8",
        )

    def test_bundle_is_deterministic_and_excerpts_recover_exact_original_lines(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        self.assertEqual(bundle, evidence_brief.build_brief(self.vault, "选品"))
        self.assertEqual(len(bundle["documents"]), 1)
        doc = bundle["documents"][0]
        self.assertEqual(doc["source"], "https://x.com/example/status/1")
        self.assertEqual(doc["captured_at"], "2026-09-17T10:00:00+08:00")
        lines = self.note.read_text().splitlines(keepends=True)
        self.assertTrue(doc["excerpts"])
        for excerpt in doc["excerpts"]:
            self.assertGreater(excerpt["start_line"], 6)
            self.assertEqual(excerpt["text"], "".join(lines[excerpt["start_line"] - 1:excerpt["end_line"]]))
        self.assertEqual(evidence_brief.validate_brief(bundle, self.vault), [])

    def test_new_note_is_searchable_and_no_match_is_explicit(self):
        evidence_brief.build_brief(self.vault, "选品")
        (self.vault / "new.md").write_text("# new\nrarekeywordxyz meaningful research\n")
        self.assertEqual(len(evidence_brief.build_brief(self.vault, "rarekeywordxyz")["documents"]), 1)
        empty = evidence_brief.build_brief(self.vault, "zzzzunmatched1234")
        self.assertEqual(empty["documents"], [])
        self.assertIn("证据不足", evidence_brief.render_markdown(empty))

    def test_changed_and_forged_evidence_is_rejected(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        forged = copy.deepcopy(bundle)
        forged["documents"][0]["excerpts"][0]["text"] = "invented evidence"
        self.assertTrue(evidence_brief.validate_brief(forged, self.vault))
        forged = copy.deepcopy(bundle)
        forged["documents"][0]["source"] = "https://example.com/forged"
        self.assertTrue(evidence_brief.validate_brief(forged, self.vault))
        self.note.write_text(self.note.read_text() + "后来修改的材料。\n")
        self.assertTrue(evidence_brief.validate_brief(bundle, self.vault))

    def test_traversal_and_symlink_citations_are_rejected(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        forged = copy.deepcopy(bundle)
        forged["documents"][0]["path"] = "../outside.md"
        self.assertTrue(evidence_brief.validate_brief(forged, self.vault))
        outside = Path(self.temporary.name) / "outside.md"
        outside.write_text("secret")
        link = self.vault / "link.md"
        link.symlink_to(outside)
        forged["documents"][0]["path"] = "link.md"
        self.assertTrue(evidence_brief.validate_brief(forged, self.vault))

    def test_exports_match_bundle_and_existing_files_are_preserved(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        output = Path(self.temporary.name) / "research.md"
        paths = evidence_brief.write_brief(bundle, output)
        self.assertEqual(json.loads(Path(paths["json"]).read_text()), bundle)
        self.assertIn("https://x.com/example/status/1", output.read_text())
        self.assertIn("SHA-256", output.read_text())
        with self.assertRaises(FileExistsError):
            evidence_brief.write_brief(bundle, output)
        self.assertEqual(json.loads(Path(paths["json"]).read_text()), bundle)

    def test_invalid_topic_and_limit_fail_before_indexing(self):
        for topic, limit in (("", 5), (" ", 5), ("topic", 0), ("topic", -1)):
            with self.subTest(topic=topic, limit=limit), self.assertRaises(ValueError):
                evidence_brief.build_brief(self.vault, topic, limit=limit)

    def test_crlf_and_embedded_code_fences_preserve_exact_citations(self):
        self.note.write_bytes(self.note.read_bytes().replace(b"\n", b"\r\n") + b"\r\n```text\r\nexample\r\n```\r\n")
        bundle = evidence_brief.build_brief(self.vault, "选品")
        self.assertEqual(evidence_brief.validate_brief(bundle, self.vault), [])
        self.assertIn("\r\n", bundle["documents"][0]["excerpts"][0]["text"])

    def test_force_cannot_overwrite_cited_original_and_changed_note_blocks_export(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        original = self.note.read_bytes()
        with self.assertRaises(ValueError):
            evidence_brief.write_brief(bundle, self.note, overwrite=True)
        self.assertEqual(self.note.read_bytes(), original)
        self.note.write_text("different content")
        with self.assertRaises(ValueError):
            evidence_brief.write_brief(bundle, Path(self.temporary.name) / "new.md")

    def test_existing_json_does_not_leave_a_partial_markdown_export(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        output = Path(self.temporary.name) / "new.md"
        output.with_suffix(".json").write_text("existing")
        with self.assertRaises(FileExistsError):
            evidence_brief.write_brief(bundle, output)
        self.assertFalse(output.exists())
        self.assertEqual(output.with_suffix(".json").read_text(), "existing")

    def test_force_only_replaces_briefs_not_unrelated_documents(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        output = self.vault / "unrelated.md"
        output.write_text("Handwritten notes unrelated to the query")
        with self.assertRaises(ValueError):
            evidence_brief.write_brief(bundle, output, overwrite=True)
        self.assertEqual(output.read_text(), "Handwritten notes unrelated to the query")
        output.unlink()
        output.with_suffix(".json").write_text('{"private": "data"}')
        with self.assertRaises(ValueError):
            evidence_brief.write_brief(bundle, output, overwrite=True)
        self.assertFalse(output.exists())
        output.with_suffix(".json").unlink()
        evidence_brief.write_brief(bundle, output)
        evidence_brief.write_brief(bundle, output, overwrite=True)
        self.assertEqual(json.loads(output.with_suffix(".json").read_text()), bundle)

    def test_brief_respects_explicit_database_environment(self):
        db = Path(self.temporary.name) / "custom.sqlite"
        with mock.patch.dict(os.environ, {"VAULT_INDEX_DB": str(db)}):
            result = evidence_brief.build_brief(self.vault, "选品")
        self.assertEqual(len(result["documents"]), 1)
        self.assertTrue(db.exists())
        self.assertFalse((self.vault / ".chubby" / "index.sqlite").exists())

    def test_saved_briefs_cannot_crowd_original_sources_out_of_search(self):
        bundle = evidence_brief.build_brief(self.vault, "选品")
        for index in range(8):
            evidence_brief.write_brief(bundle, self.vault / f"brief-{index}.md")
        result = evidence_brief.build_brief(self.vault, "选品", limit=1)
        self.assertEqual([item["path"] for item in result["documents"]], [self.note.name])


if __name__ == "__main__":
    unittest.main()
