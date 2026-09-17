import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mcp_sync_server", ROOT / "knowledge-base-management/scripts/mcp_server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class McpSyncTests(unittest.TestCase):
    def test_mcp_rejects_symlinked_database_directory(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "INDEX_DB", ""):
            vault = Path(tmp) / "vault"
            vault.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (vault / ".chubby").symlink_to(outside, target_is_directory=True)
            self.assertIn("索引不可用", server.search(vault, "query"))
            self.assertFalse((outside / "index.sqlite").exists())

    def test_running_server_sees_added_changed_and_deleted_notes(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "INDEX_DB", ""):
            vault = Path(tmp)
            self.assertIn("未找到", server.search(vault, "first"))
            note = vault / "note.md"
            note.write_text("---\ntitle: Test\nsource: https://example.com\n---\n\nfirst", encoding="utf-8")
            self.assertIn("note.md", server.search(vault, "first"))
            note.write_text(note.read_text().replace("first", "second"), encoding="utf-8")
            self.assertIn("note.md", server.semantic_search(vault, "second"))
            self.assertIn("未找到", server.search(vault, "first"))
            self.assertIn("note.md", server.list_recent(vault))
            note.unlink()
            self.assertIn("0 篇", server.vault_stats(vault))
            self.assertEqual(Path(server.index_db(vault)), vault / ".chubby" / "index.sqlite")


if __name__ == "__main__":
    unittest.main()
