#!/usr/bin/env python3
"""
Local Markdown vault index for chubbyskills.

The indexer stores normalized frontmatter and note bodies in SQLite. It creates
an FTS5 table when available, and the search path falls back to LIKE matching so
Chinese notes still work on default SQLite tokenizers.
"""

import argparse
import math
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / ".chubby" / "vault_index.sqlite"
MAX_READ_CHARS = 12000
SNIPPET_CTX = 80
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 4 :].lstrip("\n")


def clean_scalar(value):
    value = str(value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def parse_frontmatter(block):
    data = {}
    if not block:
        return data
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            data[match.group(1)] = clean_scalar(match.group(2))
    return data


def inline_list_items(value):
    value = clean_scalar(value)
    if not value.startswith("[") or not value.endswith("]"):
        return [value] if value else []
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [clean_scalar(item) for item in inner.split(",") if clean_scalar(item)]


def iter_markdown(vault):
    vault = Path(vault)
    for root, dirs, files in os.walk(vault):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and d != "__pycache__" and not d.endswith(".assets")
        ]
        for name in files:
            if name.endswith(".md"):
                yield Path(root) / name


def safe_path(vault, rel_path):
    vault_real = Path(vault).resolve()
    full = (vault_real / rel_path).resolve()
    if full != vault_real and vault_real not in full.parents:
        raise ValueError("path escapes vault")
    return full


def note_record(vault, path):
    vault = Path(vault)
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    fields = parse_frontmatter(frontmatter)
    stat = path.stat()
    rel = str(path.relative_to(vault))
    title = fields.get("title") or path.stem
    tags = inline_list_items(fields.get("tags", "")) + inline_list_items(fields.get("auto_tags", ""))
    return {
        "path": rel,
        "title": title,
        "platform": fields.get("platform", ""),
        "source": fields.get("source", ""),
        "author": fields.get("author", ""),
        "created": fields.get("created", ""),
        "content_type": fields.get("content_type", fields.get("type", "")),
        "tags": ", ".join(dict.fromkeys(tags)),
        "summary": fields.get("summary", ""),
        "modified": stat.st_mtime,
        "size": stat.st_size,
        "body": body,
    }


def connect(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def require_db(db_path):
    if not Path(db_path).exists():
        raise FileNotFoundError(f"index not found: {db_path}. Run `python3 tools/vault_index.py index <vault>` first.")


def has_fts5(conn):
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts_probe")
        return True
    except sqlite3.DatabaseError:
        return False


def reset_schema(conn):
    conn.execute("DROP TABLE IF EXISTS notes_fts")
    conn.execute("DROP TABLE IF EXISTS notes")
    conn.execute(
        """
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT,
            platform TEXT,
            source TEXT,
            author TEXT,
            created TEXT,
            content_type TEXT,
            tags TEXT,
            summary TEXT,
            modified REAL,
            size INTEGER,
            body TEXT
        )
        """
    )
    if has_fts5(conn):
        conn.execute("CREATE VIRTUAL TABLE notes_fts USING fts5(path UNINDEXED, title, tags, body)")
        return True
    return False


def index_vault(vault, db_path=DEFAULT_DB):
    vault = Path(vault).expanduser().resolve()
    if not vault.is_dir():
        raise FileNotFoundError(f"vault not found: {vault}")
    conn = connect(db_path)
    try:
        fts_enabled = reset_schema(conn)
        records = [note_record(vault, path) for path in sorted(iter_markdown(vault))]
        for record in records:
            conn.execute(
                """
                INSERT INTO notes (
                    path, title, platform, source, author, created, content_type,
                    tags, summary, modified, size, body
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["path"],
                    record["title"],
                    record["platform"],
                    record["source"],
                    record["author"],
                    record["created"],
                    record["content_type"],
                    record["tags"],
                    record["summary"],
                    record["modified"],
                    record["size"],
                    record["body"],
                ),
            )
            if fts_enabled:
                conn.execute(
                    "INSERT INTO notes_fts(path, title, tags, body) VALUES (?, ?, ?, ?)",
                    (record["path"], record["title"], record["tags"], record["body"]),
                )
        conn.commit()
        return {"vault": str(vault), "db": str(Path(db_path)), "notes": len(records), "fts5": fts_enabled}
    finally:
        conn.close()


def snippet(text, query):
    if not query:
        return ""
    lower = text.lower()
    needle = query.lower()
    idx = lower.find(needle)
    if idx == -1:
        return text[: SNIPPET_CTX * 2].replace("\n", " ").strip()
    start = max(0, idx - SNIPPET_CTX)
    end = min(len(text), idx + len(query) + SNIPPET_CTX)
    value = text[start:end].replace("\n", " ").strip()
    return ("..." if start else "") + value + ("..." if end < len(text) else "")


def semantic_terms(text):
    text = str(text or "").lower()
    terms = WORD_RE.findall(text)
    for block in CJK_RE.findall(text):
        terms.append(block)
        if len(block) > 1:
            terms.extend(block[i : i + 2] for i in range(len(block) - 1))
        if len(block) > 2:
            terms.extend(block[i : i + 3] for i in range(len(block) - 2))
    return [term for term in terms if term]


def semantic_vector(*parts):
    return Counter(term for part in parts for term in semantic_terms(part))


def cosine_score(query_vector, doc_vector):
    if not query_vector or not doc_vector:
        return 0.0
    overlap = set(query_vector) & set(doc_vector)
    dot = sum(query_vector[term] * doc_vector[term] for term in overlap)
    if not dot:
        return 0.0
    q_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    d_norm = math.sqrt(sum(value * value for value in doc_vector.values()))
    return dot / (q_norm * d_norm)


def semantic_search(db_path=DEFAULT_DB, query="", limit=10, platform=None, tag=None):
    require_db(db_path)
    query_vector = semantic_vector(query)
    if not query_vector:
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        params = []
        where = []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if tag:
            where.append("LOWER(tags) LIKE ?")
            params.append(f"%{tag.lower()}%")
        sql = "SELECT path, title, platform, tags, summary, modified, body FROM notes"
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = []
        for row in conn.execute(sql, params).fetchall():
            doc_vector = semantic_vector(
                row[1],
                row[3],
                row[4],
                row[6],
                row[1],
                row[1],
                row[3],
            )
            score = cosine_score(query_vector, doc_vector)
            lower_blob = " ".join(str(part or "").lower() for part in (row[1], row[3], row[4], row[6]))
            if query.lower() in lower_blob:
                score += 0.15
            if score <= 0:
                continue
            rows.append(
                {
                    "path": row[0],
                    "title": row[1],
                    "platform": row[2],
                    "tags": row[3],
                    "summary": row[4],
                    "modified": row[5],
                    "snippet": snippet(row[6] or row[4] or "", query),
                    "score": round(score, 4),
                }
            )
        rows.sort(key=lambda item: (item["score"], item.get("modified") or 0), reverse=True)
        return rows[:limit]
    finally:
        conn.close()


def like_query(conn, query, limit=10, platform=None, tag=None):
    params = []
    where = []
    if query:
        where.append("(LOWER(title) LIKE ? OR LOWER(body) LIKE ? OR LOWER(tags) LIKE ?)")
        q = f"%{query.lower()}%"
        params.extend([q, q, q])
    if platform:
        where.append("platform = ?")
        params.append(platform)
    if tag:
        where.append("LOWER(tags) LIKE ?")
        params.append(f"%{tag.lower()}%")
    sql = "SELECT path, title, platform, tags, modified, body FROM notes"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY modified DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "path": row[0],
            "title": row[1],
            "platform": row[2],
            "tags": row[3],
            "modified": row[4],
            "snippet": snippet(row[5] or "", query),
        }
        for row in rows
    ]


def fts_query(conn, query, limit=10, platform=None, tag=None):
    if not query:
        return []
    phrase = '"' + query.replace('"', '""') + '"'
    params = [phrase]
    where = ["notes_fts MATCH ?"]
    if platform:
        where.append("notes.platform = ?")
        params.append(platform)
    if tag:
        where.append("LOWER(notes.tags) LIKE ?")
        params.append(f"%{tag.lower()}%")
    sql = (
        "SELECT notes.path, notes.title, notes.platform, notes.tags, notes.modified, notes.body "
        "FROM notes_fts JOIN notes ON notes_fts.path = notes.path "
        "WHERE " + " AND ".join(where) + " ORDER BY notes.modified DESC LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "path": row[0],
            "title": row[1],
            "platform": row[2],
            "tags": row[3],
            "modified": row[4],
            "snippet": snippet(row[5] or "", query),
        }
        for row in rows
    ]


def search(db_path=DEFAULT_DB, query="", limit=10, platform=None, tag=None):
    require_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = []
        try:
            rows = fts_query(conn, query, limit=limit, platform=platform, tag=tag)
        except sqlite3.DatabaseError:
            rows = []
        if not rows:
            rows = like_query(conn, query, limit=limit, platform=platform, tag=tag)
        return rows
    finally:
        conn.close()


def recent(db_path=DEFAULT_DB, limit=10, platform=None):
    require_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        params = []
        sql = "SELECT path, title, platform, tags, modified FROM notes"
        if platform:
            sql += " WHERE platform = ?"
            params.append(platform)
        sql += " ORDER BY modified DESC LIMIT ?"
        params.append(limit)
        return [
            {"path": row[0], "title": row[1], "platform": row[2], "tags": row[3], "modified": row[4]}
            for row in conn.execute(sql, params).fetchall()
        ]
    finally:
        conn.close()


def stats(db_path=DEFAULT_DB):
    require_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        total = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        by_platform = conn.execute(
            "SELECT COALESCE(NULLIF(platform, ''), 'unknown'), COUNT(*) FROM notes GROUP BY platform ORDER BY 2 DESC"
        ).fetchall()
        return {"notes": total, "platforms": dict(by_platform)}
    finally:
        conn.close()


def read_note(vault, rel_path, max_chars=MAX_READ_CHARS):
    full = safe_path(vault, rel_path)
    if not full.is_file():
        raise FileNotFoundError(f"note not found: {rel_path}")
    text = full.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + f"\n\n... truncated, full length {len(text)} chars"
    return {"path": rel_path, "text": text, "truncated": truncated}


def print_rows(rows):
    if not rows:
        print("No notes found.")
        return
    for idx, row in enumerate(rows, 1):
        day = datetime.fromtimestamp(row["modified"]).strftime("%Y-%m-%d") if row.get("modified") else "-"
        score = f" score={row['score']}" if "score" in row else ""
        print(f"{idx}. {row.get('title') or row['path']} [{row.get('platform') or '-'}] {day}{score}")
        print(f"   {row['path']}")
        if row.get("snippet"):
            print(f"   {row['snippet']}")


def default_vault(value):
    vault = value or os.environ.get("VAULT_DIR")
    if not vault:
        raise SystemExit("Provide a vault path or set VAULT_DIR.")
    return vault


def build_parser():
    parser = argparse.ArgumentParser(description="Index and search a local Markdown vault")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite index path")
    sub = parser.add_subparsers(dest="command", required=True)

    index_cmd = sub.add_parser("index", help="Build or rebuild the vault index")
    index_cmd.add_argument("vault", nargs="?", help="Vault directory, defaults to VAULT_DIR")
    index_cmd.add_argument("--json", action="store_true", help="Print JSON")

    search_cmd = sub.add_parser("search", help="Search indexed notes")
    search_cmd.add_argument("query", help="Search query")
    search_cmd.add_argument("--limit", type=int, default=10)
    search_cmd.add_argument("--platform")
    search_cmd.add_argument("--tag")
    search_cmd.add_argument("--json", action="store_true")

    semantic_cmd = sub.add_parser("semantic", help="Semantic-lite search over indexed notes")
    semantic_cmd.add_argument("query", help="Search query")
    semantic_cmd.add_argument("--limit", type=int, default=10)
    semantic_cmd.add_argument("--platform")
    semantic_cmd.add_argument("--tag")
    semantic_cmd.add_argument("--json", action="store_true")

    recent_cmd = sub.add_parser("recent", help="List recent notes")
    recent_cmd.add_argument("--limit", type=int, default=10)
    recent_cmd.add_argument("--platform")
    recent_cmd.add_argument("--json", action="store_true")

    read_cmd = sub.add_parser("read", help="Read a note from the vault")
    read_cmd.add_argument("path", help="Note path relative to the vault")
    read_cmd.add_argument("--vault", help="Vault directory, defaults to VAULT_DIR")
    read_cmd.add_argument("--json", action="store_true")

    stats_cmd = sub.add_parser("stats", help="Print index stats")
    stats_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db).expanduser()

    try:
        return run_command(args, db_path)
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


def run_command(args, db_path):
    if args.command == "index":
        result = index_vault(default_vault(args.vault), db_path=db_path)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Indexed {result['notes']} note(s) into {result['db']} (fts5={result['fts5']})")
        return 0

    if args.command == "search":
        rows = search(db_path=db_path, query=args.query, limit=args.limit, platform=args.platform, tag=args.tag)
        if args.json:
            print(json.dumps({"notes": rows}, ensure_ascii=False, indent=2))
        else:
            print_rows(rows)
        return 0

    if args.command == "semantic":
        rows = semantic_search(db_path=db_path, query=args.query, limit=args.limit, platform=args.platform, tag=args.tag)
        if args.json:
            print(json.dumps({"notes": rows}, ensure_ascii=False, indent=2))
        else:
            print_rows(rows)
        return 0

    if args.command == "recent":
        rows = recent(db_path=db_path, limit=args.limit, platform=args.platform)
        if args.json:
            print(json.dumps({"notes": rows}, ensure_ascii=False, indent=2))
        else:
            print_rows(rows)
        return 0

    if args.command == "read":
        result = read_note(default_vault(args.vault), args.path)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["text"])
        return 0

    if args.command == "stats":
        result = stats(db_path=db_path)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Notes: {result['notes']}")
            for platform, count in result["platforms"].items():
                print(f"- {platform}: {count}")
        return 0

    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
