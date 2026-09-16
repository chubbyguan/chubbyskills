#!/usr/bin/env python3
"""
Run the chubbyskills platform smoke matrix.

The matrix has three layers:
- offline: verifies every platform definition routes to the expected skill script.
- fallback: verifies manual fallback platforms can produce schema v1 Markdown.
- live: optionally runs real platform samples from CHUBBY_SMOKE_<PLATFORM>_SOURCE.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform as runtime_platform
import re
import subprocess
import sys
import tempfile
from contextlib import nullcontext
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
    ("auth_or_cookie", ("cookie", "login", "登录", "XHS_COOKIE", "unauthorized", "forbidden", "403")),
    ("anti_bot_or_rate_limit", ("blocked", "风控", "verify", "captcha", "rate limit", "429", "环境异常")),
    ("network", ("timed out", "timeout", "Temporary failure", "Connection", "Name or service")),
    ("missing_dependency", ("No module named", "ModuleNotFoundError", "command not found", "No such file or directory",
                            "缺少 Python 依赖", "未找到系统命令", "ffmpeg not found", "yt-dlp not found")),
    ("expired_or_invalid_source", ("404", "not found", "无法识别", "Invalid input", "受限", "已删除")),
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
        "checked_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
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


def save_evidence(item, source, directory):
    """Keep local evidence; captured content and logs are not publication-safe."""
    item["source"] = source
    item["human_verified"] = False
    item["runtime"] = {"python": runtime_platform.python_version(), "system": runtime_platform.system()}
    for package in ("yt-dlp", "beautifulsoup4", "faster-whisper", "mcp"):
        try:
            item["runtime"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    item["project_version"] = (ROOT / "VERSION").read_text().strip()
    output = item.get("output_path")
    if output and Path(output).is_file():
        data = Path(output).read_bytes()
        _, body = validate_outputs.split_frontmatter(data.decode("utf-8"))
        item["output_sha256"] = hashlib.sha256(data).hexdigest()
        item["output_bytes"] = len(data)
        item["body_chars"] = len(body.strip())
    evidence = Path(directory) / "evidence.json"
    item["evidence_path"] = str(evidence)
    evidence.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return item


def pipeline_smoke(platform, source, extra, mode, artifacts_dir=None):
    if artifacts_dir:
        if not re.fullmatch(r"[a-z0-9-]+", platform["id"]):
            raise ValueError("invalid platform id for evidence path")
        base = Path(artifacts_dir).expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        context = nullcontext(tempfile.mkdtemp(prefix=platform["id"] + "-", dir=base))
    else:
        context = tempfile.TemporaryDirectory()
    with context as tmpdir:
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
            item = result(platform, mode, "failed", str(exc), cmd, failure_kind=classify_failure(str(exc)))
            if artifacts_dir:
                logs = []
                for value in (getattr(exc, "stdout", ""), getattr(exc, "stderr", ""), str(exc)):
                    logs.append(value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value or ""))
                Path(tmpdir, "process.log").write_text("\n".join(logs), encoding="utf-8")
            return save_evidence(item, source, tmpdir) if artifacts_dir else item

        combined = "\n".join(part for part in (proc.stderr, proc.stdout) if part)
        if artifacts_dir:
            Path(tmpdir, "process.log").write_text(combined, encoding="utf-8")
        if proc.returncode != 0:
            item = result(platform, mode, "failed", combined, cmd, failure_kind=classify_failure(combined))
        else:
            ok, detail, output_path = validate_generated_output(output_dir)
            item = result(platform, mode, "passed" if ok else "failed", detail, cmd,
                          output_path=output_path, failure_kind="" if ok else classify_failure(detail))
        return save_evidence(item, source, tmpdir) if artifacts_dir else item


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


def live_smoke(platform, use_sample_sources=False, artifacts_dir=None):
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
    return pipeline_smoke(platform, source, [], "live", artifacts_dir=artifacts_dir)


def run_matrix(platform_dir=platform_health.DEFAULT_PLATFORM_DIR, mode="offline", use_sample_sources=False,
               platform_ids=None, artifacts_dir=None):
    platforms = load_platforms(platform_dir)
    if platform_ids:
        selected = set(platform_ids)
        unknown = selected - {item["id"] for item in platforms}
        if unknown:
            raise ValueError("unknown platforms: " + ", ".join(sorted(unknown)))
        platforms = [item for item in platforms if item["id"] in selected]
    all_results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "dry-run-output"
        for platform in platforms:
            if mode in {"offline", "all"}:
                all_results.append(offline_smoke(platform, output_dir))
            if mode in {"fallback", "all"}:
                all_results.append(fallback_smoke(platform))
            if mode in {"live", "all"}:
                all_results.append(live_smoke(platform, use_sample_sources=use_sample_sources,
                                              artifacts_dir=artifacts_dir))
    return all_results


def has_failures(results, require_live=False):
    if require_live and not any(item["mode"] == "live" for item in results):
        return True
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
        "A skipped live check is unverified. A passed check validates output structure, not transcript accuracy.",
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
    parser.add_argument("--platform", action="append", dest="platform_ids", help="Select a platform ID; repeat for multiple")
    parser.add_argument("--artifacts-dir", help="Retain live outputs/logs/evidence locally; inspect before sharing")
    parser.add_argument("--check", action="store_true", help="Exit non-zero on failures")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown matrix output")
    parser.add_argument("--write", action="store_true", help="Write Markdown matrix output")
    args = parser.parse_args(argv)

    if args.require_live and args.mode not in {"live", "all"}:
        parser.error("--require-live requires --mode live or all")
    try:
        results = run_matrix(args.platform_dir, mode=args.mode, use_sample_sources=args.use_sample_sources,
                             platform_ids=args.platform_ids, artifacts_dir=args.artifacts_dir)
    except ValueError as exc:
        parser.error(str(exc))
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
