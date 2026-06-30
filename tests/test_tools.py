import os
import shutil
import subprocess
import sys
import types
import importlib.util
import tempfile
import unittest

from tools import chubby
from tools import chubby_ingest
from tools import golden_outputs
from tools import mcp_workflow_demo
from tools import platform_adapter
from tools import platform_health
from tools import platform_smoke
from tools import validate_outputs
from tools import vault_curator
from tools import vault_index


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DetectSkillTest(unittest.TestCase):
    def test_detects_common_platforms(self):
        cases = {
            "BV1xx411c7mD": "bilibili",
            "https://www.youtube.com/watch?v=abc": "youtube",
            "https://youtu.be/abc": "youtube",
            "https://v.douyin.com/example/": "douyin",
            "https://x.com/example/status/123456": "x",
            "https://twitter.com/example/status/123456": "x",
            "https://www.xiaohongshu.com/explore/abc": "xiaohongshu",
            "https://mp.weixin.qq.com/s/abc": "wechat",
            "https://www.zhihu.com/video/123": "zhihu",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(chubby_ingest.detect_skill(source), expected)

    def test_detects_local_audio_as_podcast(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            self.assertEqual(chubby_ingest.detect_skill(f.name), "podcast")

    def test_detects_local_pdf_as_wechat(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            self.assertEqual(chubby_ingest.detect_skill(f.name), "wechat")


class OutputValidatorTest(unittest.TestCase):
    def test_examples_are_valid(self):
        examples = os.path.join(ROOT, "examples", "outputs")
        for path in validate_outputs.iter_markdown([examples]):
            with self.subTest(path=path):
                errors = [
                    p for p in validate_outputs.validate_file(path) if p["level"] == "error"
                ]
                self.assertEqual(errors, [])

    def test_missing_frontmatter_is_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as f:
            f.write("# Missing\n")
            f.flush()
            problems = validate_outputs.validate_file(f.name)
        self.assertTrue(any(p["level"] == "error" for p in problems))

    def test_schema_v1_fields_are_required_when_declared(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as f:
            f.write(
                "---\n"
                "title: Bad v1\n"
                "type: note\n"
                "platform: x\n"
                "source: https://x.com/example/status/1\n"
                "created: 2026-06-30\n"
                "schema_version: 1\n"
                "---\n\n"
                "# Bad v1\n"
            )
            f.flush()
            problems = validate_outputs.validate_file(f.name)
        messages = [p["message"] for p in problems]
        self.assertIn("missing schema v1 field: run_id", messages)

    def test_schema_v1_assets_must_be_complete_inline_list(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as f:
            f.write(
                "---\n"
                "title: Bad assets\n"
                "type: note\n"
                "platform: x\n"
                "source: https://x.com/example/status/1\n"
                "created: 2026-06-30\n"
                "schema_version: 1\n"
                "run_id: r1\n"
                "source_hash: 0123456789abcdef\n"
                "captured_at: \"2026-06-30T16:00:00+08:00\"\n"
                "processed_at: \"2026-06-30T16:00:01+08:00\"\n"
                "content_type: social\n"
                "status: success\n"
                "assets: [broken\n"
                "---\n\n"
                "# Bad assets\n"
            )
            f.flush()
            problems = validate_outputs.validate_file(f.name, require_schema_v1=True)
        messages = [p["message"] for p in problems]
        self.assertIn("assets should use inline list form", messages)

    def test_golden_snapshot_matches_examples(self):
        examples = os.path.join(ROOT, "examples", "outputs")
        golden = os.path.join(ROOT, "fixtures", "golden", "examples_outputs.json")
        actual = golden_outputs.build_snapshot([examples])
        expected = golden_outputs.load_json(golden)
        self.assertEqual(golden_outputs.compare_snapshots(actual, expected), [])


class WorkflowCopyTest(unittest.TestCase):
    def test_copy_into_same_vault_directory_is_noop(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "note.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Note\n")
            self.assertEqual(chubby_ingest.copy_into_vault(path, tmpdir), path)
            self.assertTrue(os.path.exists(path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class PipelineCliTest(unittest.TestCase):
    def test_read_queue_skips_comments_and_blank_lines(self):
        tmpdir = tempfile.mkdtemp()
        try:
            queue = os.path.join(tmpdir, "links.txt")
            with open(queue, "w", encoding="utf-8") as f:
                f.write("\n# comment\nhttps://x.com/example/status/1\n  BV1xx411c7mD  \n")
            self.assertEqual(
                chubby.read_queue(queue),
                ["https://x.com/example/status/1", "BV1xx411c7mD"],
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_stamp_pipeline_metadata_adds_schema_v1(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "note.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "title: Note\n"
                    "type: note\n"
                    "platform: x\n"
                    "source: https://x.com/example/status/1\n"
                    "created: 2026-06-30\n"
                    "---\n\n"
                    "# Note\n"
                )
            record = {
                "run_id": "test-run",
                "source_hash": "0123456789abcdef",
                "started_at": "2026-06-30T16:00:00+08:00",
                "finished_at": "2026-06-30T16:00:01+08:00",
                "content_type": "social",
                "status": "success",
                "output_path": path,
            }
            self.assertTrue(chubby.stamp_pipeline_metadata(record))
            problems = validate_outputs.validate_file(path, require_schema_v1=True)
            self.assertEqual([p for p in problems if p["level"] == "error"], [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_dry_run_records_state(self):
        tmpdir = tempfile.mkdtemp()
        try:
            config = dict(chubby.DEFAULT_CONFIG)
            config["state_file"] = os.path.join(tmpdir, "runs.jsonl")
            config["report_dir"] = os.path.join(tmpdir, "reports")
            config["output_dir"] = os.path.join(tmpdir, "output")
            config["queue_file"] = os.path.join(tmpdir, "links.txt")
            args = types.SimpleNamespace(
                output=None,
                skill=None,
                vault=None,
                enrich=False,
                dry_run=True,
                extra=[],
            )
            record = chubby.run_ingest_source("https://x.com/example/status/1", args, config)
            chubby.append_record(config, record)
            records = chubby.load_records(config)
            self.assertEqual(record["status"], "dry_run")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "dry_run")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_config_arg_can_appear_after_subcommand(self):
        cleaned, config_path = chubby.extract_config_arg(
            ["ingest", "https://x.com/example/status/1", "--dry-run", "--config", "/tmp/chubby.yaml"]
        )
        self.assertEqual(config_path, "/tmp/chubby.yaml")
        self.assertEqual(cleaned, ["ingest", "https://x.com/example/status/1", "--dry-run"])

    def test_timeout_records_failed_run(self):
        tmpdir = tempfile.mkdtemp()
        try:
            config = dict(chubby.DEFAULT_CONFIG)
            config["state_file"] = os.path.join(tmpdir, "runs.jsonl")
            config["report_dir"] = os.path.join(tmpdir, "reports")
            config["output_dir"] = os.path.join(tmpdir, "output")
            config["queue_file"] = os.path.join(tmpdir, "links.txt")
            config["timeout_seconds"] = "1"
            args = types.SimpleNamespace(
                output=None,
                skill="podcast",
                vault=None,
                enrich=False,
                dry_run=False,
                extra=[],
            )
            fake_tools = os.path.join(tmpdir, "tools")
            os.makedirs(fake_tools)
            with open(os.path.join(fake_tools, "chubby_ingest.py"), "w", encoding="utf-8") as f:
                f.write("import time\ntime.sleep(5)\n")
            original_tools_dir = chubby.TOOLS_DIR
            chubby.TOOLS_DIR = chubby.Path(fake_tools)
            try:
                record = chubby.run_ingest_source("audio.mp3", args, config)
            finally:
                chubby.TOOLS_DIR = original_tools_dir
            self.assertEqual(record["status"], "failed")
            self.assertIn("timeout after 1s", record["error"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_stamp_all_outputs_updates_working_and_vault_copy(self):
        tmpdir = tempfile.mkdtemp()
        try:
            source_path = os.path.join(tmpdir, "output", "note.md")
            vault_path = os.path.join(tmpdir, "vault", "note.md")
            os.makedirs(os.path.dirname(source_path))
            os.makedirs(os.path.dirname(vault_path))
            body = (
                "---\n"
                "title: Note\n"
                "type: note\n"
                "platform: x\n"
                "source: https://x.com/example/status/1\n"
                "created: 2026-06-30\n"
                "---\n\n"
                "# Note\n"
            )
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(body)
            with open(vault_path, "w", encoding="utf-8") as f:
                f.write(body)
            record = {
                "run_id": "test-run",
                "source_hash": "0123456789abcdef",
                "started_at": "2026-06-30T16:00:00+08:00",
                "finished_at": "2026-06-30T16:00:01+08:00",
                "content_type": "social",
                "status": "success",
                "output_path": vault_path,
                "output_paths": [source_path, vault_path],
            }
            stamped = chubby.stamp_all_outputs(record)
            self.assertEqual(set(stamped), {source_path, vault_path})
            for path in (source_path, vault_path):
                problems = validate_outputs.validate_file(path, require_schema_v1=True)
                self.assertEqual([p for p in problems if p["level"] == "error"], [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_vault_output_inferrs_working_output_candidate(self):
        tmpdir = tempfile.mkdtemp()
        try:
            output_dir = os.path.join(tmpdir, "output")
            vault_dir = os.path.join(tmpdir, "vault")
            os.makedirs(output_dir)
            os.makedirs(vault_dir)
            working_path = os.path.join(output_dir, "note.md")
            vault_path = os.path.join(vault_dir, "note.md")
            with open(working_path, "w", encoding="utf-8") as f:
                f.write("# Note\n")
            with open(vault_path, "w", encoding="utf-8") as f:
                f.write("# Note\n")
            record = {
                "output_dir": output_dir,
                "vault_dir": vault_dir,
                "output_path": vault_path,
                "output_paths": [vault_path],
            }
            chubby.add_inferred_working_output(record)
            self.assertEqual(record["output_paths"][0], working_path)
            self.assertIn(vault_path, record["output_paths"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_quickstart_ephemeral_generates_report(self):
        tmpdir = tempfile.mkdtemp()
        try:
            report = os.path.join(tmpdir, "quickstart.md")
            code = chubby.main(["quickstart", "--ephemeral", "--report", report])
            self.assertEqual(code, 0)
            with open(report, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Chubby Quickstart Report", text)
            self.assertIn("示例采集 dry-run", text)
            self.assertIn("知识库索引", text)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class PlatformHealthTest(unittest.TestCase):
    def test_repository_platform_definitions_are_valid(self):
        results = platform_health.run_checks(
            platform_health.DEFAULT_PLATFORM_DIR,
            platform_health.DEFAULT_TEMPLATE_DIR,
            platform_health.ROOT,
        )
        self.assertGreaterEqual(len(results), 10)
        self.assertFalse(platform_health.has_errors(results))

    def test_simple_yaml_parser_reads_inline_lists(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "sample.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write("id: x\nsource_types: [text, image, video]\nstatus: manual\n")
            data = platform_health.parse_simple_yaml(platform_health.Path(path))
            self.assertEqual(data["source_types"], ["text", "image", "video"])
            self.assertEqual(data["status"], "manual")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_missing_script_is_platform_error(self):
        tmpdir = tempfile.mkdtemp()
        try:
            platform_dir = os.path.join(tmpdir, "platforms")
            template_dir = os.path.join(tmpdir, "templates", "sites")
            skill_dir = os.path.join(tmpdir, "demo-skill")
            os.makedirs(platform_dir)
            os.makedirs(template_dir)
            os.makedirs(skill_dir)
            with open(os.path.join(platform_dir, "demo.yaml"), "w", encoding="utf-8") as f:
                f.write(
                    "id: demo\n"
                    "name: Demo\n"
                    "skill: demo-skill\n"
                    "script: scripts/missing.py\n"
                    "category: article\n"
                    "status: beta\n"
                    "source_types: [article]\n"
                    "required_deps: []\n"
                    "optional_deps: []\n"
                    "output_contract: markdown_schema_v1\n"
                    "fallback: manual\n"
                    "sample_source: https://example.com\n"
                )
            with open(os.path.join(template_dir, "demo.yaml"), "w", encoding="utf-8") as f:
                f.write(
                    "id: demo\n"
                    "platform: demo\n"
                    "name: Demo template\n"
                    "match: [example.com]\n"
                    "frontmatter: [title, source]\n"
                    "postprocess: [validate_schema_v1]\n"
                )
            results = platform_health.run_checks(
                platform_health.Path(platform_dir),
                platform_health.Path(template_dir),
                platform_health.Path(tmpdir),
            )
            self.assertTrue(platform_health.has_errors(results))
            self.assertIn("missing script", results[0]["errors"][0])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_missing_template_is_platform_error(self):
        tmpdir = tempfile.mkdtemp()
        try:
            platform_dir = os.path.join(tmpdir, "platforms")
            template_dir = os.path.join(tmpdir, "templates", "sites")
            script_dir = os.path.join(tmpdir, "demo-skill", "scripts")
            os.makedirs(platform_dir)
            os.makedirs(template_dir)
            os.makedirs(script_dir)
            with open(os.path.join(script_dir, "run.py"), "w", encoding="utf-8") as f:
                f.write("")
            with open(os.path.join(platform_dir, "demo.yaml"), "w", encoding="utf-8") as f:
                f.write(
                    "id: demo\n"
                    "name: Demo\n"
                    "skill: demo-skill\n"
                    "script: scripts/run.py\n"
                    "category: article\n"
                    "status: beta\n"
                    "source_types: [article]\n"
                    "required_deps: []\n"
                    "optional_deps: []\n"
                    "output_contract: markdown_schema_v1\n"
                    "fallback: manual\n"
                    "sample_source: https://example.com\n"
                )
            results = platform_health.run_checks(
                platform_health.Path(platform_dir),
                platform_health.Path(template_dir),
                platform_health.Path(tmpdir),
            )
            self.assertTrue(platform_health.has_errors(results))
            self.assertIn("missing site template", results[0]["errors"][0])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_output_freshness_detects_stale_status_page(self):
        tmpdir = tempfile.mkdtemp()
        try:
            output = os.path.join(tmpdir, "platform-status.md")
            results = platform_health.run_checks(
                platform_health.DEFAULT_PLATFORM_DIR,
                platform_health.DEFAULT_TEMPLATE_DIR,
                platform_health.ROOT,
            )
            with open(output, "w", encoding="utf-8") as f:
                f.write("# stale\n")
            ok, error = platform_health.output_is_fresh(output, results)
            self.assertFalse(ok)
            self.assertIn("stale", error)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class PlatformSmokeTest(unittest.TestCase):
    def test_offline_smoke_checks_all_platform_routes(self):
        results = platform_smoke.run_matrix(mode="offline")
        self.assertGreaterEqual(len(results), 10)
        self.assertFalse(platform_smoke.has_failures(results))

    def test_fallback_smoke_generates_schema_v1_for_manual_platforms(self):
        results = platform_smoke.run_matrix(mode="fallback")
        manual_results = [
            item for item in results
            if item["platform"] in {"x", "xiaohongshu"}
        ]
        self.assertEqual(len(manual_results), 2)
        self.assertFalse(platform_smoke.has_failures(manual_results))
        self.assertTrue(all(item["status"] == "passed" for item in manual_results))


class VaultIndexTest(unittest.TestCase):
    def write_note(self, root, rel, title, platform, tags, body):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                f"title: {title}\n"
                "type: note\n"
                f"platform: {platform}\n"
                f"source: https://example.com/{platform}\n"
                "created: 2026-06-30\n"
                f"tags: [{tags}]\n"
                "schema_version: 1\n"
                "run_id: test\n"
                "source_hash: 0123456789abcdef\n"
                "captured_at: \"2026-06-30T16:00:00+08:00\"\n"
                "processed_at: \"2026-06-30T16:00:01+08:00\"\n"
                "content_type: note\n"
                "status: success\n"
                "assets: []\n"
                "---\n\n"
                f"# {title}\n\n"
                f"{body}\n"
            )
        return path

    def test_index_search_recent_stats_and_read(self):
        tmpdir = tempfile.mkdtemp()
        try:
            vault = os.path.join(tmpdir, "vault")
            db = os.path.join(tmpdir, "index.sqlite")
            self.write_note(vault, "10_Sources/x/agent.md", "Agent Note", "x", "AI, Agent", "AI Agent workflow")
            self.write_note(vault, "10_Sources/wechat/brand.md", "Brand Note", "wechat", "Brand", "品牌 内容 策略")

            result = vault_index.index_vault(vault, db_path=db)
            self.assertEqual(result["notes"], 2)

            rows = vault_index.search(db_path=db, query="Agent", platform="x", tag="AI")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["path"], "10_Sources/x/agent.md")

            chinese_rows = vault_index.search(db_path=db, query="品牌")
            self.assertEqual(len(chinese_rows), 1)
            self.assertEqual(chinese_rows[0]["platform"], "wechat")

            recent = vault_index.recent(db_path=db, limit=2)
            self.assertEqual(len(recent), 2)

            stats = vault_index.stats(db_path=db)
            self.assertEqual(stats["notes"], 2)
            self.assertEqual(stats["platforms"]["x"], 1)

            note = vault_index.read_note(vault, "10_Sources/x/agent.md")
            self.assertIn("AI Agent workflow", note["text"])

            semantic_rows = vault_index.semantic_search(db_path=db, query="内容策略")
            self.assertEqual(semantic_rows[0]["path"], "10_Sources/wechat/brand.md")
            self.assertGreater(semantic_rows[0]["score"], 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_embedding_provider_search_uses_persisted_vectors(self):
        tmpdir = tempfile.mkdtemp()
        try:
            vault = os.path.join(tmpdir, "vault")
            db = os.path.join(tmpdir, "index.sqlite")
            self.write_note(vault, "10_Sources/x/agent.md", "Agent Note", "x", "AI, Agent", "AI Agent workflow")
            self.write_note(vault, "10_Sources/wechat/brand.md", "Brand Note", "wechat", "Brand", "品牌 内容 策略")

            original_embed_texts = vault_index.embed_texts

            def fake_embed_texts(texts, provider, model):
                vectors = []
                for text in texts:
                    if "内容" in text or "策略" in text or "品牌" in text:
                        vectors.append([1.0, 0.0])
                    else:
                        vectors.append([0.0, 1.0])
                return vectors

            vault_index.embed_texts = fake_embed_texts
            try:
                result = vault_index.embed_vault(
                    vault,
                    db_path=db,
                    provider="openai",
                    model="test-embedding",
                )
                self.assertEqual(result["notes"], 2)
                rows = vault_index.semantic_search(
                    db_path=db,
                    query="内容策略",
                    provider="openai",
                    model="test-embedding",
                )
            finally:
                vault_index.embed_texts = original_embed_texts

            self.assertEqual(rows[0]["path"], "10_Sources/wechat/brand.md")
            self.assertEqual(rows[0]["provider"], "openai")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_read_note_rejects_path_traversal(self):
        tmpdir = tempfile.mkdtemp()
        try:
            vault = os.path.join(tmpdir, "vault")
            os.makedirs(vault)
            with self.assertRaises(ValueError):
                vault_index.read_note(vault, "../secret.md")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class KnowledgeBaseMcpTest(unittest.TestCase):
    def load_mcp_server(self):
        path = os.path.join(ROOT, "knowledge-base-management", "scripts", "mcp_server.py")
        spec = importlib.util.spec_from_file_location("chubby_mcp_server_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_mcp_search_recent_and_stats_use_index(self):
        tmpdir = tempfile.mkdtemp()
        try:
            vault = os.path.join(tmpdir, "vault")
            note_dir = os.path.join(vault, "10_Sources", "x")
            os.makedirs(note_dir, exist_ok=True)
            with open(os.path.join(note_dir, "agent.md"), "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "title: Agent MCP\n"
                    "type: note\n"
                    "platform: x\n"
                    "source: https://x.com/example/status/1\n"
                    "created: 2026-06-30\n"
                    "tags: [AI]\n"
                    "---\n\n"
                    "# Agent MCP\n\n"
                    "AI Agent retrieval test.\n"
                )
            module = self.load_mcp_server()
            self.assertIn("10_Sources/x/agent.md", module.search(vault, "Agent", platform="x"))
            self.assertIn("10_Sources/x/agent.md", module.semantic_search(vault, "retrieval", platform="x"))
            self.assertIn("10_Sources/x/agent.md", module.list_recent(vault, limit=5, platform="x"))
            self.assertIn("x: 1", module.vault_stats(vault))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_mcp_missing_indexer_returns_actionable_error(self):
        tmpdir = tempfile.mkdtemp()
        try:
            vault = os.path.join(tmpdir, "vault")
            os.makedirs(vault)
            module = self.load_mcp_server()
            original_indexer = module.vault_index
            original_error = module.VAULT_INDEX_ERROR
            module.vault_index = None
            module.VAULT_INDEX_ERROR = "missing tools/vault_index.py"
            try:
                result = module.search(vault, "Agent")
                self.assertIn("索引不可用", result)
                self.assertIn("tools/vault_index.py", result)
                self.assertIn("完整 chubbyskills 仓库", result)
            finally:
                module.vault_index = original_indexer
                module.VAULT_INDEX_ERROR = original_error
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_mcp_read_requires_vault_dir(self):
        module = self.load_mcp_server()
        result = module.read_note("", "README.md")
        self.assertIn("索引不可用", result)
        self.assertIn("VAULT_DIR", result)

    def test_mcp_workflow_demo_uses_vault_sources(self):
        vault = os.path.join(ROOT, "fixtures", "mcp-vault")
        result = mcp_workflow_demo.run_workflow(
            vault,
            "给我一个内容复盘建议",
            "Agent vault 内容策略复盘",
        )
        self.assertGreaterEqual(len(result["notes"]), 1)
        self.assertIn("source:", result["answer"])
        self.assertIn("10_Sources", result["answer"])


class VaultCuratorTest(unittest.TestCase):
    def write_inbox_note(self, vault, name="note.md", extra_frontmatter="", body=""):
        inbox = os.path.join(vault, "00_Inbox")
        os.makedirs(inbox, exist_ok=True)
        path = os.path.join(inbox, name)
        body_text = body or "- Build a repeatable capture loop.\n- Review useful ideas weekly.\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "title: Strategy Note\n"
                "type: note\n"
                "platform: wechat\n"
                "source: https://example.com/a\n"
                "created: 2026-06-30\n"
                "tags: [strategy]\n"
                f"{extra_frontmatter}"
                "---\n\n"
                "# Strategy Note\n\n"
                f"{body_text}"
            )
        return path

    def test_archive_moves_inbox_note_to_source_folder(self):
        tmpdir = tempfile.mkdtemp()
        try:
            vault = os.path.join(tmpdir, "vault")
            self.write_inbox_note(vault)
            actions = vault_curator.archive_vault(vault, dry_run=False)
            self.assertEqual(actions[0]["target"], "10_Sources/wechat/note.md")
            target = os.path.join(vault, "10_Sources", "wechat", "note.md")
            self.assertTrue(os.path.exists(target))
            with open(target, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("archived_from", text)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_generate_card_writes_knowledge_card(self):
        tmpdir = tempfile.mkdtemp()
        try:
            vault = os.path.join(tmpdir, "vault")
            self.write_inbox_note(vault, body="This note explains a durable content strategy.\n\n- Capture signals.\n- Distill cards.")
            action = vault_curator.generate_card(vault, "00_Inbox/note.md", dry_run=False)
            self.assertEqual(action["status"], "written")
            target = os.path.join(vault, action["target"])
            self.assertTrue(os.path.exists(target))
            with open(target, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("type: knowledge_card", text)
            self.assertIn("Capture signals", text)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class PlatformAdapterTest(unittest.TestCase):
    def test_scaffold_platform_creates_valid_definition(self):
        tmpdir = tempfile.mkdtemp()
        try:
            args = types.SimpleNamespace(
                id="demo-news",
                name="Demo News",
                skill="demo-news-ingest",
                script="scripts/fetch_demo_news.py",
                category="article",
                status="experimental",
                source_types="article",
                required_deps="",
                optional_deps="",
                fallback="manual",
                sample_source="https://demo.example/news/1",
                match="demo.example",
                notes="test scaffold",
                force=False,
            )
            files = platform_adapter.scaffold_platform(args, repo_root=tmpdir)
            self.assertEqual(len(files), 4)
            results = platform_health.run_checks(
                platform_health.Path(tmpdir) / "platforms",
                platform_health.Path(tmpdir) / "templates" / "sites",
                platform_health.Path(tmpdir),
            )
            self.assertFalse(platform_health.has_errors(results))

            output = os.path.join(tmpdir, "output")
            script = os.path.join(tmpdir, "demo-news-ingest", "scripts", "fetch_demo_news.py")
            subprocess.run(
                [sys.executable, script, args.sample_source, "--output", output],
                check=True,
                capture_output=True,
                text=True,
            )
            sample = os.path.join(output, "demo-news-sample.md")
            platform_set = validate_outputs.known_platforms(os.path.join(tmpdir, "platforms"))
            errors = [
                problem
                for problem in validate_outputs.validate_file(
                    sample,
                    require_schema_v1=True,
                    allowed_platforms=platform_set,
                )
                if problem["level"] == "error"
            ]
            self.assertEqual(errors, [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
