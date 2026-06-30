#!/usr/bin/env python3
"""
Scaffold contributor platform adapters.

The scaffold creates the four files a new platform needs before deeper fetch
logic is implemented:
- platforms/<id>.yaml
- templates/sites/<id>.yaml
- <skill>/SKILL.md
- <skill>/<script>
"""

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALID_ID = re.compile(r"^[a-z][a-z0-9-]*$")


def inline_list(values):
    return "[" + ", ".join(value for value in values if value) + "]"


def split_values(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_platform_id(platform_id):
    if not VALID_ID.match(platform_id):
        raise ValueError("platform id must match ^[a-z][a-z0-9-]*$")


def write_file(path, text, force=False):
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"file exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def platform_yaml(args):
    return "\n".join(
        [
            f"id: {args.id}",
            f"name: {args.name}",
            f"skill: {args.skill}",
            f"script: {args.script}",
            f"category: {args.category}",
            f"status: {args.status}",
            f"source_types: {inline_list(split_values(args.source_types))}",
            f"required_deps: {inline_list(split_values(args.required_deps))}",
            f"optional_deps: {inline_list(split_values(args.optional_deps))}",
            "output_contract: markdown_schema_v1",
            f"fallback: {args.fallback}",
            f"sample_source: {args.sample_source}",
            f"notes: {args.notes}",
            "",
        ]
    )


def template_yaml(args):
    frontmatter = ["title", "type", "platform", "source", "created", "schema_version", "run_id", "source_hash"]
    postprocess = ["normalize_markdown", "validate_schema_v1"]
    return "\n".join(
        [
            f"id: {args.id}",
            f"platform: {args.id}",
            f"name: {args.name} site template",
            f"match: {inline_list(split_values(args.match))}",
            f"frontmatter: {inline_list(frontmatter)}",
            "assets: sidecar_assets",
            f"postprocess: {inline_list(postprocess)}",
            "",
        ]
    )


def skill_markdown(args):
    return "\n".join(
        [
            f"# {args.name}",
            "",
            f"{args.name} adapter scaffold for chubbyskills.",
            "",
            "## Usage",
            "",
            "```bash",
            f"python3 {args.skill}/{args.script} \"{args.sample_source}\" --output output",
            "```",
            "",
            "## Output Contract",
            "",
            "The script should write Markdown with shared frontmatter fields and schema v1 metadata.",
            "",
        ]
    )


def script_stub(args):
    return f'''#!/usr/bin/env python3
"""Minimal {args.name} adapter stub."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="{args.name} adapter stub")
    parser.add_argument("source")
    parser.add_argument("--output", "-o", default="output")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "{args.id}-sample.md"
    path.write_text(
        "---\\n"
        "title: {args.name} sample\\n"
        "type: note\\n"
        "platform: {args.id}\\n"
        f"source: {{args.source}}\\n"
        "created: 2026-06-30\\n"
        "schema_version: 1\\n"
        "run_id: adapter-sample\\n"
        "source_hash: 000000000000\\n"
        "captured_at: \\"2026-06-30T00:00:00+00:00\\"\\n"
        "processed_at: \\"2026-06-30T00:00:00+00:00\\"\\n"
        "content_type: note\\n"
        "status: success\\n"
        "assets: []\\n"
        "---\\n\\n"
        "# {args.name} sample\\n\\n"
        "Replace this stub with real fetch logic.\\n",
        encoding="utf-8",
    )
    print(path)


if __name__ == "__main__":
    main()
'''


def default_args(args):
    if not args.skill:
        args.skill = f"{args.id}-ingest"
    if not args.script:
        args.script = f"scripts/fetch_{args.id.replace('-', '_')}.py"
    if not args.match:
        args.match = args.sample_source.split("//", 1)[-1].split("/", 1)[0]
    return args


def scaffold_platform(args, repo_root=ROOT):
    args = default_args(args)
    validate_platform_id(args.id)
    repo_root = Path(repo_root)
    files = [
        write_file(repo_root / "platforms" / f"{args.id}.yaml", platform_yaml(args), force=args.force),
        write_file(repo_root / "templates" / "sites" / f"{args.id}.yaml", template_yaml(args), force=args.force),
        write_file(repo_root / args.skill / "SKILL.md", skill_markdown(args), force=args.force),
        write_file(repo_root / args.skill / args.script, script_stub(args), force=args.force),
    ]
    return [str(path) for path in files]


def build_parser():
    parser = argparse.ArgumentParser(description="Scaffold a new platform adapter")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="Create platform definition, site template, and skill stub")
    new.add_argument("id", help="Machine id, e.g. hacker-news")
    new.add_argument("--name", required=True)
    new.add_argument("--skill")
    new.add_argument("--script")
    new.add_argument("--category", default="article")
    new.add_argument("--status", default="experimental")
    new.add_argument("--source-types", default="article")
    new.add_argument("--required-deps", default="")
    new.add_argument("--optional-deps", default="")
    new.add_argument("--fallback", default="manual")
    new.add_argument("--sample-source", required=True)
    new.add_argument("--match", default="")
    new.add_argument("--notes", default="Contributor scaffold; replace stub fetch logic before marking stable.")
    new.add_argument("--force", action="store_true")
    new.add_argument("--json", action="store_true")
    new.add_argument("--repo-root", default=str(ROOT), help="Repository root to write into")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            files = scaffold_platform(args, repo_root=args.repo_root)
        else:
            raise ValueError(f"unknown command: {args.command}")
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"files": files}, ensure_ascii=False, indent=2))
    else:
        for path in files:
            print(path)
        print("Next: python3 tools/platform_health.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
