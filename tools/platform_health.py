#!/usr/bin/env python3
"""
Generate and validate the chubbyskills platform health matrix.

Platform definitions live in platforms/*.yaml. Site templates live in
templates/sites/*.yaml. The parser intentionally supports only the small YAML
subset used by this repository: top-level key/value pairs and inline lists.
"""

import argparse
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLATFORM_DIR = ROOT / "platforms"
DEFAULT_TEMPLATE_DIR = ROOT / "templates" / "sites"
DEFAULT_OUTPUT = ROOT / "docs" / "platform-status.md"

REQUIRED_PLATFORM_FIELDS = (
    "id",
    "name",
    "skill",
    "script",
    "category",
    "status",
    "source_types",
    "output_contract",
    "fallback",
    "sample_source",
)
REQUIRED_TEMPLATE_FIELDS = ("id", "platform", "name", "match", "frontmatter", "postprocess")
VALID_STATUSES = {"stable", "beta", "heavy", "manual", "experimental"}


def clean_scalar(value):
    value = str(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def parse_inline_list(value):
    value = value.strip()
    if not value.startswith("[") or not value.endswith("]"):
        return None
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [clean_scalar(item) for item in inner.split(",")]


def parse_simple_yaml(path):
    data = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        parsed_list = parse_inline_list(value)
        data[key] = parsed_list if parsed_list is not None else clean_scalar(value)
    return data


def ensure_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_records(directory):
    records = []
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.yaml")):
        data = parse_simple_yaml(path)
        data["_path"] = str(path)
        records.append(data)
    return records


def check_dependency(dep):
    dep = clean_scalar(dep)
    if dep.startswith("cmd:"):
        name = dep.split(":", 1)[1]
        return shutil.which(name) is not None, name
    if dep.startswith("python:"):
        name = dep.split(":", 1)[1]
        try:
            ok = importlib.util.find_spec(name) is not None
        except Exception:
            ok = False
        return ok, name
    if dep.startswith("env:"):
        name = dep.split(":", 1)[1]
        return bool(os.environ.get(name)), name
    return True, dep


def validate_template(template, platform_id):
    errors = []
    for field in REQUIRED_TEMPLATE_FIELDS:
        if not template.get(field):
            errors.append(f"template missing field: {field}")
    if template.get("platform") and template.get("platform") != platform_id:
        errors.append(f"template platform mismatch: {template.get('platform')} != {platform_id}")
    return errors


def check_platform(platform, repo_root, template_dir, local=False):
    errors = []
    warnings = []

    for field in REQUIRED_PLATFORM_FIELDS:
        if not platform.get(field):
            errors.append(f"missing field: {field}")

    status = platform.get("status", "")
    if status and status not in VALID_STATUSES:
        errors.append(f"invalid status: {status}")

    skill_dir = repo_root / str(platform.get("skill", ""))
    script_path = skill_dir / str(platform.get("script", ""))
    if platform.get("skill") and not skill_dir.is_dir():
        errors.append(f"missing skill directory: {platform.get('skill')}")
    if platform.get("script") and not script_path.is_file():
        errors.append(f"missing script: {platform.get('skill')}/{platform.get('script')}")

    template_path = template_dir / f"{platform.get('id')}.yaml"
    template = {}
    if not template_path.exists():
        errors.append(f"missing site template: {template_path.name}")
    else:
        template = parse_simple_yaml(template_path)
        errors.extend(validate_template(template, platform.get("id", "")))

    missing_required = []
    missing_optional = []
    if local:
        for dep in ensure_list(platform.get("required_deps")):
            ok, name = check_dependency(dep)
            if not ok:
                missing_required.append(name)
        for dep in ensure_list(platform.get("optional_deps")):
            ok, name = check_dependency(dep)
            if not ok:
                missing_optional.append(name)

    if errors:
        health = "broken"
    elif local and missing_required:
        health = "blocked"
    elif local and missing_optional:
        health = "degraded"
    else:
        health = status or "unknown"

    return {
        "id": platform.get("id", ""),
        "name": platform.get("name", ""),
        "skill": platform.get("skill", ""),
        "category": platform.get("category", ""),
        "status": status,
        "health": health,
        "source_types": ensure_list(platform.get("source_types")),
        "required_deps": ensure_list(platform.get("required_deps")),
        "optional_deps": ensure_list(platform.get("optional_deps")),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "fallback": platform.get("fallback", ""),
        "output_contract": platform.get("output_contract", ""),
        "sample_source": platform.get("sample_source", ""),
        "notes": platform.get("notes", ""),
        "template": str(template_path),
        "template_exists": template_path.exists(),
        "errors": errors,
        "warnings": warnings,
        "definition": platform.get("_path", ""),
    }


def status_badge(status):
    labels = {
        "stable": "stable",
        "beta": "beta",
        "heavy": "heavy deps",
        "manual": "manual fallback",
        "experimental": "experimental",
        "degraded": "degraded",
        "blocked": "blocked",
        "broken": "broken",
    }
    return labels.get(status, status or "unknown")


def format_list(values):
    values = ensure_list(values)
    return ", ".join(values) if values else "-"


def escape_cell(value):
    value = str(value or "").replace("\n", " ").replace("|", "\\|").strip()
    return value or "-"


def build_markdown(results, local=False, generated_at=None):
    generated_at = generated_at or datetime.now().astimezone().replace(microsecond=0).isoformat()
    lines = [
        "# Platform Status",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "This page is generated from `platforms/*.yaml` and `templates/sites/*.yaml`.",
        "Default checks validate repository structure and template coverage. Run with `--local` to include local dependency readiness.",
        "",
        f"Local dependency check: `{'on' if local else 'off'}`",
        "",
        "| platform | skill | status | content | fallback | template | notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in sorted(results, key=lambda record: record["id"]):
        template_state = "yes" if item["template_exists"] else "missing"
        notes = item["notes"]
        if item["errors"]:
            notes = "errors: " + "; ".join(item["errors"])
        elif item["warnings"]:
            notes = (notes + " " if notes else "") + "warnings: " + "; ".join(item["warnings"])
        if local:
            if item["missing_required"]:
                notes = (notes + " " if notes else "") + "missing required: " + format_list(item["missing_required"])
            if item["missing_optional"]:
                notes = (notes + " " if notes else "") + "missing optional: " + format_list(item["missing_optional"])
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(item["name"] or item["id"]),
                    escape_cell(item["skill"]),
                    escape_cell(status_badge(item["health"])),
                    escape_cell(format_list(item["source_types"])),
                    escape_cell(item["fallback"]),
                    escape_cell(template_state),
                    escape_cell(notes),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Status Meaning",
            "",
            "- `stable`: text/subtitle-first path is expected to be reliable.",
            "- `beta`: works, but platform markup or anti-bot behavior may change.",
            "- `heavy deps`: requires local audio/video transcription dependencies.",
            "- `manual fallback`: supports manual text fallback when live fetch fails.",
            "- `blocked` / `degraded`: local dependency check found missing required or optional dependencies.",
            "- `broken`: repository definition, script, or template validation failed.",
            "",
            "## Commands",
            "",
            "```bash",
            "python3 tools/platform_health.py --check",
            "python3 tools/platform_health.py --local --check",
            "python3 tools/platform_health.py --json",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_checks(platform_dir, template_dir, repo_root, local=False):
    platforms = load_records(platform_dir)
    results = [check_platform(platform, repo_root, template_dir, local=local) for platform in platforms]
    if not platforms:
        results.append(
            {
                "id": "",
                "name": "",
                "skill": "",
                "category": "",
                "status": "",
                "health": "broken",
                "source_types": [],
                "required_deps": [],
                "optional_deps": [],
                "missing_required": [],
                "missing_optional": [],
                "fallback": "",
                "output_contract": "",
                "sample_source": "",
                "notes": "",
                "template": "",
                "template_exists": False,
                "errors": [f"no platform definitions found in {platform_dir}"],
                "warnings": [],
                "definition": "",
            }
        )
    return results


def has_errors(results):
    return any(item["errors"] for item in results)


def normalize_generated_markdown(text):
    lines = []
    for line in text.splitlines():
        if line.startswith("Generated at: `"):
            lines.append("Generated at: `<generated>`")
        else:
            lines.append(line)
    return "\n".join(lines).strip() + "\n"


def output_is_fresh(output, results, local=False):
    output = Path(output)
    if not output.exists():
        return False, f"missing generated output: {output}"
    expected = build_markdown(results, local=local, generated_at="<generated>")
    actual = output.read_text(encoding="utf-8")
    if normalize_generated_markdown(actual) != normalize_generated_markdown(expected):
        return False, f"generated output is stale: {output}"
    return True, ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate platforms and generate docs/platform-status.md")
    parser.add_argument("--platform-dir", default=str(DEFAULT_PLATFORM_DIR), help="Directory with platform YAML files")
    parser.add_argument("--template-dir", default=str(DEFAULT_TEMPLATE_DIR), help="Directory with site template YAML files")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root used to resolve skill scripts")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown output path")
    parser.add_argument("--local", action="store_true", help="Check local commands, Python packages, and env vars")
    parser.add_argument("--check", action="store_true", help="Validate only; do not write Markdown")
    parser.add_argument("--check-output", action="store_true", help="Validate that the generated Markdown output is fresh")
    parser.add_argument("--json", action="store_true", help="Print JSON results")
    args = parser.parse_args(argv)

    platform_dir = Path(args.platform_dir)
    template_dir = Path(args.template_dir)
    repo_root = Path(args.repo_root)
    results = run_checks(platform_dir, template_dir, repo_root, local=args.local)

    if args.json:
        print(json.dumps({"platforms": results}, ensure_ascii=False, indent=2))
    elif args.check or args.check_output:
        for item in results:
            if args.local:
                detail = ""
                if item["missing_required"]:
                    detail += " missing required: " + format_list(item["missing_required"])
                if item["missing_optional"]:
                    detail += " missing optional: " + format_list(item["missing_optional"])
                print(f"{item['id']}: {status_badge(item['health'])}{detail}")
            for error in item["errors"]:
                print(f"❌ {item['id'] or item['definition']}: {error}")
            for warning in item["warnings"]:
                print(f"⚠️  {item['id']}: {warning}")
        output_error = ""
        if args.check_output:
            ok, output_error = output_is_fresh(args.output, results, local=args.local)
            if not ok:
                print(f"❌ {output_error}")
        if not has_errors(results) and not output_error:
            print(f"✅ Checked {len(results)} platform definition(s).")
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(build_markdown(results, local=args.local), encoding="utf-8")
        print(f"✅ Wrote {output}")

    if has_errors(results):
        return 1
    if args.check_output:
        ok, _ = output_is_fresh(args.output, results, local=args.local)
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
