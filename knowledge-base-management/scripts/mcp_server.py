#!/usr/bin/env python3
"""
知识库 MCP Server —— 让任何 Agent 都能检索你的 Obsidian 知识库

把本地 vault 的「搜索 / 读取 / 最近笔记」暴露成 MCP 工具。配合采集类 skill
（采集加工 → 入库）形成「skill 负责写入、MCP 负责被调用查询」的闭环。

依赖：pip install mcp        （仅本 server 需要；知识库其它脚本零依赖）
运行：VAULT_DIR=/path/to/vault python3 mcp_server.py

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

import os
import sys
from datetime import datetime


VAULT = os.environ.get("VAULT_DIR", "")
MAX_READ_CHARS = 12000
SNIPPET_CTX = 80


def _iter_md(vault):
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                yield os.path.join(root, f)


def _safe_path(vault, rel):
    """把相对路径解析到 vault 内，拒绝越界（路径穿越防护）。"""
    full = os.path.realpath(os.path.join(vault, rel))
    if not full.startswith(os.path.realpath(vault) + os.sep):
        raise ValueError("路径越界，拒绝访问")
    return full


def _snippet(text, q):
    i = text.lower().find(q.lower())
    if i == -1:
        return ""
    start = max(0, i - SNIPPET_CTX)
    end = min(len(text), i + len(q) + SNIPPET_CTX)
    s = text[start:end].replace("\n", " ").strip()
    return ("…" if start > 0 else "") + s + ("…" if end < len(text) else "")


def search(vault, query, limit=10):
    """按关键词搜文件名+正文，返回匹配笔记的相对路径与片段。"""
    if not query.strip():
        return "请提供搜索关键词。"
    q = query.lower()
    hits = []
    for path in _iter_md(vault):
        rel = os.path.relpath(path, vault)
        name_hit = q in os.path.basename(path).lower()
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except Exception:
            text = ""
        if name_hit or q in text.lower():
            hits.append((rel, _snippet(text, query) or "(命中标题)"))
        if len(hits) >= limit:
            break
    if not hits:
        return f"知识库中未找到与「{query}」相关的笔记。"
    out = [f"找到 {len(hits)} 条与「{query}」相关的笔记：\n"]
    for i, (rel, snip) in enumerate(hits, 1):
        out.append(f"{i}. `{rel}`\n   {snip}")
    return "\n".join(out)


def read_note(vault, path):
    """读取某篇笔记全文（path 相对 vault 根），过长则截断。"""
    full = _safe_path(vault, path)
    if not os.path.isfile(full):
        return f"笔记不存在：{path}"
    text = open(full, encoding="utf-8", errors="replace").read()
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n\n…（已截断，全文共 {len(text)} 字）"
    return f"# {path}\n\n{text}"


def list_recent(vault, limit=10):
    """列出最近修改的笔记。"""
    items = []
    for path in _iter_md(vault):
        try:
            items.append((os.path.getmtime(path), os.path.relpath(path, vault)))
        except Exception:
            continue
    items.sort(reverse=True)
    if not items:
        return "知识库为空。"
    out = [f"最近 {min(limit, len(items))} 篇笔记：\n"]
    for mtime, rel in items[:limit]:
        day = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        out.append(f"- `{rel}`  ({day})")
    return "\n".join(out)


def main():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("chubby-kb")

    @mcp.tool()
    def search_vault(query: str, limit: int = 10) -> str:
        """在个人知识库中按关键词搜索笔记，返回匹配的相对路径与上下文片段。"""
        return search(VAULT, query, limit)

    @mcp.tool()
    def read_kb_note(path: str) -> str:
        """读取知识库中某篇笔记的全文，path 为相对 vault 根的路径。"""
        return read_note(VAULT, path)

    @mcp.tool()
    def list_recent_notes(limit: int = 10) -> str:
        """列出知识库中最近修改的笔记。"""
        return list_recent(VAULT, limit)

    mcp.run()


if __name__ == "__main__":
    if not VAULT or not os.path.isdir(VAULT):
        print("❌ 请设置 VAULT_DIR 环境变量指向你的 vault 根目录", file=sys.stderr)
        sys.exit(1)
    main()
