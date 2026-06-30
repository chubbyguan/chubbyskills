#!/usr/bin/env python3
"""
知识库 MCP Server —— 让任何 Agent 都能检索你的 Obsidian 知识库

把本地 vault 的「搜索 / 语义检索 / 读取 / 最近笔记 / 重建索引 / 统计」暴露成 MCP 工具。
配合采集类 skill（采集加工 → 入库 → 索引）形成「skill 负责写入、MCP 负责被调用查询」的闭环。

依赖：pip install mcp        （仅本 server 需要；知识库其它脚本零依赖）
运行：VAULT_DIR=/path/to/vault python3 mcp_server.py
可选：VAULT_INDEX_DB=/path/to/vault_index.sqlite

在 Claude Code / 其它支持 MCP 的 Agent 里这样配置：
    {
      "mcpServers": {
        "chubby-kb": {
          "command": "python3",
          "args": ["<本文件绝对路径>"],
          "env": { "VAULT_DIR": "/path/to/your-vault" }
        }
      }
    }
"""

import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
VAULT_INDEX_PATH = TOOLS_DIR / "vault_index.py"


def load_vault_index():
    if not VAULT_INDEX_PATH.is_file():
        return None, f"missing {VAULT_INDEX_PATH}"
    try:
        spec = importlib.util.spec_from_file_location("chubby_vault_index", VAULT_INDEX_PATH)
        if spec is None or spec.loader is None:
            return None, f"cannot create import spec for {VAULT_INDEX_PATH}"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, ""
    except Exception as exc:
        return None, str(exc)


vault_index, VAULT_INDEX_ERROR = load_vault_index()


VAULT = os.environ.get("VAULT_DIR", "")
MAX_READ_CHARS = 12000
INDEX_DB = os.environ.get("VAULT_INDEX_DB", "")
SEMANTIC_PROVIDER = os.environ.get("CHUBBY_EMBEDDING_PROVIDER", "lite")
SEMANTIC_MODEL = os.environ.get("CHUBBY_EMBEDDING_MODEL", "")


def index_db(vault):
    if INDEX_DB:
        return INDEX_DB
    return str(Path(vault) / ".chubby" / "vault_index.sqlite")


def unavailable(exc):
    return f"索引不可用：{exc}"


def require_vault_index():
    if vault_index is None:
        detail = VAULT_INDEX_ERROR or f"missing {VAULT_INDEX_PATH}"
        raise RuntimeError(
            f"无法加载 tools/vault_index.py（{detail}）。请从完整 chubbyskills 仓库运行 MCP，或保留 tools/vault_index.py。"
        )
    return vault_index


def require_vault_dir(vault):
    if not vault or not os.path.isdir(vault):
        raise RuntimeError("VAULT_DIR 未设置或不是目录")


def ensure_index(vault):
    require_vault_dir(vault)
    indexer = require_vault_index()
    db = index_db(vault)
    if not os.path.exists(db):
        indexer.index_vault(vault, db_path=db)
    return db


def format_notes(rows, empty):
    if not rows:
        return empty
    out = []
    for i, row in enumerate(rows, 1):
        bits = []
        if row.get("platform"):
            bits.append(row["platform"])
        if row.get("tags"):
            bits.append(row["tags"])
        meta = " | ".join(bits)
        out.append(f"{i}. `{row['path']}` — {row.get('title') or row['path']}")
        if meta:
            out.append(f"   {meta}")
        if row.get("snippet"):
            out.append(f"   {row['snippet']}")
    return "\n".join(out)


def search(vault, query, limit=10, platform="", tag=""):
    """按关键词搜索索引，返回匹配笔记的相对路径与片段。"""
    if not query.strip():
        return "请提供搜索关键词。"
    try:
        indexer = require_vault_index()
        db = ensure_index(vault)
        rows = indexer.search(
            db_path=db,
            query=query,
            limit=limit,
            platform=platform or None,
            tag=tag or None,
        )
    except Exception as exc:
        return unavailable(exc)
    return format_notes(rows, f"知识库中未找到与「{query}」相关的笔记。")


def semantic_search(vault, query, limit=10, platform="", tag=""):
    """按 semantic-lite 排序搜索索引，适合概念查询。"""
    if not query.strip():
        return "请提供搜索关键词。"
    try:
        indexer = require_vault_index()
        db = ensure_index(vault)
        rows = indexer.semantic_search(
            db_path=db,
            query=query,
            limit=limit,
            platform=platform or None,
            tag=tag or None,
            provider=SEMANTIC_PROVIDER,
            model=SEMANTIC_MODEL or None,
        )
    except Exception as exc:
        return unavailable(exc)
    return format_notes(rows, f"知识库中未找到与「{query}」语义相关的笔记。")


def read_note(vault, path):
    """读取某篇笔记全文（path 相对 vault 根），过长则截断。"""
    try:
        indexer = require_vault_index()
        require_vault_dir(vault)
        note = indexer.read_note(vault, path, max_chars=MAX_READ_CHARS)
    except RuntimeError as exc:
        return unavailable(exc)
    except Exception as exc:
        return f"笔记不存在或不可读：{path} ({exc})"
    return f"# {path}\n\n{note['text']}"


def list_recent(vault, limit=10, platform=""):
    """列出最近修改的笔记。"""
    try:
        indexer = require_vault_index()
        db = ensure_index(vault)
        rows = indexer.recent(db_path=db, limit=limit, platform=platform or None)
    except Exception as exc:
        return unavailable(exc)
    return format_notes(rows, "知识库为空。")


def reindex(vault):
    try:
        indexer = require_vault_index()
        result = indexer.index_vault(vault, db_path=index_db(vault))
    except Exception as exc:
        return unavailable(exc)
    return f"已索引 {result['notes']} 篇笔记：{result['db']} (fts5={result['fts5']})"


def vault_stats(vault):
    try:
        indexer = require_vault_index()
        db = ensure_index(vault)
        result = indexer.stats(db_path=db)
    except Exception as exc:
        return unavailable(exc)
    lines = [f"共 {result['notes']} 篇笔记。"]
    for platform, count in result["platforms"].items():
        lines.append(f"- {platform}: {count}")
    return "\n".join(lines)


def main():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("chubby-kb")

    @mcp.tool()
    def search_vault(query: str, limit: int = 10, platform: str = "", tag: str = "") -> str:
        """在个人知识库中搜索笔记，可按 platform 或 tag 过滤。"""
        return search(VAULT, query, limit, platform=platform, tag=tag)

    @mcp.tool()
    def semantic_search_vault(query: str, limit: int = 10, platform: str = "", tag: str = "") -> str:
        """在个人知识库中做 semantic-lite 概念检索，可按 platform 或 tag 过滤。"""
        return semantic_search(VAULT, query, limit, platform=platform, tag=tag)

    @mcp.tool()
    def read_kb_note(path: str) -> str:
        """读取知识库中某篇笔记的全文，path 为相对 vault 根的路径。"""
        return read_note(VAULT, path)

    @mcp.tool()
    def list_recent_notes(limit: int = 10, platform: str = "") -> str:
        """列出知识库中最近修改的笔记，可按 platform 过滤。"""
        return list_recent(VAULT, limit, platform=platform)

    @mcp.tool()
    def reindex_vault() -> str:
        """重建知识库 SQLite 索引。"""
        return reindex(VAULT)

    @mcp.tool()
    def vault_index_stats() -> str:
        """查看知识库索引统计。"""
        return vault_stats(VAULT)

    mcp.run()


if __name__ == "__main__":
    if not VAULT or not os.path.isdir(VAULT):
        print("❌ 请设置 VAULT_DIR 环境变量指向你的 vault 根目录", file=sys.stderr)
        sys.exit(1)
    main()
