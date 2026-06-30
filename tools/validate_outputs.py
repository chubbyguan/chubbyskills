#!/usr/bin/env python3
"""
Validate Markdown files produced by chubbyskills.

The validator is intentionally dependency-free so it can run in CI and inside a
freshly cloned repo. It checks the shared contract that downstream tools rely on:
frontmatter exists, required keys are present, platform is known, and dates are
machine-readable.

Usage:
    python3 tools/validate_outputs.py examples/outputs
    python3 tools/validate_outputs.py path/to/note.md --json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime


REQUIRED_KEYS = ("title", "type", "platform", "source", "created")
SCHEMA_V1_REQUIRED_KEYS = (
    "schema_version",
    "run_id",
    "source_hash",
    "captured_at",
    "processed_at",
    "content_type",
    "status",
    "assets",
)
VALID_STATUSES = {"success", "failed", "dry_run"}
KNOWN_PLATFORMS = {
    "bilibili",
    "content",
    "douyin",
    "industry-intelligence",
    "knowledge-base",
    "learning",
    "podcast",
    "tiktok",
    "wechat",
    "weibo",
    "x",
    "xiaohongshu",
    "youtube",
    "zhihu",
}


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 4 :].lstrip("\n")


def parse_frontmatter(block):
    data = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            data[match.group(1)] = match.group(2).strip()
    return data


def clean_scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def validate_created(value):
    value = clean_scalar(value)
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_iso_datetime(value):
    value = clean_scalar(value)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def is_inline_list(value):
    value = clean_scalar(value)
    return value.startswith("[") and value.endswith("]")


def validate_file(path, require_schema_v1=False):
    problems = []
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    frontmatter, body = split_frontmatter(text)
    if frontmatter is None:
        return [{"level": "error", "message": "missing YAML frontmatter"}]

    fields = parse_frontmatter(frontmatter)
    for key in REQUIRED_KEYS:
        if key not in fields or not clean_scalar(fields[key]):
            problems.append({"level": "error", "message": f"missing required field: {key}"})

    platform = clean_scalar(fields.get("platform", ""))
    if platform and platform not in KNOWN_PLATFORMS:
        problems.append({"level": "error", "message": f"unknown platform: {platform}"})

    created = fields.get("created", "")
    if created and not validate_created(created):
        problems.append({"level": "error", "message": f"created must be YYYY-MM-DD: {created}"})

    schema_version = clean_scalar(fields.get("schema_version", ""))
    should_validate_schema_v1 = require_schema_v1 or bool(schema_version)
    if require_schema_v1 and schema_version != "1":
        problems.append({"level": "error", "message": "schema_version must be 1"})
    if schema_version and schema_version != "1":
        problems.append({"level": "error", "message": f"unsupported schema_version: {schema_version}"})

    if should_validate_schema_v1 and schema_version == "1":
        for key in SCHEMA_V1_REQUIRED_KEYS:
            if key not in fields or not clean_scalar(fields[key]):
                problems.append({"level": "error", "message": f"missing schema v1 field: {key}"})

        for key in ("captured_at", "processed_at"):
            value = fields.get(key, "")
            if value and not validate_iso_datetime(value):
                problems.append({"level": "error", "message": f"{key} must be ISO datetime: {value}"})

        status = clean_scalar(fields.get("status", ""))
        if status and status not in VALID_STATUSES:
            problems.append({"level": "error", "message": f"invalid status: {status}"})

        source_hash = clean_scalar(fields.get("source_hash", ""))
        if source_hash and not re.match(r"^[0-9a-f]{12,64}$", source_hash):
            problems.append({"level": "error", "message": "source_hash should be lowercase hex"})

        assets = clean_scalar(fields.get("assets", ""))
        if assets and not is_inline_list(assets):
            problems.append({"level": "error", "message": "assets should use inline list form"})

    tags = fields.get("tags")
    if tags and not is_inline_list(tags):
        problems.append({"level": "warning", "message": "tags should use inline list form, e.g. [B站]"})

    if not re.search(r"^#\s+\S+", body, re.MULTILINE):
        problems.append({"level": "warning", "message": "body should contain a top-level # heading"})

    return problems


def iter_markdown(paths):
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".") and d != "__pycache__" and not d.endswith(".assets")
                ]
                for name in files:
                    if name.endswith(".md"):
                        yield os.path.join(root, name)
        elif path.endswith(".md"):
            yield path


def main():
    parser = argparse.ArgumentParser(description="Validate chubbyskills Markdown outputs")
    parser.add_argument("paths", nargs="+", help="Markdown files or directories")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--schema-v1", action="store_true", help="Require pipeline schema v1 fields")
    args = parser.parse_args()

    files = sorted(set(iter_markdown(args.paths)))
    results = []
    error_count = 0
    warning_count = 0

    for path in files:
        problems = validate_file(path, require_schema_v1=args.schema_v1)
        for problem in problems:
            if problem["level"] == "error":
                error_count += 1
            else:
                warning_count += 1
        results.append({"path": path, "problems": problems})

    if args.json:
        print(json.dumps({"files": results}, ensure_ascii=False, indent=2))
    else:
        if not files:
            print("No Markdown files found.", file=sys.stderr)
        for item in results:
            if not item["problems"]:
                print(f"✅ {item['path']}")
                continue
            for problem in item["problems"]:
                mark = "❌" if problem["level"] == "error" else "⚠️ "
                print(f"{mark} {item['path']}: {problem['message']}")
        print(f"\nChecked {len(files)} file(s): {error_count} error(s), {warning_count} warning(s)")

    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
