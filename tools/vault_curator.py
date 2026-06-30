#!/usr/bin/env python3
"""
Curate a local Markdown vault.

This tool handles two zero-dependency workflows:
- archive: move notes from 00_Inbox into 10_Sources/<platform>/ or 20_Processed/
- card: generate a durable knowledge card from one note
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"

try:
    from tools import vault_index
except ModuleNotFoundError:
    sys.path.insert(0, str(TOOLS_DIR))
    import vault_index


def now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def today():
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def yaml_quote(value):
    value = str(value or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{value}"'


def slugify(value, fallback="note"):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or fallback


def rel_to(vault, path):
    return str(Path(path).resolve().relative_to(Path(vault).resolve()))


def unique_path(path):
    path = Path(path)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    idx = 2
    while True:
        candidate = parent / f"{stem}-{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def read_note(vault, path):
    path = vault_index.safe_path(vault, path)
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = vault_index.split_frontmatter(text)
    fields = vault_index.parse_frontmatter(frontmatter)
    return path, fields, body


def upsert_frontmatter_text(text, fields):
    frontmatter, body = vault_index.split_frontmatter(text)
    if frontmatter is None:
        frontmatter = ""
    keys = set(fields)
    kept = []
    for line in frontmatter.splitlines():
        key = line.split(":", 1)[0].strip()
        if key not in keys:
            kept.append(line)
    for key, value in fields.items():
        kept.append(f"{key}: {value}")
    return "---\n" + "\n".join(kept) + "\n---\n\n" + body


def inbox_notes(vault):
    inbox = Path(vault) / "00_Inbox"
    if not inbox.is_dir():
        return []
    return [
        path
        for path in sorted(inbox.rglob("*.md"))
        if path.name.lower() != "readme.md" and ".assets" not in path.parts
    ]


def archive_target(vault, path, fields):
    platform = vault_index.clean_scalar(fields.get("platform", "")) or "unknown"
    summary = vault_index.clean_scalar(fields.get("summary", ""))
    status = vault_index.clean_scalar(fields.get("archive_status", fields.get("status", "")))
    tags = ",".join(vault_index.inline_list_items(fields.get("tags", ""))).lower()
    if summary or status == "processed" or "processed" in tags or "evergreen" in tags:
        base = Path(vault) / "20_Processed"
    else:
        base = Path(vault) / "10_Sources" / slugify(platform, "unknown")
    return unique_path(base / path.name)


def move_assets(source, target, dry_run=True):
    source_assets = source.with_name(source.stem + ".assets")
    if not source_assets.is_dir():
        return ""
    target_assets = unique_path(target.with_name(target.stem + ".assets"))
    if not dry_run:
        target_assets.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_assets), str(target_assets))
    return str(target_assets)


def archive_vault(vault, dry_run=True, limit=0):
    vault = Path(vault).expanduser().resolve()
    if not vault.is_dir():
        raise FileNotFoundError(f"vault not found: {vault}")
    actions = []
    for path in inbox_notes(vault):
        _, fields, _ = read_note(vault, rel_to(vault, path))
        target = archive_target(vault, path, fields)
        action = {
            "source": rel_to(vault, path),
            "target": rel_to(vault, target),
            "status": "planned" if dry_run else "moved",
        }
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            text = path.read_text(encoding="utf-8", errors="replace")
            text = upsert_frontmatter_text(
                text,
                {
                    "archived_at": yaml_quote(now_iso()),
                    "archived_from": yaml_quote(action["source"]),
                },
            )
            path.write_text(text, encoding="utf-8")
            moved_assets = move_assets(path, target, dry_run=False)
            shutil.move(str(path), str(target))
            if moved_assets:
                action["assets"] = rel_to(vault, moved_assets)
        actions.append(action)
        if limit and len(actions) >= limit:
            break
    return actions


def first_paragraph(body):
    for chunk in re.split(r"\n\s*\n", body):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        lines = [line for line in lines if not line.startswith("#") and not line.startswith("```")]
        if lines:
            return " ".join(lines)[:280]
    return ""


def extract_key_points(body, limit=5):
    points = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            points.append(stripped[2:].strip())
        if len(points) >= limit:
            return points
    sentences = re.split(r"[。.!?]\s*", re.sub(r"\s+", " ", body))
    for sentence in sentences:
        sentence = sentence.strip(" #>-")
        if len(sentence) >= 8:
            points.append(sentence[:160])
        if len(points) >= limit:
            break
    return points


def card_markdown(source_path, fields, body):
    title = fields.get("title") or Path(source_path).stem
    summary = fields.get("summary") or first_paragraph(body)
    tags = vault_index.inline_list_items(fields.get("tags", ""))
    tag_text = ", ".join(["knowledge-card"] + tags)
    points = extract_key_points(body)
    lines = [
        "---",
        f"title: {yaml_quote('Card - ' + title)}",
        "type: knowledge_card",
        f"source_note: {yaml_quote(source_path)}",
        f"platform: {fields.get('platform', 'content') or 'content'}",
        f"source: {yaml_quote(fields.get('source', source_path))}",
        f"created: {today()}",
        f"tags: [{tag_text}]",
        "---",
        "",
        f"# Card - {title}",
        "",
        "## Summary",
        "",
        summary or "待补充。",
        "",
        "## Key Points",
        "",
    ]
    lines.extend(f"- {point}" for point in points)
    if not points:
        lines.append("- 待补充。")
    lines.extend(["", "## Source", "", f"- [[{source_path}]]", ""])
    return "\n".join(lines)


def generate_card(vault, rel_path, output_dir=None, dry_run=True):
    vault = Path(vault).expanduser().resolve()
    source, fields, body = read_note(vault, rel_path)
    title = fields.get("title") or source.stem
    base = vault_index.safe_path(vault, output_dir) if output_dir else vault / "20_Processed" / "Cards"
    target = unique_path(base / f"{slugify(title)}.md")
    text = card_markdown(rel_to(vault, source), fields, body)
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return {
        "source": rel_to(vault, source),
        "target": rel_to(vault, target),
        "status": "planned" if dry_run else "written",
        "preview": text if dry_run else "",
    }


def print_actions(actions):
    if isinstance(actions, dict):
        actions = [actions]
    if not actions:
        print("No actions.")
        return
    for action in actions:
        print(f"{action['status']}: {action['source']} -> {action['target']}")


def build_parser():
    parser = argparse.ArgumentParser(description="Archive vault notes and generate knowledge cards")
    sub = parser.add_subparsers(dest="command", required=True)

    archive_cmd = sub.add_parser("archive", help="Archive notes from 00_Inbox")
    archive_cmd.add_argument("vault", help="Vault root")
    archive_cmd.add_argument("--apply", action="store_true", help="Move files; default is dry-run")
    archive_cmd.add_argument("--limit", type=int, default=0)
    archive_cmd.add_argument("--json", action="store_true")

    card_cmd = sub.add_parser("card", help="Generate a knowledge card from one note")
    card_cmd.add_argument("vault", help="Vault root")
    card_cmd.add_argument("path", help="Note path relative to vault")
    card_cmd.add_argument("--output-dir", help="Output directory relative to vault")
    card_cmd.add_argument("--apply", action="store_true", help="Write card; default is dry-run")
    card_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "archive":
            actions = archive_vault(args.vault, dry_run=not args.apply, limit=args.limit)
        elif args.command == "card":
            actions = generate_card(args.vault, args.path, output_dir=args.output_dir, dry_run=not args.apply)
        else:
            raise ValueError(f"unknown command: {args.command}")
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"actions": actions}, ensure_ascii=False, indent=2))
    else:
        print_actions(actions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
