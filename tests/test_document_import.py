import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import quote

from tools import import_document as importer


class DocumentImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "中文 原稿"
        self.source.mkdir()
        self.output = self.root / "导入 结果"

    def note(self, name, body):
        path = self.source / name
        path.write_text(body, encoding="utf-8")
        return path

    def fields(self, output):
        front = output.read_text(encoding="utf-8").split("---", 2)[1]
        return {key: json.loads(value) for key, value in
                (line.split(":", 1) for line in front.strip().splitlines())}

    def test_markdown_preserves_body_and_safe_provenance_only(self):
        body = "# 本地标题\n\n原文 **内容**。\n"
        source = self.note("原稿.markdown", '---\ntitle: "正式标题"\nsource: https://example.com/article\n'
                           'platform: youtube\nsource_id: injected\nrun_id: old\nenriched: true\n---\n' + body)
        original = source.read_bytes()
        output = importer.import_document(source, self.output)
        fields = self.fields(output)
        self.assertEqual(fields["title"], "正式标题")
        self.assertEqual(fields["source"], "https://example.com/article")
        self.assertEqual(fields["platform"], "content")
        self.assertEqual(fields["type"], "note")
        self.assertEqual(fields["source_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(fields["original_path"], str(source.resolve()))
        self.assertEqual(fields["source_fingerprint"], importer.document_fingerprint(source))
        self.assertNotIn("run_id", fields)
        self.assertNotIn("source_id", fields)
        self.assertNotIn("enriched", fields)
        self.assertTrue(output.read_text().endswith(body))
        self.assertEqual(source.read_bytes(), original)

    def test_text_source_override_and_default_file_uri(self):
        source = self.note("行业 资料.txt", "这是原始文字。\n第二行。\n")
        output = importer.import_document(source, self.output)
        self.assertEqual(self.fields(output)["source"], source.resolve().as_uri())
        other = importer.import_document(source, self.output, "https://example.com/original")
        self.assertEqual(self.fields(other)["source"], "https://example.com/original")
        self.assertNotEqual(other, output)
        for url in ("file:///tmp/example", "https://user:password@example.com/x", "javascript:alert(1)", "https://"):
            with self.assertRaises(ValueError):
                importer.import_document(source, self.output, url)

    def test_escaped_markup_is_literal_and_does_not_copy_private_files(self):
        secret = self.source / "secret.txt"
        secret.write_text("private document")
        body = r'Literal \[private](secret.txt), \<img src="secret.txt"> and \![[secret.txt]].' + "\n"
        source = self.note("literal.md", body)
        output = importer.import_document(source, self.output)
        self.assertTrue(output.read_text().endswith(body))
        self.assertFalse(output.with_suffix(".assets").exists())
        self.assertEqual(self.fields(output)["source_assets"], [])

    def test_untrusted_frontmatter_source_falls_back_to_file(self):
        source = self.note("note.md", '---\nsource: "javascript:alert(1)"\ntitle: "a\\nb"\n---\nBody\n')
        output = importer.import_document(source, self.output)
        self.assertEqual(self.fields(output)["source"], source.resolve().as_uri())
        self.assertEqual(self.fields(output)["title"], "a b")

    def test_invalid_utf8_empty_unsupported_and_unclosed_frontmatter_fail(self):
        bad = self.source / "bad.txt"
        bad.write_bytes(b"\xff\xfe")
        for source in (bad, self.note("empty.txt", " \n"), self.note("data.docx", "hello"),
                       self.note("header.md", "---\ntitle: Missing ending"),
                       self.note("metadata.md", "---\ntitle: Metadata only\n---\n")):
            with self.assertRaises((ValueError, UnicodeDecodeError)):
                importer.import_document(source, self.output)
        self.assertFalse(self.output.exists())

    def test_same_title_never_overwrites_note_or_assets(self):
        source = self.note("note.md", "# Same title\nBody\n")
        first = importer.import_document(source, self.output)
        first.write_text("User edits")
        second = importer.import_document(source, self.output)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_text(), "User edits")
        self.assertIn("Body", second.read_text())

    def test_copies_only_referenced_assets_and_fingerprint_changes(self):
        assets = self.source / "图片 目录"
        assets.mkdir()
        picture = assets / "图 一.png"
        picture.write_bytes(b"picture one")
        (assets / "private.txt").write_text("Do not copy")
        source = self.note("图文.md", '# 图文\n\n![图](<图片 目录/图 一.png> "说明")\n'
                           '[图片引用][p]\n[p]: <图片 目录/图 一.png>\n'
                           '![远程](https://example.com/p.png)\n')
        before = importer.document_fingerprint(source)
        output = importer.import_document(source, self.output)
        copied = output.with_suffix(".assets") / "图片 目录" / "图 一.png"
        self.assertEqual(copied.read_bytes(), picture.read_bytes())
        self.assertFalse((copied.parent / "private.txt").exists())
        content = output.read_text()
        self.assertIn("https://example.com/p.png", content)
        self.assertIn(quote(output.stem) + ".assets/", content)
        self.assertNotIn("<图片 目录/图 一.png>", content)
        picture.write_bytes(b"picture two")
        self.assertNotEqual(before, importer.document_fingerprint(source))

    def test_parent_escape_absolute_symlink_and_missing_assets_fail(self):
        outside = self.root / "private.png"
        outside.write_bytes(b"secret")
        (self.source / "link.png").symlink_to(outside)
        for reference in ("../private.png", "%2e%2e/private.png", str(outside), "link.png", "missing.png"):
            source = self.note("unsafe.md", f"# Unsafe\n![a]({reference})\n")
            with self.assertRaises((ValueError, OSError)):
                importer.import_document(source, self.output)
            with self.assertRaises((ValueError, OSError)):
                importer.document_fingerprint(source)
        self.assertFalse(self.output.exists())

    def test_code_examples_and_anchors_are_not_attachments(self):
        source = self.note("code.md", '# Examples\n\n`![x](missing.png)`\n'
                           '```markdown\n![x](also-missing.png)\n```\n[part](#part)\n')
        output = importer.import_document(source, self.output)
        self.assertIn("also-missing.png", output.read_text())
        self.assertFalse(output.with_suffix(".assets").exists())

    def test_longer_and_unclosed_code_fences_do_not_copy_examples(self):
        for body in ('# Example\n```markdown\n![x](missing.png)\n````\n',
                     '# Example\n~~~markdown\n![x](missing.png)\n'):
            source = self.note("fence.md", body)
            output = importer.import_document(source, self.output)
            self.assertTrue(output.read_text().endswith(body))

    def test_angle_destination_with_unbalanced_parenthesis_and_html_bare_src(self):
        (self.source / "pic(.png").write_bytes(b"picture")
        source = self.note("syntax.md", '# Syntax\n![x](<pic(.png> "title")\n<img src=pic%28.png>\n')
        output = importer.import_document(source, self.output)
        self.assertEqual(output.read_text().count(output.stem + ".assets/"), 2)
        self.assertEqual((output.with_suffix(".assets") / "pic(.png").read_bytes(), b"picture")

    def test_indented_list_images_are_copied_but_indented_code_is_not(self):
        (self.source / "pic.png").write_bytes(b"picture")
        source = self.note("list.md", '# List\n\n- Item\n\n    ![x](pic.png)\n\n'
                           'Example code follows.\n\n    ![x](missing.png)\n')
        output = importer.import_document(source, self.output)
        self.assertTrue((output.with_suffix(".assets") / "pic.png").is_file())
        self.assertIn("![x](missing.png)", output.read_text())

    def test_inline_parentheses_html_and_wiki_assets(self):
        (self.source / "pic(1).png").write_bytes(b"picture")
        source = self.note("rich.md", '# Rich\n![x](pic(1).png)\n'
                           '<img src="pic(1).png">\n![[pic(1).png|caption]]\n')
        output = importer.import_document(source, self.output)
        self.assertEqual((output.with_suffix(".assets") / "pic(1).png").read_bytes(), b"picture")
        self.assertEqual(output.read_text().count(output.stem + ".assets/"), 3)

    def test_missing_pdf_dependency_is_actionable(self):
        source = self.source / "report.pdf"
        source.write_bytes(b"%PDF-test")
        with (patch.object(importer.importlib, "import_module", side_effect=ModuleNotFoundError("pymupdf")),
              self.assertRaisesRegex(ValueError, "pymupdf")):
            importer.import_document(source, self.output)
        self.assertFalse(self.output.exists())

    def fake_pdf(self, text):
        module = MagicMock()
        document = module.open.return_value.__enter__.return_value
        document.needs_pass = False
        page = MagicMock()
        page.get_text.return_value = text
        document.__iter__.return_value = iter([page])
        return module

    def test_pdf_extracts_text_locally_and_rejects_scanned_documents(self):
        source = self.source / "report.pdf"
        source.write_bytes(b"%PDF-test")
        with patch.object(importer.importlib, "import_module", return_value=self.fake_pdf("PDF 正文\n")):
            output = importer.import_document(source, self.output)
        self.assertIn("PDF 正文", output.read_text())
        self.assertEqual(self.fields(output)["import_method"], "pdf_text")
        with (patch.object(importer.importlib, "import_module", return_value=self.fake_pdf(" \n")),
              self.assertRaisesRegex(ValueError, "文字层|扫描")):
            importer.import_document(source, self.output)

    def test_cli_isolated_mode_and_nonzero_failures(self):
        script = Path(importer.__file__)
        source = self.note("cli.md", "# CLI\nOriginal content\n")
        result = subprocess.run([sys.executable, "-I", str(script), str(source), "--output", str(self.output)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(result.stdout.strip().splitlines()[-1]).is_absolute())
        self.assertTrue(Path(result.stdout.strip().splitlines()[-1]).is_file())
        bad = subprocess.run([sys.executable, "-I", str(script), str(self.source / "absent.md"),
                              "--output", str(self.output)], capture_output=True, text=True, check=False)
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse(bad.stdout.strip())


if __name__ == "__main__":
    unittest.main()
