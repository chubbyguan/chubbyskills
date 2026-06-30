#!/usr/bin/env python3
"""Demonstrate an Agent-style task using the chubbyskills vault MCP functions."""

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = ROOT / "fixtures" / "mcp-vault"
MCP_SERVER = ROOT / "knowledge-base-management" / "scripts" / "mcp_server.py"


def load_mcp_server():
    spec = importlib.util.spec_from_file_location("chubby_mcp_workflow_demo", MCP_SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load MCP server: {MCP_SERVER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_paths(search_text):
    return re.findall(r"`([^`]+\.md)`", search_text)


def first_bullets(note_text, limit=4):
    bullets = []
    for line in note_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:])
        if len(bullets) >= limit:
            break
    return bullets


def run_workflow(vault, task, query, limit=3):
    with tempfile.TemporaryDirectory() as tmpdir:
        mcp = load_mcp_server()
        mcp.INDEX_DB = str(Path(tmpdir) / "vault_index.sqlite")
        reindex_result = mcp.reindex(str(vault))
        search_result = mcp.semantic_search(str(vault), query, limit=limit)
        paths = extract_paths(search_result)
        notes = []
        for path in paths[:limit]:
            text = mcp.read_note(str(vault), path)
            notes.append({"path": path, "text": text, "bullets": first_bullets(text)})

    answer_lines = [
        "# Vault-assisted answer",
        "",
        f"Task: {task}",
        "",
        "## Answer",
        "",
    ]
    if not notes:
        answer_lines.append("没有在 vault 中找到足够相关的笔记。")
    else:
        answer_lines.append("基于 vault，建议按这个顺序处理：")
        for note in notes:
            for bullet in note["bullets"][:2]:
                answer_lines.append(f"- {bullet}（source: `{note['path']}`）")
        answer_lines.extend(["", "## Sources", ""])
        for note in notes:
            answer_lines.append(f"- `{note['path']}`")

    return {
        "task": task,
        "query": query,
        "reindex": reindex_result,
        "search": search_result,
        "notes": [{"path": item["path"], "bullets": item["bullets"]} for item in notes],
        "answer": "\n".join(answer_lines),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run an MCP-style vault workflow demo")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--task", default="根据知识库，给我一个内容复盘的下一步行动建议")
    parser.add_argument("--query", default="Agent 如何用 vault 做内容策略复盘")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        print(f"❌ vault not found: {vault}", file=sys.stderr)
        return 1
    result = run_workflow(vault, args.task, args.query, limit=args.limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["answer"])
    return 0 if result["notes"] else 1


if __name__ == "__main__":
    sys.exit(main())
