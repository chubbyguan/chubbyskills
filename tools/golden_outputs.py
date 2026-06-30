#!/usr/bin/env python3
"""Create and verify reproducible golden snapshots for Markdown outputs."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
DEFAULT_GOLDEN = ROOT / "fixtures" / "golden" / "examples_outputs.json"

try:
    from tools import validate_outputs
except ModuleNotFoundError:
    sys.path.insert(0, str(TOOLS_DIR))
    import validate_outputs


SNAPSHOT_FIELDS = (
    "title",
    "type",
    "platform",
    "source",
    "created",
    "schema_version",
    "content_type",
    "status",
    "assets",
)


def normalize_body(body):
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"[ \t]+$", "", body, flags=re.MULTILINE)
    return body.strip() + "\n"


def body_headings(body):
    return [match.group(1).strip() for match in re.finditer(r"^#+\s+(.+)$", body, re.MULTILINE)]


def rel_path(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def snapshot_file(path, allowed_platforms=None):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    frontmatter, body = validate_outputs.split_frontmatter(text)
    if frontmatter is None:
        raise ValueError(f"missing YAML frontmatter: {path}")
    fields = validate_outputs.parse_frontmatter(frontmatter)
    errors = [
        problem["message"]
        for problem in validate_outputs.validate_file(
            str(path),
            require_schema_v1=True,
            allowed_platforms=allowed_platforms,
        )
        if problem["level"] == "error"
    ]
    if errors:
        raise ValueError(f"{path}: {'; '.join(errors)}")
    normalized = normalize_body(body)
    return {
        "path": rel_path(path),
        "fields": {key: validate_outputs.clean_scalar(fields.get(key, "")) for key in SNAPSHOT_FIELDS},
        "headings": body_headings(body),
        "body_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }


def build_snapshot(paths, platform_dir=None):
    files = sorted(set(validate_outputs.iter_markdown([str(path) for path in paths])))
    platform_set = validate_outputs.known_platforms(platform_dir)
    return {
        "schema": "chubbyskills.golden_outputs.v1",
        "files": [snapshot_file(path, allowed_platforms=platform_set) for path in files],
    }


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_snapshots(actual, expected):
    if actual == expected:
        return []
    problems = []
    actual_by_path = {item["path"]: item for item in actual.get("files", [])}
    expected_by_path = {item["path"]: item for item in expected.get("files", [])}
    for path in sorted(set(expected_by_path) - set(actual_by_path)):
        problems.append(f"missing output: {path}")
    for path in sorted(set(actual_by_path) - set(expected_by_path)):
        problems.append(f"unexpected output: {path}")
    for path in sorted(set(actual_by_path) & set(expected_by_path)):
        if actual_by_path[path] != expected_by_path[path]:
            problems.append(f"changed output: {path}")
    if actual.get("schema") != expected.get("schema"):
        problems.append("snapshot schema changed")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify reproducible golden Markdown outputs")
    parser.add_argument("paths", nargs="+", help="Markdown files or directories")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    parser.add_argument("--platform-dir", help="Directory with platform YAML files")
    parser.add_argument("--write", action="store_true", help="Write or refresh the golden snapshot")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        actual = build_snapshot(args.paths, platform_dir=args.platform_dir)
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    golden_path = Path(args.golden)
    if args.write:
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {golden_path}")
        return 0

    if not golden_path.exists():
        print(f"❌ missing golden snapshot: {golden_path}", file=sys.stderr)
        return 1

    expected = load_json(golden_path)
    problems = compare_snapshots(actual, expected)
    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems, "actual": actual}, ensure_ascii=False, indent=2))
    elif problems:
        for problem in problems:
            print(f"❌ {problem}")
    else:
        print(f"✅ Golden outputs match {golden_path}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
