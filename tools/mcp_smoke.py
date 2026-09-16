#!/usr/bin/env python3
"""Verify the real MCP stdio entrypoint with an isolated temporary vault."""

import argparse
import asyncio
from datetime import timedelta
import importlib.metadata
import json
import math
from pathlib import Path
import shlex
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "knowledge-base-management" / "scripts" / "mcp_server.py"
EXPECTED_TOOLS = {
    "search_vault",
    "semantic_search_vault",
    "read_kb_note",
    "list_recent_notes",
    "reindex_vault",
    "vault_index_stats",
}


async def run_smoke(timeout=20):
    # Keep --help usable without the optional SDK.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    with tempfile.TemporaryDirectory(prefix="chubby-mcp-smoke-") as tmpdir:
        vault = Path(tmpdir) / "vault"
        vault.mkdir()
        note = (
            "---\ntitle: MCP smoke note\nplatform: x\n---\n\n"
            "# MCP smoke note\nchubby_stdio_probe successful retrieval.\n"
        )
        (vault / "probe.md").write_text(note, encoding="utf-8")
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER)],
            env={
                "VAULT_DIR": str(vault),
                "VAULT_INDEX_DB": str(Path(tmpdir) / "index.sqlite"),
                "CHUBBY_EMBEDDING_PROVIDER": "lite",
            },
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=timeout)
            ) as session:
                init = await session.initialize()
                if init.serverInfo.name != "chubby-kb":
                    raise RuntimeError(f"Unexpected server: {init.serverInfo.name}")
                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                if names != EXPECTED_TOOLS:
                    raise RuntimeError(f"Unexpected tools: {sorted(names)}")
                search = await session.call_tool("search_vault", {"query": "chubby_stdio_probe"})
                search_text = "\n".join(item.text for item in search.content if item.type == "text")
                if search.isError or "probe.md" not in search_text:
                    raise RuntimeError(f"Search failed: {search_text}")
                result = await session.call_tool("read_kb_note", {"path": "probe.md"})
                read_text = "\n".join(item.text for item in result.content if item.type == "text")
                if result.isError or note not in read_text:
                    raise RuntimeError(f"Read failed: {read_text}")
                return {
                    "status": "passed",
                    "sdk_version": importlib.metadata.version("mcp"),
                    "server": init.serverInfo.name,
                    "protocol_version": init.protocolVersion,
                    "tools": sorted(names),
                    "search": "passed",
                    "read": "passed",
                }


def error_details(exc):
    children = getattr(exc, "exceptions", None)
    if children:
        return "; ".join(error_details(child) for child in children)
    return str(exc) or type(exc).__name__


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output the verification result as JSON")
    parser.add_argument("--timeout", type=float, default=20, help="Overall timeout in seconds (default: 20)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite positive number")
    try:
        result = asyncio.run(asyncio.wait_for(run_smoke(args.timeout), timeout=args.timeout))
    except Exception as exc:
        install = shlex.join([
            sys.executable, "-m", "pip", "install", "-r",
            str(ROOT / "knowledge-base-management" / "requirements-mcp.txt"),
        ])
        print(f"MCP smoke failed: {error_details(exc)}\nMCP dependency: {install}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            f"MCP smoke passed: {result['server']}, mcp {result['sdk_version']}, "
            f"protocol {result['protocol_version']}, 6 tools, search + read OK"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
