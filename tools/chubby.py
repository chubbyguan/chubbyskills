#!/usr/bin/env python3
"""
Chubby Skills pipeline CLI.

This is the v0.5 orchestration layer on top of the existing one-shot
tools/chubby_ingest.py workflow. It adds config, queue runs, persistent run
state, retry, and Markdown run reports without adding runtime dependencies.
"""

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"

try:
    from tools import chubby_ingest
    from tools import platform_health
    from tools import validate_outputs
    from tools import vault_index
    from tools import source_identity
    from tools import podcast_options
except ModuleNotFoundError:
    sys.path.insert(0, str(TOOLS_DIR))
    import chubby_ingest
    import platform_health
    import validate_outputs
    import vault_index
    import source_identity
    import podcast_options


DEFAULT_CONFIG = {
    "output_dir": "output",
    "vault_dir": "",
    "vault_root": "",
    "index_db": "",
    "state_file": ".chubby/runs.jsonl",
    "report_dir": "runs",
    "queue_file": "inbox/links.txt",
    "enrich": "false",
    "timeout_seconds": "1800",
}

BOOL_KEYS = {"enrich"}
SCHEMA_VERSION = "1"
VALID_STATUSES = {"success", "failed", "dry_run", "running"}
QUICKSTART_SOURCE = "https://x.com/example/status/123456"


def read_version():
    version_path = ROOT / "VERSION"
    if version_path.exists():
        return version_path.read_text(encoding="utf-8").strip()
    return "0.0.0"


def now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def today():
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def source_hash(source):
    return source_identity.source_digest(source, base_dir=ROOT)


def make_run_id():
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def clean_scalar(value):
    value = str(value).strip()
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, str):
                return decoded
        except ValueError:
            pass
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return clean_scalar(value).lower() in {"1", "true", "yes", "y", "on"}


def parse_int(value, default):
    try:
        return int(clean_scalar(value))
    except (TypeError, ValueError):
        return default


def resolve_path(value):
    value = clean_scalar(value)
    value = os.path.expandvars(os.path.expanduser(value))
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def parse_config_file(path):
    config = {}
    if not path.exists():
        return config
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in DEFAULT_CONFIG:
            config[key] = clean_scalar(value)
    return config


def load_config(path=None):
    config_path = resolve_path(path) if path else ROOT / "chubby.yaml"
    config = dict(DEFAULT_CONFIG)
    config.update(parse_config_file(config_path))
    config["_config_path"] = str(config_path)
    config["_config_exists"] = config_path.exists()
    return config


def write_default_config(path, vault=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = """# Chubby Skills pipeline config
# Paths can be absolute or relative to this repository.
output_dir: output
vault_dir:
vault_root:
index_db:
state_file: .chubby/runs.jsonl
report_dir: runs
queue_file: inbox/links.txt
enrich: false
timeout_seconds: 1800
"""
    if vault:
        root = resolve_path(vault).resolve()
        for key, value in vault_config_fields(root).items():
            text = text.replace(f"{key}:\n", f"{key}: {json.dumps(value, ensure_ascii=False)}\n")
    path.write_text(text, encoding="utf-8")


def vault_config_fields(vault):
    root = resolve_path(vault).resolve()
    return {"vault_root": str(root), "vault_dir": str(root / "00_Inbox"),
            "index_db": str(root / ".chubby" / "index.sqlite")}


def update_vault_config(path, vault):
    values = vault_config_fields(vault)
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        key = line.split(":", 1)[0].strip()
        if key in values:
            lines.append(f"{key}: {json.dumps(values.pop(key), ensure_ascii=False)}")
        else:
            lines.append(line)
    lines.extend(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in values.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_runtime_dirs(config):
    resolve_path(config["state_file"]).parent.mkdir(parents=True, exist_ok=True)
    resolve_path(config["report_dir"]).mkdir(parents=True, exist_ok=True)
    resolve_path(config["queue_file"]).parent.mkdir(parents=True, exist_ok=True)
    resolve_path(config["output_dir"]).mkdir(parents=True, exist_ok=True)
    if config.get("vault_dir"):
        resolve_path(config["vault_dir"]).mkdir(parents=True, exist_ok=True)


def init_workspace(args):
    config_path = resolve_path(args.config) if args.config else ROOT / "chubby.yaml"
    if config_path.exists() and not args.force:
        if getattr(args, "vault", None):
            update_vault_config(config_path, args.vault)
            print(f"✅ 已更新知识库配置：{config_path}")
        else:
            print(f"⚠️  配置已存在：{config_path}")
            print("   如需覆盖，请加 --force。")
    else:
        write_default_config(config_path, vault=getattr(args, "vault", None))
        print(f"✅ 已写入配置：{config_path}")

    config = load_config(str(config_path))
    ensure_runtime_dirs(config)
    state_file = resolve_path(config["state_file"])
    if not state_file.exists():
        state_file.write_text("", encoding="utf-8")

    queue_file = resolve_path(config["queue_file"])
    if not queue_file.exists():
        queue_file.write_text(
            "# One source per line. Blank lines and # comments are ignored.\n"
            "# https://www.bilibili.com/video/BVxxxx\n"
            "# https://mp.weixin.qq.com/s/xxxx\n",
            encoding="utf-8",
        )
    print(f"✅ 已准备队列：{queue_file}")
    print(f"✅ 已准备状态：{state_file}")
    print(f"✅ 已准备报告目录：{resolve_path(config['report_dir'])}")
    return 0


def read_queue(path):
    queue_path = resolve_path(path)
    if not queue_path.exists():
        raise FileNotFoundError(f"queue file not found: {queue_path}")
    sources = []
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            sources.append(item)
    return sources


def load_records(config):
    path = resolve_path(config["state_file"])
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append({"status": "failed", "error": "invalid state line", "raw": line})
    # A cloud run writes a start event before launching a possibly billable
    # child and a final event afterwards. Keep attempts in their first-seen
    # order: an older attempt finishing late must not hide a newer pending job.
    latest = {}
    for index, record in enumerate(records):
        key = record.get("run_id") or ("line", index)
        latest[key] = record
    return list(latest.values())


def append_record(config, record):
    state_file = resolve_path(config["state_file"])
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 4 :].lstrip("\n")


def upsert_frontmatter(path, fields):
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = split_frontmatter(text)
    if frontmatter is None:
        return False

    keys = set(fields)
    kept = []
    for line in frontmatter.splitlines():
        key = line.split(":", 1)[0].strip()
        if key not in keys:
            kept.append(line)
    for key, value in fields.items():
        kept.append(f"{key}: {value}")
    path.write_text("---\n" + "\n".join(kept) + "\n---\n\n" + body, encoding="utf-8")
    return True


def yaml_quote(value):
    value = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{value}"'


def infer_content_type(skill, source):
    lower = source.lower()
    if skill == "podcast" or lower.endswith((".mp3", ".m4a", ".wav", ".ogg", ".aac")):
        return "audio"
    if skill in {"bilibili", "douyin", "tiktok", "weibo", "youtube", "zhihu"}:
        return "video"
    if skill == "wechat" or lower.endswith(".pdf"):
        return "article"
    if skill in {"x", "xiaohongshu"}:
        return "social"
    return "note"


def asset_manifest(markdown_path):
    asset_dir = markdown_path.with_suffix("").with_name(markdown_path.stem + ".assets")
    if asset_dir.is_dir():
        return json.dumps([asset_dir.name], ensure_ascii=False)
    return "[]"


def stamp_pipeline_metadata(record):
    output = record.get("output_path")
    if not output or not str(output).endswith(".md"):
        return False
    path = resolve_path(output)
    if not path.exists():
        return False

    fields = {
        "schema_version": SCHEMA_VERSION,
        "run_id": yaml_quote(record["run_id"]),
        "source_hash": yaml_quote(record["source_hash"]),
        "captured_at": yaml_quote(record["started_at"]),
        "processed_at": yaml_quote(record["finished_at"]),
        "content_type": record["content_type"],
        "status": record["status"],
        "assets": asset_manifest(path),
    }
    return upsert_frontmatter(path, fields)


def candidate_output_paths(stdout, stderr):
    candidates = []
    output_prefixes = ("📥 已入库：", "✅ Saved fallback:", "✅ Saved:", "Output:")
    for text, is_stdout in ((stdout or "", True), (stderr or "", False)):
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            declared_output = is_stdout
            for prefix in output_prefixes:
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    declared_output = True
                    break
            # stderr also contains progress messages that happen to end in .md.
            # Only declared outputs or an existing bare path belong to the contract.
            if not line.endswith(".md"):
                continue
            if not declared_output:
                try:
                    if not resolve_path(line).is_file():
                        continue
                except OSError:
                    # Arbitrary log text can exceed the filesystem's filename limit.
                    continue
            candidates.append(line)
    deduped = []
    seen = set()
    for item in candidates:
        key = str(resolve_path(item))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def stamp_all_outputs(record):
    stamped = []
    for output in record.get("output_paths") or [record.get("output_path", "")]:
        if not output:
            continue
        item = dict(record)
        item["output_path"] = output
        if stamp_pipeline_metadata(item):
            stamped.append(output)
    return stamped


def add_inferred_working_output(record):
    output_path = record.get("output_path", "")
    if not output_path or not str(output_path).endswith(".md") or not record.get("vault_dir"):
        return record
    working_dir = resolve_path(record.get("output_dir", DEFAULT_CONFIG["output_dir"]))
    if any(resolve_path(path).resolve().parent == working_dir.resolve() for path in record.get("output_paths", [])):
        return record
    working_path = working_dir / Path(output_path).name
    if working_path.exists():
        paths = list(record.get("output_paths") or [])
        working = str(working_path)
        if working not in paths:
            paths.insert(0, working)
        record["output_paths"] = paths
    return record


def build_ingest_command(source, args, config, skill=None):
    output = args.output or config["output_dir"]
    vault = args.vault if args.vault is not None else config["vault_dir"]
    enrich = args.enrich if args.enrich is not None else parse_bool(config["enrich"])

    cmd = [
        sys.executable,
        str(TOOLS_DIR / "chubby_ingest.py"),
        source,
        "--output",
        output,
    ]
    selected_skill = skill or args.skill
    if selected_skill:
        cmd.extend(["--skill", selected_skill])
    if enrich:
        cmd.append("--enrich")
    if vault:
        cmd.extend(["--vault", vault])
    if args.dry_run:
        cmd.append("--dry-run")
    cmd.extend(getattr(args, "extra", []))
    return cmd, selected_skill, output, vault, enrich


def last_stdout_line(stdout):
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def compact_error(stdout, stderr):
    # Tracebacks and actionable dependency errors usually finish stderr.
    text = "\n".join(part.strip() for part in (stdout, stderr) if part and part.strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= 800 else "...[truncated]... " + text[-782:]


def compact_log(value, limit=4000):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 20] + "\n...[truncated]..."


def index_context(vault, config):
    if not vault:
        return "", ""
    destination = resolve_path(vault).resolve()
    root = resolve_path(config["vault_root"]).resolve() if config.get("vault_root") else None
    if root is not None and (destination == root or root in destination.parents):
        database = resolve_path(config["index_db"]) if config.get("index_db") else None
        return str(root), str(vault_index.resolve_db_path(root, db_path=database))
    # An explicit destination outside the configured vault owns its own index.
    database = None
    if root is None and config.get("vault_dir") and destination == resolve_path(config["vault_dir"]).resolve():
        database = resolve_path(config["index_db"]) if config.get("index_db") else None
    return str(destination), str(vault_index.resolve_db_path(destination, db_path=database))


def execution_fingerprint(execution):
    context = dict(execution)
    file_inputs = {}
    for value in execution["extra"]:
        if str(value).startswith("-"):
            if "=" not in str(value):
                continue
            value = str(value).split("=", 1)[1]
        path = resolve_path(value)
        try:
            if path.is_file():
                file_inputs[str(path.resolve())] = source_hash(str(path))
        except OSError:
            continue
    context["file_inputs"] = file_inputs
    context["project_version"] = read_version()
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode("utf-8")).hexdigest()


def find_reusable_record(config, identity, fingerprint):
    for previous in reversed(load_records(config)):
        if previous.get("source_hash") != identity or previous.get("execution_hash") != fingerprint:
            continue
        # A newer failed refresh/resubmission represents unfinished work. Do
        # not hide it by returning an older success instead of resuming it.
        if previous.get("status") in {"failed", "running"}:
            return None
        if previous.get("status") != "success":
            continue
        paths = previous.get("output_paths") or [previous.get("output_path")]
        if not paths or not all(paths):
            continue
        try:
            valid = True
            for value in paths:
                path = resolve_path(value)
                if not path.is_file() or any(
                    issue["level"] == "error"
                    for issue in validate_outputs.validate_file(path, require_schema_v1=True)
                ):
                    valid = False
                    break
                block, _ = split_frontmatter(path.read_text(encoding="utf-8"))
                fields = validate_outputs.parse_frontmatter(block)
                if (clean_scalar(fields.get("source_hash", "")) != identity
                        or clean_scalar(fields.get("status", "")) != "success"):
                    valid = False
                    break
                for asset in vault_index.inline_list_items(fields.get("assets", "[]")):
                    if not (path.parent / asset).exists():
                        valid = False
            if not all(resolve_path(path).is_file() for path in previous.get("artifact_files", [])):
                valid = False
            if valid:
                return previous
        except (OSError, ValueError):
            continue
    return None


def finish_record(record, secrets=()):
    if record.get("status") == "success" and not record.get("reused"):
        files = []
        try:
            for value in record.get("output_paths", []):
                assets = resolve_path(value).with_suffix(".assets")
                if assets.is_dir():
                    files.extend(str(path) for path in assets.rglob("*") if path.is_file())
            record["artifact_files"] = sorted(set(files))
        except OSError as exc:
            record["status"] = "failed"
            record["error"] = f"cannot inspect output assets: {exc}"
    if record.get("status") == "success" and record.get("index_vault"):
        try:
            record["index_result"] = vault_index.sync_vault(record["index_vault"], db_path=record["index_db"])
            record["index_status"] = "success"
        except Exception as exc:
            record["index_status"] = "failed"
            record["index_error"] = str(exc)
    # Commands, source URLs, and persisted options are already structurally
    # redacted. Only free-form diagnostics need value-based scrubbing; doing
    # this to every field could corrupt IDs or status for short credentials.
    for key in ("stdout", "stderr", "error", "index_error"):
        if key in record:
            record[key] = chubby_ingest.redact_text(record[key], secrets)
    return record


def run_ingest_source(source, args, config, batch_id=None, skill=None):
    started_at = now_iso()
    detected_skill = skill or args.skill or chubby_ingest.detect_skill(source)
    args = copy.copy(args)
    args.extra = list(getattr(args, "extra", []))
    preflight_error = ""
    document_fingerprint = ""
    try:
        if detected_skill == "podcast":
            args.extra, _ = podcast_options.resolve_extra(args.extra)
        elif detected_skill == "document" and not args.dry_run:
            try:
                from tools import import_document
            except ModuleNotFoundError:
                import import_document
            document_fingerprint = import_document.document_fingerprint(resolve_path(source))
    except (OSError, ValueError) as exc:
        preflight_error = str(exc)
    cmd, selected_skill, output, vault, enrich = build_ingest_command(
        source, args, config, skill=detected_skill
    )
    timeout_seconds = getattr(args, "timeout", None)
    if timeout_seconds is None:
        timeout_seconds = parse_int(config.get("timeout_seconds"), 1800)
    index_vault, index_db = index_context(vault, config)
    execution = {
        "output_dir": str(resolve_path(output).resolve()),
        "vault_dir": str(resolve_path(vault).resolve()) if vault else "",
        "vault_root": index_vault, "index_db": index_db,
        "enrich": bool(enrich), "skill": selected_skill or detected_skill or "",
        "extra": [item for item in args.extra if item != "--resubmit"], "timeout_seconds": timeout_seconds,
    }
    if document_fingerprint:
        execution["document_fingerprint"] = document_fingerprint
    safe_extra, retry_requires, secrets = chubby_ingest.redact_arguments(execution["extra"])
    safe_source, source_secrets = chubby_ingest.redact_url(source)
    secrets.extend(source_secrets)
    if detected_skill == "podcast":
        secrets.extend(os.environ[key] for key in ("ATLAS_API_KEY", "ATLAS_CLOUD_API_KEY", "MUAPI_API_KEY", "MU_API_KEY") if os.environ.get(key))
    if source_secrets:
        retry_requires.append("--source")
    safe_command, _, command_secrets = chubby_ingest.redact_arguments(cmd)
    secrets.extend(command_secrets)
    fingerprint = execution_fingerprint(execution)
    run_id = make_run_id()
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "batch_id": batch_id or run_id,
        "source": safe_source,
        "source_hash": source_hash(source),
        "skill": selected_skill or detected_skill or "",
        "content_type": infer_content_type(selected_skill or detected_skill or "", source),
        "status": "failed",
        "started_at": started_at,
        "finished_at": "",
        "output_dir": output,
        "output_path": "",
        "output_paths": [],
        "stamped_paths": [],
        "vault_dir": vault or "",
        "enrich": bool(enrich),
        "dry_run": bool(args.dry_run),
        "reused": False,
        "command": safe_command,
        "execution": dict(execution, extra=safe_extra),
        "execution_hash": fingerprint,
        "retry_requires": sorted(set(retry_requires)),
        "index_vault": index_vault,
        "index_db": index_db,
        "index_status": "not_run" if index_vault else "skipped",
        "error": "",
    }
    if preflight_error:
        record.update(error=preflight_error, finished_at=now_iso())
        return finish_record(record, secrets)
    if not args.dry_run and not getattr(args, "refresh", False) and "--resubmit" not in args.extra:
        previous = find_reusable_record(config, record["source_hash"], fingerprint)
        if previous:
            record.update(status="success", finished_at=now_iso(),
                          output_path=previous["output_path"],
                          output_paths=previous.get("output_paths") or [previous["output_path"]],
                          artifact_files=previous.get("artifact_files", []),
                          reused=True, reused_from=previous["run_id"])
            return finish_record(record, secrets)
    if detected_skill == "podcast" and extra_option_value(args.extra, "--provider") in {"atlas", "muapi"} and not args.dry_run:
        # A killed parent must not leave an older success eligible for reuse
        # while the provider's newer job still needs recovery.
        append_record(config, dict(record, status="running", error="Cloud capture started; final state not recorded yet"))
    try:
        process = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds if timeout_seconds > 0 else None,
        )
    except subprocess.TimeoutExpired as exc:
        record["finished_at"] = now_iso()
        record["stdout"] = compact_log(chubby_ingest.redact_text(exc.stdout, secrets))
        record["stderr"] = compact_log(chubby_ingest.redact_text(exc.stderr, secrets))
        record["error"] = f"timeout after {timeout_seconds}s"
        return finish_record(record, secrets)

    record["finished_at"] = now_iso()
    record["stdout"] = compact_log(chubby_ingest.redact_text(process.stdout, secrets))
    record["stderr"] = compact_log(chubby_ingest.redact_text(process.stderr, secrets))

    if process.returncode == 0:
        record["status"] = "dry_run" if args.dry_run else "success"
        record["output_path"] = last_stdout_line(process.stdout)
        record["output_paths"] = candidate_output_paths(process.stdout, process.stderr)
        if record["output_path"] and record["output_path"] not in record["output_paths"]:
            record["output_paths"].append(record["output_path"])
        add_inferred_working_output(record)
        if record["status"] == "success":
            validation_errors = []
            paths = record["output_paths"]
            if not paths:
                validation_errors.append("no Markdown output reported")
            for output_path in paths:
                path = resolve_path(output_path)
                if path.suffix != ".md":
                    validation_errors.append(f"expected Markdown output: {output_path}")
                    continue
                try:
                    if not path.is_file():
                        validation_errors.append(f"missing output file: {output_path}")
                        continue
                    item = dict(record, output_path=output_path)
                    if stamp_pipeline_metadata(item):
                        record["stamped_paths"].append(output_path)
                    for problem in validate_outputs.validate_file(path, require_schema_v1=True):
                        if problem["level"] == "error":
                            validation_errors.append(f"{output_path}: {problem['message']}")
                except OSError as exc:
                    validation_errors.append(f"cannot validate output {output_path}: {exc}")
            if validation_errors:
                record["status"] = "failed"
                # Invalidate both the working file and any already-written vault copy.
                for output_path in record["stamped_paths"]:
                    try:
                        stamp_pipeline_metadata(dict(record, output_path=output_path))
                    except OSError as exc:
                        validation_errors.append(f"cannot mark output failed {output_path}: {exc}")
                record["error"] = "output validation failed: " + "; ".join(validation_errors)
    else:
        record["error"] = compact_error(chubby_ingest.redact_text(process.stdout, secrets),
                                         chubby_ingest.redact_text(process.stderr, secrets))

    return finish_record(record, secrets)


def escape_cell(value):
    value = str(value or "").replace("\n", " ").replace("|", "\\|").strip()
    if len(value) > 96:
        return value[:93] + "..."
    return value


def write_report(config, records, title):
    if not records:
        return None
    report_dir = resolve_path(config["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{today()}.md"
    if not report_path.exists():
        report_path.write_text(f"# Chubby Runs - {today()}\n\n", encoding="utf-8")

    lines = [
        f"## {now_iso()} {title}",
        "",
        "| status | skill | source | output | error |",
        "|---|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(record.get("status")),
                    escape_cell(record.get("skill")),
                    escape_cell(record.get("source")),
                    escape_cell(record.get("output_path")),
                    escape_cell(record.get("error") or (
                        "索引同步失败: " + record.get("index_error", "")
                        if record.get("index_status") == "failed" else ""
                    )),
                ]
            )
            + " |"
        )
    lines.append("")
    with report_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return report_path


def summarize(records):
    counts = {status: 0 for status in VALID_STATUSES}
    for record in records:
        counts[record.get("status", "failed")] = counts.get(record.get("status", "failed"), 0) + 1
    return counts


def print_run_summary(records, report_path):
    counts = summarize(records)
    print(
        f"✅ 完成：success={counts.get('success', 0)} / "
        f"failed={counts.get('failed', 0)} / dry_run={counts.get('dry_run', 0)}"
    )
    if report_path:
        print(f"🧾 报告：{report_path}")
    for record in records:
        if record.get("status") == "failed":
            print(f"❌ {record.get('source')}: {record.get('error')}")
        elif record.get("reused_from"):
            print(f"♻️  复用：{record.get('output_path')}")
        if record.get("index_status") == "failed":
            print(f"❌ 采集已成功，索引同步失败：{record.get('index_error')}")


def record_failed(record):
    return record.get("status") in {"failed", "running"} or record.get("index_status") == "failed"


def command_ingest(args, config):
    batch_id = make_run_id()
    record = run_ingest_source(args.source, args, config, batch_id=batch_id)
    append_record(config, record)
    report_path = write_report(config, [record], "ingest")
    print_run_summary([record], report_path)
    if record.get("output_path"):
        print(record["output_path"])
    return 1 if record_failed(record) else 0


def command_run(args, config):
    try:
        sources = args.sources or read_queue(args.queue or config["queue_file"])
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        print("   先运行 python3 tools/chubby.py init，或用 --queue 指定队列文件。")
        return 1
    if args.limit:
        sources = sources[: args.limit]
    if not sources:
        print("⚠️  队列为空。")
        return 0

    batch_id = make_run_id()
    records = []
    seen = {}
    for source in sources:
        identity = source_hash(source)
        run_args = copy.copy(args)
        if identity in seen:
            run_args.refresh = False
        if identity in seen and seen[identity].get("status") == "failed":
            record = dict(seen[identity], run_id=make_run_id(), duplicate_of=seen[identity]["run_id"])
        else:
            record = run_ingest_source(source, run_args, config, batch_id=batch_id)
        append_record(config, record)
        records.append(record)
        seen[identity] = record
    report_path = write_report(config, records, "queue run")
    print_run_summary(records, report_path)
    return 1 if any(record_failed(record) for record in records) else 0


def latest_records(records):
    latest = {}
    for record in records:
        key = record.get("source_hash") or record.get("source") or record.get("run_id")
        latest[key] = record
    return list(latest.values())


def command_status(args, config):
    records = load_records(config)
    if args.latest:
        records = latest_records(records)
    if args.failed:
        records = [record for record in records if record_failed(record)]
    records = records[-args.limit :]
    if not records:
        print("暂无运行记录。")
        return 0

    print("| status | skill | run_id | source | output/error |")
    print("|---|---|---|---|---|")
    for record in records:
        tail = record.get("error") or record.get("index_error") or record.get("output_path")
        print(
            "| "
            + " | ".join(
                [
                    escape_cell(record.get("status")),
                    escape_cell(record.get("skill")),
                    escape_cell(record.get("run_id")),
                    escape_cell(record.get("source")),
                    escape_cell(tail),
                ]
            )
            + " |"
        )
    return 0


def failed_retry_targets(records, all_failed=False, run_id=None):
    if run_id:
        return [record for record in records if record.get("run_id") == run_id]
    failed = [record for record in latest_records(records) if record_failed(record)]
    if all_failed:
        return failed
    return failed[-1:] if failed else []


def extra_groups(values):
    groups = []
    index = 0
    while index < len(values):
        item = str(values[index])
        group = [item]
        key = item.split("=", 1)[0] if item.startswith("-") else f"positional:{index}"
        if item.startswith("-") and "=" not in item and index + 1 < len(values) and not str(values[index + 1]).startswith("-"):
            index += 1
            group.append(str(values[index]))
        groups.append((key, group))
        index += 1
    return groups


def merge_extra_options(original, overrides):
    replacement = {key for key, _ in extra_groups(overrides)}
    return [item for key, group in extra_groups(original) if key not in replacement for item in group] + list(overrides)


def extra_option_value(values, option):
    result = None
    for key, group in extra_groups(values):
        if key == option:
            result = group[0].split("=", 1)[1] if "=" in group[0] else (group[1] if len(group) > 1 else None)
    return result


def retry_arguments(target, args, config):
    inherited = dict(target.get("execution") or {})
    legacy_requires = []
    if not inherited and target.get("command"):
        # v0.11 records stored the complete wrapper command instead of a
        # structured execution context. Recover only its adapter options.
        core_options = {"--output", "-o", "--vault", "--skill", "--enrich", "--dry-run"}
        old_extra = [item for key, group in extra_groups(target["command"][3:])
                     if key not in core_options for item in group]
        safe_extra, legacy_requires, _ = chubby_ingest.redact_arguments(old_extra)
        inherited["extra"] = safe_extra
        _, source_secrets = chubby_ingest.redact_url(target.get("source", ""))
        if source_secrets:
            legacy_requires.append("--source")
    retry_args = copy.copy(args)
    for argument, key in (("output", "output_dir"), ("vault", "vault_dir"), ("enrich", "enrich"), ("skill", "skill")):
        if getattr(args, argument, None) is None:
            setattr(retry_args, argument, inherited.get(key, target.get(key)))
    if getattr(args, "timeout", None) is None:
        retry_args.timeout = inherited.get("timeout_seconds", parse_int(config.get("timeout_seconds"), 1800))
    original_extra = [item for key, group in extra_groups(inherited.get("extra", [])) if key != "--resubmit" for item in group]
    requested_provider = extra_option_value(getattr(args, "extra", []), "--provider")
    previous_provider = extra_option_value(original_extra, "--provider") or "local"
    if requested_provider is not None and requested_provider != previous_provider:
        # A provider's default model and endpoint must never leak into another
        # provider, especially when their authentication headers differ.
        original_extra = [item for key, group in extra_groups(original_extra)
                          if key not in {"--model", "--base-url"} for item in group]
    retry_args.extra = merge_extra_options(original_extra, getattr(args, "extra", []))
    required = set(target.get("retry_requires", [])) | set(legacy_requires)
    supplied = {key for key, _ in extra_groups(getattr(args, "extra", []))}
    if getattr(args, "source", None):
        supplied.add("--source")
    missing = required - supplied
    if missing:
        raise ValueError("凭据未保存在运行记录中，请重新提供：" + ", ".join(sorted(missing)))
    retry_config = dict(config)
    for key in ("vault_root", "index_db"):
        if key in inherited:
            retry_config[key] = inherited[key]
    return retry_args, retry_config


def command_retry(args, config):
    records = load_records(config)
    targets = failed_retry_targets(records, all_failed=args.all_failed, run_id=args.run_id)
    if not targets:
        print("没有可重试的失败记录。")
        return 0

    batch_id = make_run_id()
    retry_records = []
    blocked = False
    for target in targets:
        try:
            retry_args, retry_config = retry_arguments(target, args, config)
        except ValueError as exc:
            print(f"❌ 无法重试 {target.get('run_id')}: {exc}")
            blocked = True
            continue
        source = getattr(args, "source", None) or target["source"]
        record = run_ingest_source(source, retry_args, retry_config, batch_id=batch_id, skill=retry_args.skill)
        record["retry_of"] = target.get("run_id")
        append_record(config, record)
        retry_records.append(record)
    report_path = write_report(config, retry_records, "retry")
    print_run_summary(retry_records, report_path)
    return 1 if blocked or any(record_failed(record) for record in retry_records) else 0


def command_doctor(args, config):
    print(f"配置文件：{config['_config_path']} ({'存在' if config['_config_exists'] else '未创建'})")
    for key in ("output_dir", "state_file", "report_dir", "queue_file", "vault_dir", "vault_root", "index_db", "enrich", "timeout_seconds"):
        print(f"  {key}: {config.get(key, '')}")
    if not config["_config_exists"]:
        print("\n提示：运行 python3 tools/chubby.py init 可生成 chubby.yaml。")
    print("")
    command = [sys.executable, str(TOOLS_DIR / "check_env.py")]
    if getattr(args, "platform", None):
        command.extend(["--platform", args.platform])
    if getattr(args, "provider", None):
        command.extend(["--provider", args.provider])
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


def query_context(args, config):
    configured = config.get("vault_root") or config.get("vault_dir") or os.environ.get("VAULT_DIR")
    value = getattr(args, "vault", None) or configured
    if not value:
        raise ValueError("请先运行 init --vault <知识库根目录>，或提供 --vault")
    vault = resolve_path(value).resolve()
    database = getattr(args, "db", None)
    if not database and config.get("index_db") and configured and vault == resolve_path(configured).resolve():
        database = config["index_db"]
    return vault, vault_index.resolve_db_path(vault, db_path=resolve_path(database) if database else None)


def command_search(args, config):
    try:
        vault, database = query_context(args, config)
        vault_index.sync_vault(vault, db_path=database)
        options = dict(db_path=database, query=args.query, limit=args.limit,
                       platform=args.platform, tag=args.tag)
        rows = (vault_index.semantic_search(**options, provider="lite") if args.mode == "lite"
                else vault_index.search(**options))
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(f"{row['title']}\n  {row['path']}\n  {row.get('snippet', '')}\n")
            if not rows:
                print("没有找到匹配素材。")
        return 0
    except Exception as exc:
        print(f"❌ 搜索失败：{exc}", file=sys.stderr)
        return 1


def command_brief(args, config):
    try:
        try:
            from tools import evidence_brief
        except ModuleNotFoundError:
            import evidence_brief
        vault, database = query_context(args, config)
        bundle = evidence_brief.build_brief(vault, args.topic, db_path=database,
                                            limit=args.limit, platform=args.platform)
        if args.output:
            outputs = evidence_brief.write_brief(bundle, resolve_path(args.output), overwrite=args.force)
            print(json.dumps(outputs, ensure_ascii=False, indent=2))
        else:
            print(evidence_brief.render_markdown(bundle))
        return 0
    except Exception as exc:
        print(f"❌ 资料包生成失败：{exc}", file=sys.stderr)
        return 1


def prepare_runtime_files(config):
    ensure_runtime_dirs(config)
    state_file = resolve_path(config["state_file"])
    if not state_file.exists():
        state_file.write_text("", encoding="utf-8")

    queue_file = resolve_path(config["queue_file"])
    if not queue_file.exists():
        queue_file.write_text(
            "# One source per line. Blank lines and # comments are ignored.\n"
            "# https://www.bilibili.com/video/BVxxxx\n"
            "# https://mp.weixin.qq.com/s/xxxx\n",
            encoding="utf-8",
        )


def quickstart_step(name, status, detail, action=""):
    return {"name": name, "status": status, "detail": detail, "action": action}


def status_icon(status):
    return {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "•")


def validate_example_outputs(schema_v1=False):
    examples = ROOT / "examples" / "outputs"
    problems = []
    files = sorted(validate_outputs.iter_markdown([str(examples)]))
    for path in files:
        for problem in validate_outputs.validate_file(path, require_schema_v1=schema_v1):
            if problem["level"] == "error":
                problems.append(f"{Path(path).name}: {problem['message']}")
    return files, problems


def check_platform_definitions():
    results = platform_health.run_checks(
        platform_health.DEFAULT_PLATFORM_DIR,
        platform_health.DEFAULT_TEMPLATE_DIR,
        platform_health.ROOT,
    )
    errors = []
    for item in results:
        for error in item.get("errors", []):
            errors.append(f"{item.get('id')}: {error}")
    return results, errors


def check_example_vault_index():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "quickstart-vault.sqlite"
        result = vault_index.index_vault(ROOT / "examples" / "outputs", db_path=db)
        rows = vault_index.search(db_path=db, query="样例", limit=2)
        semantic_rows = vault_index.semantic_search(db_path=db, query="内容策略", limit=2)
        stats = vault_index.stats(db_path=db)
    if result["notes"] < 1:
        raise RuntimeError("examples/outputs has no notes to index")
    if not rows:
        raise RuntimeError("sample search returned no notes")
    if not semantic_rows:
        raise RuntimeError("sample semantic search returned no notes")
    return result, stats


def mcp_ready():
    try:
        return importlib.util.find_spec("mcp.server.fastmcp") is not None
    except (ModuleNotFoundError, ImportError, ValueError):
        return False


def quickstart_report_lines(steps):
    lines = [
        "# Chubby Quickstart Report",
        "",
        f"Generated at: `{now_iso()}`",
        "",
        "| status | check | detail | next |",
        "|---|---|---|---|",
    ]
    for step in steps:
        lines.append(
            "| "
            + " | ".join(
                [
                    status_icon(step["status"]),
                    escape_cell(step["name"]),
                    escape_cell(step["detail"]),
                    escape_cell(step.get("action", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Next Commands",
            "",
            "```bash",
            "python3 tools/chubby.py ingest \"https://x.com/user/status/123\" --dry-run",
            "python3 tools/chubby.py status --latest",
            "python3 tools/vault_index.py index /path/to/your-vault",
            "VAULT_DIR=/path/to/your-vault python3 knowledge-base-management/scripts/mcp_server.py",
            "```",
            "",
        ]
    )
    return lines


def write_quickstart_report(path, steps):
    path = resolve_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(quickstart_report_lines(steps)), encoding="utf-8")
    return path


def ephemeral_quickstart_config(tmpdir):
    config = dict(DEFAULT_CONFIG)
    config.update(
        {
            "output_dir": str(Path(tmpdir) / "output"),
            "vault_dir": "",
            "state_file": str(Path(tmpdir) / "runs.jsonl"),
            "report_dir": str(Path(tmpdir) / "reports"),
            "queue_file": str(Path(tmpdir) / "inbox" / "links.txt"),
            "_config_path": str(Path(tmpdir) / "chubby.yaml"),
            "_config_exists": False,
        }
    )
    return config


def run_quickstart(args, config):
    steps = []

    if args.ephemeral:
        steps.append(
            quickstart_step("初始化配置", "ok", f"使用临时配置 {config['_config_path']}")
        )
    elif not config["_config_exists"] or args.force_init:
        write_default_config(resolve_path(config["_config_path"]))
        config = load_config(config["_config_path"])
        steps.append(
            quickstart_step("初始化配置", "ok", f"已准备 {config['_config_path']}")
        )
    else:
        steps.append(
            quickstart_step("初始化配置", "ok", f"使用已有 {config['_config_path']}")
        )

    prepare_runtime_files(config)
    steps.append(
        quickstart_step(
            "运行目录",
            "ok",
            f"state={config['state_file']}, report={config['report_dir']}, queue={config['queue_file']}",
        )
    )

    dry_args = argparse.Namespace(
        output=None,
        skill=None,
        vault="",
        enrich=False,
        dry_run=True,
        extra=[],
    )
    record = run_ingest_source(QUICKSTART_SOURCE, dry_args, config, batch_id=make_run_id())
    if not args.no_state:
        append_record(config, record)
        write_report(config, [record], "quickstart dry-run")
    if record["status"] == "dry_run":
        steps.append(
            quickstart_step(
                "示例采集 dry-run",
                "ok",
                f"{QUICKSTART_SOURCE} -> {record.get('skill')}",
                "换成真实链接后去掉 --dry-run",
            )
        )
    else:
        steps.append(
            quickstart_step(
                "示例采集 dry-run",
                "fail",
                record.get("error") or "dry-run failed",
                "检查 tools/chubby_ingest.py",
            )
        )

    _, base_errors = validate_example_outputs(schema_v1=False)
    _, schema_errors = validate_example_outputs(schema_v1=True)
    output_errors = base_errors + schema_errors
    if output_errors:
        steps.append(
            quickstart_step(
                "示例输出校验",
                "fail",
                "; ".join(output_errors[:3]),
                "运行 python3 tools/validate_outputs.py examples/outputs --schema-v1",
            )
        )
    else:
        steps.append(quickstart_step("示例输出校验", "ok", "examples/outputs 通过基础与 schema v1 校验"))

    platform_results, platform_errors = check_platform_definitions()
    if platform_errors:
        steps.append(
            quickstart_step(
                "平台定义",
                "fail",
                "; ".join(platform_errors[:3]),
                "运行 python3 tools/platform_health.py --check",
            )
        )
    else:
        steps.append(quickstart_step("平台定义", "ok", f"{len(platform_results)} 个平台定义可用"))

    try:
        index_result, index_stats = check_example_vault_index()
        steps.append(
            quickstart_step(
                "知识库索引",
                "ok",
                f"示例 vault 索引 {index_result['notes']} 篇，平台 {len(index_stats['platforms'])} 类，semantic-lite 可用",
            )
        )
    except Exception as exc:
        steps.append(
            quickstart_step(
                "知识库索引",
                "fail",
                str(exc),
                "运行 python3 tools/vault_index.py index examples/outputs",
            )
        )

    if mcp_ready():
        steps.append(quickstart_step("MCP 依赖", "ok", "兼容 SDK 可导入；真实握手请运行 python3 tools/mcp_smoke.py"))
    else:
        steps.append(
            quickstart_step(
                "MCP 依赖",
                "warn",
                "缺少兼容 MCP SDK；不影响 CLI 和索引",
                "python3 -m pip install -r knowledge-base-management/requirements-mcp.txt",
            )
        )

    report_path = write_quickstart_report(args.report, steps)
    for step in steps:
        print(f"{status_icon(step['status'])} {step['name']}: {step['detail']}")
        if step.get("action"):
            print(f"   下一步：{step['action']}")
    print(f"🧾 Quickstart 报告：{report_path}")
    return 1 if any(step["status"] == "fail" for step in steps) else 0


def command_quickstart(args, config):
    if args.ephemeral:
        with tempfile.TemporaryDirectory() as tmpdir:
            if not args.report:
                stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
                args.report = str(Path(tempfile.gettempdir()) / f"chubby-quickstart-{stamp}.md")
            config = ephemeral_quickstart_config(tmpdir)
            return run_quickstart(args, config)
    if not args.report:
        args.report = ".chubby/quickstart.md"
    return run_quickstart(args, config)


def add_ingest_options(parser):
    parser.add_argument("--output", "-o", help="Working output directory")
    parser.add_argument("--skill", choices=sorted(chubby_ingest.SKILL_COMMANDS), help="Override platform")
    parser.add_argument("--vault", help="Copy final Markdown and assets into this vault/inbox")
    parser.set_defaults(enrich=None)
    parser.add_argument("--enrich", dest="enrich", action="store_true", help="Run content-enrich")
    parser.add_argument("--no-enrich", dest="enrich", action="store_false", help="Disable configured enrich")
    parser.add_argument("--dry-run", action="store_true", help="Print matching skill commands only")
    parser.add_argument("--refresh", action="store_true", help="Capture again, preserving previous artifacts")
    parser.add_argument("--timeout", type=int, help="Ingest timeout in seconds; 0 disables the limit")


def build_parser():
    parser = argparse.ArgumentParser(description="Chubby Skills pipeline CLI")
    parser.add_argument("--config", help="Path to chubby.yaml")
    parser.add_argument("--version", action="version", version=f"chubbyskills {read_version()}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create chubby.yaml and runtime directories")
    init.add_argument("--force", action="store_true", help="Overwrite existing config")
    init.add_argument("--vault", help="Vault root; captures go to its 00_Inbox directory")

    doctor = sub.add_parser("doctor", help="Show config and dependency health")
    doctor.set_defaults(handler=command_doctor)
    doctor.add_argument("--platform", choices=sorted(chubby_ingest.SKILL_COMMANDS))
    doctor.add_argument("--provider", choices=["local", "atlas", "muapi"], help="Podcast provider to check")

    quickstart = sub.add_parser("quickstart", help="Run the first-use offline acceptance flow")
    quickstart.add_argument("--force-init", action="store_true", help="Overwrite chubby.yaml before checks")
    quickstart.add_argument("--no-state", action="store_true", help="Do not append the dry-run record")
    quickstart.add_argument("--report", help="Quickstart report path")
    quickstart.add_argument("--ephemeral", action="store_true", help="Use a temporary workspace for CI/tests")

    ingest = sub.add_parser("ingest", help="Ingest one source and record state")
    ingest.add_argument("source", help="URL, BV id, local audio, or article PDF")
    add_ingest_options(ingest)

    document = sub.add_parser("import", help="Import local Markdown, text or text-based PDF into the same capture pipeline")
    document.add_argument("source", help="Local .md, .markdown, .txt or .pdf file")
    document.add_argument("--source-url", help="Original HTTP(S) source of the imported document")
    add_ingest_options(document)

    run = sub.add_parser("run", help="Run a queue or explicit list of sources")
    run.add_argument("sources", nargs="*", help="Optional sources; defaults to queue_file")
    run.add_argument("--queue", help="Queue file, one source per line")
    run.add_argument("--limit", type=int, help="Process at most N sources")
    add_ingest_options(run)

    status = sub.add_parser("status", help="Show persisted run state")
    status.add_argument("--limit", type=int, default=10, help="Rows to print")
    status.add_argument("--failed", action="store_true", help="Only show failures")
    status.add_argument("--latest", action="store_true", help="Only show latest record per source")

    retry = sub.add_parser("retry", help="Retry failed runs")
    retry.add_argument("--run-id", help="Retry a specific run_id")
    retry.add_argument("--all-failed", action="store_true", help="Retry all latest failed sources")
    retry.add_argument("--source", help="Resupply a source URL whose credentials were redacted")
    add_ingest_options(retry)

    search = sub.add_parser("search", help="Sync the vault index and search collected notes")
    search.add_argument("query")
    search.add_argument("--mode", choices=["keyword", "lite"], default="keyword")
    search.add_argument("--tag")
    search.add_argument("--json", action="store_true")

    brief = sub.add_parser("brief", help="Build a local source-backed evidence brief")
    brief.add_argument("--topic", required=True)
    brief.add_argument("--output")
    brief.add_argument("--force", action="store_true", help="Explicitly replace existing brief outputs")
    for command in (search, brief):
        command.add_argument("--vault", help="Vault root directory")
        command.add_argument("--db", help="Override SQLite index path")
        command.add_argument("--platform")
        command.add_argument("--limit", type=int, default=5 if command is brief else 10)

    return parser


def extract_config_arg(argv):
    raw = list(sys.argv[1:] if argv is None else argv)
    cleaned = []
    config_path = None
    i = 0
    while i < len(raw):
        item = raw[i]
        if item == "--config":
            if i + 1 >= len(raw):
                raise ValueError("--config requires a path")
            config_path = raw[i + 1]
            i += 2
            continue
        if item.startswith("--config="):
            config_path = item.split("=", 1)[1]
            i += 1
            continue
        cleaned.append(item)
        i += 1
    return cleaned, config_path


def main(argv=None):
    parser = build_parser()
    try:
        cleaned_argv, config_path = extract_config_arg(argv)
    except ValueError as exc:
        parser.error(str(exc))
    args, extra = parser.parse_known_args(cleaned_argv)
    if config_path:
        args.config = config_path
    if extra and args.command not in {"ingest", "run", "retry"}:
        parser.error("unrecognized arguments: " + " ".join(extra))
    args.extra = extra
    if args.command == "import":
        if args.skill and args.skill != "document":
            parser.error("import only accepts the document skill")
        args.skill = "document"
        if args.source_url:
            args.extra.extend(["--source-url", args.source_url])
    config = load_config(args.config)

    if args.command == "init":
        return init_workspace(args)
    if args.command == "doctor":
        return command_doctor(args, config)
    if args.command == "quickstart":
        return command_quickstart(args, config)
    if args.command in {"ingest", "import"}:
        return command_ingest(args, config)
    if args.command == "run":
        return command_run(args, config)
    if args.command == "status":
        return command_status(args, config)
    if args.command == "retry":
        return command_retry(args, config)
    if args.command == "search":
        return command_search(args, config)
    if args.command == "brief":
        return command_brief(args, config)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
