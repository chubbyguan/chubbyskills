#!/usr/bin/env python3
"""
Run the chubbyskills platform smoke matrix.

The matrix has three layers:
- offline: verifies every platform definition routes to the expected skill script.
- fallback: verifies manual fallback platforms can produce schema v1 Markdown.
- live: optionally runs real platform samples from CHUBBY_SMOKE_<PLATFORM>_SOURCE.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
DEFAULT_OUTPUT = ROOT / "docs" / "platform-smoke-matrix.md"
FALLBACK_TEXT = ROOT / "fixtures" / "platform_smoke" / "fallback-text.md"

try:
    from tools import platform_health
    from tools import validate_outputs
except ModuleNotFoundError:
    sys.path.insert(0, str(TOOLS_DIR))
    import platform_health
    import validate_outputs


FALLBACK_PLATFORMS = {
    "x": {
        "source": "https://x.com/example/status/1234567890",
        "title": "X fallback smoke",
    },
    "xiaohongshu": {
        "source": "https://www.xiaohongshu.com/explore/example",
        "title": "小红书 fallback smoke",
    },
}

FAILURE_PATTERNS = (
    ("missing_dependency", ("No module named", "ModuleNotFoundError", "not found", "No such file", "ffmpeg", "yt-dlp")),
    ("auth_or_cookie", ("cookie", "login", "登录", "XHS_COOKIE", "unauthorized", "forbidden", "403")),
    ("anti_bot_or_rate_limit", ("blocked", "风控", "verify", "captcha", "rate limit", "429", "环境异常")),
    ("expired_or_invalid_source", ("404", "not found", "无法识别", "Invalid input", "受限", "已删除")),
    ("network", ("timed out", "timeout", "Temporary failure", "Connection", "Name or service")),
)


def load_platforms(platform_dir):
    return platform_health.load_records(Path(platform_dir))


def env_name(platform_id):
    return "CHUBBY_SMOKE_" + re.sub(r"[^A-Z0-9]+", "_", platform_id.upper()) + "_SOURCE"


def compact(value, limit=500):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def classify_failure(text):
    lower = text.lower()
    for kind, patterns in FAILURE_PATTERNS:
        for pattern in patterns:
            if pattern.lower() in lower:
                return kind
    return "unknown"


def run_process(cmd, timeout=90):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def result(platform, mode, status, detail="", command=None, output_path="", failure_kind="", fallback=""):
    return {
        "platform": platform.get("id", ""),
        "name": platform.get("name", ""),
        "mode": mode,
        "status": status,
        "detail": compact(detail),
        "command": command or [],
        "output_path": output_path,
        "failure_kind": failure_kind,
        "fallback": fallback or platform.get("fallback", ""),
    }


def offline_smoke(platform, output_dir):
    source = platform.get("sample_source") or f"offline://{platform.get('id')}"
    cmd = [
        sys.executable,
        str(TOOLS_DIR / "chubby_ingest.py"),
        source,
        "--skill",
        platform["id"],
        "--output",
        str(output_dir),
        "--dry-run",
    ]
    try:
        proc = run_process(cmd, timeout=30)
    except Exception as exc:
        return result(platform, "offline", "failed", str(exc), cmd, failure_kind=classify_failure(str(exc)))

    detail = "\n".join(part for part in (proc.stderr, proc.stdout) if part)
    expected = str(Path(platform.get("skill", "")) / platform.get("script", ""))
    if proc.returncode == 0 and expected in detail:
        return result(platform, "offline", "passed", f"routes to {expected}", cmd)
    return result(
        platform,
        "offline",
        "failed",
        detail or f"returncode={proc.returncode}",
        cmd,
        failure_kind=classify_failure(detail),
    )


def write_temp_config(tmpdir):
    config = Path(tmpdir) / "chubby.yaml"
    config.write_text(
        "\n".join(
            [
                f"output_dir: {Path(tmpdir) / 'output'}",
                "vault_dir:",
                f"state_file: {Path(tmpdir) / 'runs.jsonl'}",
                f"report_dir: {Path(tmpdir) / 'runs'}",
                f"queue_file: {Path(tmpdir) / 'inbox' / 'links.txt'}",
                "enrich: false",
                "timeout_seconds: 120",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config


def validate_generated_output(output_dir):
    files = sorted(Path(output_dir).glob("*.md"))
    if not files:
        return False, "no Markdown output generated", ""
    latest = max(files, key=lambda path: path.stat().st_mtime)
    problems = [
        problem
        for problem in validate_outputs.validate_file(str(latest), require_schema_v1=True)
        if problem["level"] == "error"
    ]
    if problems:
        return False, "; ".join(problem["message"] for problem in problems), str(latest)
    return True, "generated schema v1 Markdown", str(latest)


def pipeline_smoke(platform, source, extra, mode):
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        config = write_temp_config(tmpdir)
        cmd = [
            sys.executable,
            str(TOOLS_DIR / "chubby.py"),
            "--config",
            str(config),
            "ingest",
            source,
            "--skill",
            platform["id"],
            "--output",
            str(output_dir),
        ] + list(extra)
        try:
            proc = run_process(cmd, timeout=150)
        except Exception as exc:
            return result(platform, mode, "failed", str(exc), cmd, failure_kind=classify_failure(str(exc)))

        combined = "\n".join(part for part in (proc.stderr, proc.stdout) if part)
        if proc.returncode != 0:
            return result(platform, mode, "failed", combined, cmd, failure_kind=classify_failure(combined))

        ok, detail, output_path = validate_generated_output(output_dir)
        if ok:
            return result(platform, mode, "passed", detail, cmd, output_path=output_path)
        return result(platform, mode, "failed", detail, cmd, output_path=output_path, failure_kind=classify_failure(detail))


def fallback_smoke(platform):
    spec = FALLBACK_PLATFORMS.get(platform["id"])
    if not spec:
        return result(platform, "fallback", "skipped", "platform has no deterministic fallback smoke")
    extra = [
        "--fallback-only",
        "--fallback-text",
        str(FALLBACK_TEXT),
        "--fallback-title",
        spec["title"],
    ]
    return pipeline_smoke(platform, spec["source"], extra, "fallback")


def live_smoke(platform, use_sample_sources=False):
    source = os.environ.get(env_name(platform["id"]))
    source_from_env = bool(source)
    if not source and use_sample_sources:
        source = platform.get("sample_source", "")
    if (
        not source
        or (not source_from_env and source.startswith("/path/to/"))
        or (not source_from_env and "example" in source.lower())
        or (not source_from_env and "xxxx" in source.lower())
    ):
        return result(
            platform,
            "live",
            "skipped",
            f"set {env_name(platform['id'])} to run a live smoke",
        )
    return pipeline_smoke(platform, source, [], "live")


def run_matrix(platform_dir=platform_health.DEFAULT_PLATFORM_DIR, mode="offline", use_sample_sources=False):
    platforms = load_platforms(platform_dir)
    all_results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "dry-run-output"
        for platform in platforms:
            if mode in {"offline", "all"}:
                all_results.append(offline_smoke(platform, output_dir))
            if mode in {"fallback", "all"}:
                all_results.append(fallback_smoke(platform))
            if mode in {"live", "all"}:
                all_results.append(live_smoke(platform, use_sample_sources=use_sample_sources))
    return all_results


def has_failures(results, require_live=False):
    for item in results:
        if item["status"] == "failed":
            return True
        if require_live and item["mode"] == "live" and item["status"] == "skipped":
            return True
    return False


def print_table(results):
    print("| platform | mode | status | failure kind | detail |")
    print("|---|---|---|---|---|")
    for item in results:
        print(
            "| "
            + " | ".join(
                [
                    item["platform"],
                    item["mode"],
                    item["status"],
                    item.get("failure_kind") or "-",
                    item.get("detail") or "-",
                ]
            )
            + " |"
        )


def build_markdown(results, generated_at=None):
    generated_at = generated_at or datetime.now().astimezone().replace(microsecond=0).isoformat()
    lines = [
        "# Platform Smoke Matrix",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "This matrix separates deterministic CI checks from optional live platform checks.",
        "",
        "- `offline`: verifies platform routing without network access.",
        "- `fallback`: verifies manual fallback can still produce schema v1 Markdown.",
        "- `live`: runs only when `CHUBBY_SMOKE_<PLATFORM>_SOURCE` is set.",
        "",
        "| platform | mode | status | failure kind | fallback | detail |",
        "|---|---|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["platform"],
                    item["mode"],
                    item["status"],
                    item.get("failure_kind") or "-",
                    (item.get("fallback") or "-").replace("|", "\\|"),
                    (item.get("detail") or "-").replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Live Smoke",
            "",
            "```bash",
            "export CHUBBY_SMOKE_X_SOURCE='https://x.com/<user>/status/<id>'",
            "python3 tools/platform_smoke.py --mode live --check",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run platform smoke matrix")
    parser.add_argument("--platform-dir", default=str(platform_health.DEFAULT_PLATFORM_DIR))
    parser.add_argument("--mode", choices=["offline", "fallback", "live", "all"], default="offline")
    parser.add_argument("--use-sample-sources", action="store_true", help="Allow live mode to use sample_source values")
    parser.add_argument("--require-live", action="store_true", help="Treat skipped live checks as failures")
    parser.add_argument("--check", action="store_true", help="Exit non-zero on failures")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown matrix output")
    parser.add_argument("--write", action="store_true", help="Write Markdown matrix output")
    args = parser.parse_args(argv)

    results = run_matrix(args.platform_dir, mode=args.mode, use_sample_sources=args.use_sample_sources)
    failed = has_failures(results, require_live=args.require_live)

    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    elif args.write:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(build_markdown(results), encoding="utf-8")
        print(f"Wrote {output}")
    else:
        print_table(results)

    if args.check and failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
