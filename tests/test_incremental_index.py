import os
import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import vault_index as index


class IncrementalIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir()
        self.db = self.vault / ".chubby" / "index.sqlite"

    def note(self, name, body="original", title="Title", source="https://example.com/source"):
        path = self.vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'---\ntitle: "{title}"\nsource: "{source}"\ntags: [AI]\n---\n\n{body}\n', encoding="utf-8")
        return path

    def vectors(self):
        with sqlite3.connect(self.db) as conn:
            return conn.execute("SELECT * FROM embeddings ORDER BY path").fetchall()

    def seed_vectors(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO embeddings SELECT path, 'local', 'test', 2, '[1,0]', 'old-time' FROM notes")

    def test_sync_changes_and_preserves_only_unchanged_embedding_inputs(self):
        self.note("keep.md")
        changed = self.note("change.md")
        deleted = self.note("delete.md")
        first = index.sync_vault(self.vault, self.db)
        self.assertEqual(first["added"], 3)
        self.seed_vectors()
        old_stat = changed.stat()
        self.note("change.md", body="modified")
        os.utime(changed, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
        deleted.unlink()
        self.note("new.md")
        result = index.sync_vault(self.vault, self.db)
        self.assertEqual((result["added"], result["updated"], result["deleted"], result["unchanged"]), (1, 1, 1, 1))
        self.assertEqual([row[0] for row in self.vectors()], ["keep.md"])
        self.assertEqual(self.vectors()[0][-1], "old-time")
        self.assertEqual(index.search(self.db, "modified")[0]["source"], "https://example.com/source")
        self.assertEqual(index.semantic_search(self.db, "modified")[0]["source"], "https://example.com/source")

    def test_metadata_touch_and_body_tail_preserve_vectors_but_title_change_invalidates(self):
        path = self.note("note.md", body="a" * 6100)
        index.index_vault(self.vault, self.db)
        self.seed_vectors()
        before = self.vectors()
        self.note("note.md", body="a" * 6100 + "new tail", source="https://example.com/updated")
        index.index_vault(self.vault, self.db)
        self.assertEqual(self.vectors(), before)
        path.write_text(path.read_text().replace('title: "Title"', 'title: "Changed"'), encoding="utf-8")
        index.index_vault(self.vault, self.db)
        self.assertEqual(self.vectors(), [])

    def test_read_or_scan_failure_does_not_delete_or_partially_update(self):
        self.note("one.md")
        self.note("two.md")
        index.sync_vault(self.vault, self.db)
        self.seed_vectors()
        self.note("one.md", body="changed")
        original = index.note_record

        def broken(vault, path):
            if path.name == "two.md":
                raise PermissionError("unreadable note")
            return original(vault, path)

        with mock.patch.object(index, "note_record", side_effect=broken), self.assertRaises(PermissionError):
            index.sync_vault(self.vault, self.db)
        self.assertEqual(len(self.vectors()), 2)
        self.assertEqual(index.search(self.db, "changed"), [])

        def partial_scan(vault):
            yield self.vault / "one.md"
            raise PermissionError("unreadable directory")

        with mock.patch.object(index, "iter_markdown", side_effect=partial_scan), self.assertRaises(PermissionError):
            index.sync_vault(self.vault, self.db)
        self.assertEqual(index.stats(self.db)["notes"], 2)

    def test_bound_database_rejects_another_vault_without_mutation(self):
        self.note("private.md")
        index.sync_vault(self.vault, self.db)
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        with self.assertRaisesRegex(ValueError, "vault"):
            index.sync_vault(other, self.db)
        self.assertEqual(index.stats(self.db)["notes"], 1)

    def test_external_symlinks_fail_closed_and_do_not_delete_index(self):
        self.note("keep.md")
        index.sync_vault(self.vault, self.db)
        external = Path(self.tmp.name) / "secret.md"
        external.write_text("secret", encoding="utf-8")
        (self.vault / "leak.md").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "vault"):
            index.sync_vault(self.vault, self.db)
        self.assertEqual(index.stats(self.db)["notes"], 1)

    def test_legacy_database_migrates_without_losing_vectors_and_rebuild_is_explicit(self):
        self.note("legacy.md")
        self.db.parent.mkdir()
        with sqlite3.connect(self.db) as conn:
            index.reset_schema(conn)
            record = index.note_record(self.vault, self.vault / "legacy.md")
            conn.execute("INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(record.values()))
        self.seed_vectors()
        before = self.vectors()
        result = index.index_vault(self.vault, self.db)
        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(self.vectors(), before)
        index.index_vault(self.vault, self.db, rebuild=True)
        self.assertEqual(self.vectors(), [])

    def test_default_database_lives_in_vault_and_old_default_is_migrated(self):
        self.note("legacy.md")
        legacy = self.db.with_name("vault_index.sqlite")
        index.index_vault(self.vault, legacy)
        with sqlite3.connect(legacy) as conn:
            conn.execute("INSERT INTO embeddings SELECT path, 'local', 'test', 2, '[1,0]', 'old-time' FROM notes")
        with mock.patch.dict(os.environ, {}, clear=True):
            result = index.sync_vault(self.vault)
        self.assertEqual(Path(result["db"]), self.db.resolve())
        self.assertEqual(len(self.vectors()), 1)
        self.assertTrue(legacy.exists())

    def test_embedding_command_only_requests_missing_vectors(self):
        self.note("note.md")
        with mock.patch.object(index, "embed_texts", return_value=[[1.0, 0.0]]) as provider:
            index.embed_vault(self.vault, self.db, provider="local", model="test")
            index.embed_vault(self.vault, self.db, provider="local", model="test")
        self.assertEqual(provider.call_count, 1)

    def test_mid_transaction_error_rolls_back_updated_rows_and_vectors(self):
        self.note("first.md")
        self.note("second.md")
        index.sync_vault(self.vault, self.db)
        self.seed_vectors()
        self.note("first.md", body="changed one")
        self.note("second.md", body="changed two")
        original = index.embedding_text

        def fail_second(record):
            if record["path"] == "second.md":
                raise RuntimeError("simulated write-phase failure")
            return original(record)

        with mock.patch.object(index, "embedding_text", side_effect=fail_second), self.assertRaises(RuntimeError):
            index.sync_vault(self.vault, self.db)
        self.assertEqual(len(self.vectors()), 2)
        self.assertEqual(index.search(self.db, "changed"), [])

    def test_missing_fts_table_is_repaired_for_unchanged_notes(self):
        self.note("note.md", body="repairable")
        result = index.sync_vault(self.vault, self.db)
        if not result["fts5"]:
            self.skipTest("SQLite has no FTS5")
        with sqlite3.connect(self.db) as conn:
            conn.execute("DROP TABLE notes_fts")
        index.sync_vault(self.vault, self.db)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(index.fts_query(conn, "repairable")[0]["path"], "note.md")

    def test_external_directory_symlink_and_invalid_text_leave_existing_db_intact(self):
        self.note("note.md")
        index.sync_vault(self.vault, self.db)
        external = Path(self.tmp.name) / "outside"
        external.mkdir()
        link = self.vault / "linked"
        link.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "vault"):
            index.sync_vault(self.vault, self.db)
        link.unlink()
        (self.vault / "broken.md").write_bytes(b"\xff")
        with self.assertRaises(UnicodeDecodeError):
            index.sync_vault(self.vault, self.db)
        self.assertEqual(index.stats(self.db)["notes"], 1)

    def test_unbound_external_legacy_database_requires_proven_ownership(self):
        self.note("note.md")
        external = Path(self.tmp.name) / "legacy.sqlite"
        index.sync_vault(self.vault, external)
        with sqlite3.connect(external) as conn:
            conn.execute("DROP TABLE index_metadata")
        index.sync_vault(self.vault, external)
        with sqlite3.connect(external) as conn:
            conn.execute("DROP TABLE index_metadata")
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        with self.assertRaisesRegex(ValueError, "legacy index"):
            index.sync_vault(other, external)
        self.assertEqual(index.stats(external)["notes"], 1)
        self.assertEqual(index.index_vault(other, external, rebuild=True)["notes"], 0)

    def test_cli_uses_vault_default_and_environment_override(self):
        self.note("note.md", body="searchable")
        with mock.patch.dict(os.environ, {"VAULT_DIR": str(self.vault)}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(index.main(["index", str(self.vault)]), 0)
            self.assertEqual(index.main(["search", "searchable", "--json"]), 0)
        override = Path(self.tmp.name) / "override.sqlite"
        with mock.patch.dict(os.environ, {"VAULT_INDEX_DB": str(override)}, clear=True):
            self.assertEqual(index.sync_vault(self.vault)["db"], str(override.resolve()))

    def test_search_without_fts_uses_like_and_retains_source(self):
        self.note("note.md", body="中文词语")
        with mock.patch.object(index, "has_fts5", return_value=False):
            index.sync_vault(self.vault, self.db)
        self.assertEqual(index.search(self.db, "中文")[0]["source"], "https://example.com/source")

    def test_explicit_logical_db_path_cannot_escape_through_symlink(self):
        self.note("note.md")
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        self.db.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "vault"):
            index.sync_vault(self.vault, self.db)
        self.assertFalse((outside / "index.sqlite").exists())

    def test_embedding_provider_runs_without_write_lock_and_discards_stale_response(self):
        self.note("note.md", body="before provider")

        def provider(texts, provider, model):
            # A concurrent pipeline/MCP sync can commit while the provider works.
            self.note("note.md", body="after provider")
            index.sync_vault(self.vault, self.db)
            return [[1.0, 0.0]]

        with mock.patch.object(index, "embed_texts", side_effect=provider):
            result = index.embed_vault(self.vault, self.db, provider="local", model="test")
        self.assertEqual(result["notes"], 0)
        self.assertEqual(result["skipped_changed"], 1)
        self.assertEqual(self.vectors(), [])

    def test_content_type_exclusions_apply_before_search_limits_and_ranking(self):
        self.note("original.md", body="searchable original material")
        for number in range(6):
            path = self.note(f"generated-{number}.md", body="searchable", title="searchable")
            path.write_text(path.read_text().replace("tags: [AI]", "tags: [AI]\ncontent_type: research_brief"), encoding="utf-8")
        result = index.sync_vault(self.vault, self.db)
        self.seed_vectors()
        options = {"query": "searchable", "limit": 1, "exclude_content_types": ("research_brief",)}
        self.assertEqual(index.search(self.db, **options)[0]["path"], "original.md")
        self.assertEqual(index.semantic_search(self.db, **options)[0]["path"], "original.md")
        with mock.patch.object(index, "embed_texts", return_value=[[1.0, 0.0]]):
            self.assertEqual(index.semantic_search(self.db, provider="local", model="test", **options)[0]["path"], "original.md")
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(index.like_query(conn, **options)[0]["path"], "original.md")
            if result["fts5"]:
                self.assertEqual(index.fts_query(conn, **options)[0]["path"], "original.md")
        self.assertEqual(len(index.search(self.db, "searchable")), 7)


if __name__ == "__main__":
    unittest.main()
