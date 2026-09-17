#!/usr/bin/env python3
"""
One-command ingest workflow for chubbyskills.

It detects the input platform, runs the matching skill script, optionally enriches
the generated Markdown, and can copy the result into an Obsidian vault directory.

Usage:
    python3 tools/chubby_ingest.py "https://www.bilibili.com/video/BV..." -o output/
    python3 tools/chubby_ingest.py "https://x.com/user/status/123" --enrich --vault ~/Vault/00_Inbox
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote_plus, urlencode, urlparse, urlunparse


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from tools import source_identity
except ModuleNotFoundError:
    sys.path.insert(0, ROOT)
    from tools import source_identity

# 静态映射作为兜底：正常情况下从 platforms/*.yaml 动态构建（见 load_skill_commands）
STATIC_SKILL_COMMANDS = {
    "bilibili": ["bilibili-transcribe", "scripts", "transcribe.py"],
    "douyin": ["douyin-transcribe", "scripts", "transcribe.py"],
    "tiktok": ["tiktok-transcribe", "scripts", "transcribe.py"],
    "weibo": ["weibo-transcribe", "scripts", "transcribe.py"],
    "wechat": ["wechat-article-ingest", "scripts", "fetch_article.py"],
    "x": ["x-ingest", "scripts", "fetch_tweet.py"],
    "xiaohongshu": ["xiaohongshu-ingest", "scripts", "fetch_note.py"],
    "youtube": ["youtube-transcribe", "scripts", "transcribe.py"],
    "zhihu": ["zhihu-transcribe", "scripts", "transcribe.py"],
    "podcast": ["podcast-transcribe", "scripts", "transcribe.py"],
}


def load_skill_commands(platform_dir=None):
    """从 platforms/*.yaml 构建 {id: [skill_dir, script_parts...]}，消除双事实来源。

    新增平台只需写一份 platforms/<id>.yaml，路由自动生效；
    解析失败时回退到静态映射，保证旧环境可用。
    """
    commands = {}
    try:
        from tools import platform_health
    except ImportError:
        platform_health = None
    if platform_health is not None:
        try:
            directory = platform_dir or platform_health.DEFAULT_PLATFORM_DIR
            for platform in platform_health.load_records(directory):
                pid = platform.get("id")
                skill = platform.get("skill")
                script = platform.get("script")
                if pid and skill and script:
                    commands[pid] = [skill] + str(script).split("/")
        except Exception:
            commands = {}
    return commands or dict(STATIC_SKILL_COMMANDS)


SKILL_COMMANDS = load_skill_commands()


REDACTED = "[REDACTED]"
SAFE_CREDENTIAL_REFERENCES = {"--cookies", "--cookie-file", "--cookies-from-browser"}


def sensitive_option(option):
    key = option.split("=", 1)[0].lower()
    return key not in SAFE_CREDENTIAL_REFERENCES and bool(
        re.search(r"(?:key|token|secret|password|passwd|authorization|cookie|header|credential|proxy)", key)
    )


def redact_url(value):
    """Return a log-safe URL and credential values that must also be scrubbed."""
    parsed = urlparse(str(value))
    if parsed.scheme not in {"http", "https"}:
        return str(value), []
    secrets = []
    netloc = parsed.netloc
    if "@" in netloc:
        credentials, host = netloc.rsplit("@", 1)
        secrets.append(credentials)
        secrets.extend(part for part in credentials.split(":") if part)
        netloc = REDACTED + "@" + host
    pairs = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        if sensitive_option(key) or key.lower() in {"sign", "signature", "auth"}:
            secrets.append(item)
            item = REDACTED
        pairs.append((key, item))
    for pair in parsed.query.split("&"):
        raw_key, separator, raw_value = pair.partition("=")
        key = unquote_plus(raw_key)
        if separator and (sensitive_option(key) or key.lower() in {"sign", "signature", "auth"}):
            secrets.append(raw_value)
    if not secrets:
        return str(value), []
    return urlunparse(parsed._replace(netloc=netloc, query=urlencode(pairs))), secrets


def redact_arguments(arguments):
    safe, required, secrets = [], [], []
    index = 0
    previous_option = "--source"
    while index < len(arguments):
        value = str(arguments[index])
        flag, equal, inline = value.partition("=")
        if flag.startswith("-") and sensitive_option(flag):
            required.append(flag)
            if equal:
                secrets.append(inline)
                safe.append(flag + "=" + REDACTED)
            else:
                safe.append(flag)
                if index + 1 < len(arguments) and not str(arguments[index + 1]).startswith("--"):
                    index += 1
                    secrets.append(str(arguments[index]))
                    safe.append(REDACTED)
        else:
            is_inline_option = flag.startswith("-") and bool(equal)
            cleaned, embedded = redact_url(inline if is_inline_option else value)
            safe.append(flag + "=" + cleaned if is_inline_option else cleaned)
            secrets.extend(embedded)
            if embedded:
                required.append(flag if is_inline_option else previous_option)
        if flag.startswith("-"):
            previous_option = flag
        index += 1
    return safe, sorted(set(required)), [item for item in secrets if item]


def redact_text(value, secrets=()):
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value or "")
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def detect_skill(source):
    parsed = urlparse(source if "://" in source else "")
    host = parsed.netloc.lower()
    lower = source.lower()

    if lower.startswith("bv") or "bilibili.com" in host:
        return "bilibili"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin"
    if "tiktok.com" in host:
        return "tiktok"
    if "weibo.com" in host or "m.weibo.cn" in host:
        return "weibo"
    if "zhihu.com" in host:
        return "zhihu"
    if "mp.weixin.qq.com" in host:
        return "wechat"
    if host in {"x.com", "twitter.com", "mobile.twitter.com"} or "/status/" in lower:
        return "x"
    if "xiaohongshu.com" in host or "xhslink.com" in host:
        return "xiaohongshu"
    if lower.endswith(".pdf") and os.path.exists(source):
        return "wechat"
    if os.path.exists(source) or lower.endswith((".mp3", ".m4a", ".wav", ".ogg", ".aac")):
        return "podcast"
    return None


def script_path(skill):
    return os.path.join(ROOT, *SKILL_COMMANDS[skill])


def run_command(cmd, dry_run=False):
    safe_command, _, secrets = redact_arguments(cmd)
    print("▶ " + " ".join(safe_command), file=sys.stderr)
    if dry_run:
        return ""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stderr:
        # Adapter paths are temporary. Only the published paths below are outputs.
        for line in result.stderr.splitlines():
            if not re.match(r"^\s*(?:✅ Saved(?: fallback)?:|Output:|📥 已入库：)", line):
                print(redact_text(line, secrets), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(redact_text(result.stdout.strip(), secrets) or f"command failed: {' '.join(safe_command)}")
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def publish_bundle(markdown_path, destination, source=None):
    """Publish a Markdown/assets pair without replacing any existing artifact."""
    original = Path(markdown_path)
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    stem = original.stem
    if source is not None:
        stem += "--" + source_identity.source_digest(source, base_dir=ROOT)
    original_assets = original.with_suffix(".assets")
    content = original.read_text(encoding="utf-8")
    revision = 1
    while True:
        suffix = "" if revision == 1 else f"--{revision}"
        target = destination / f"{stem}{suffix}.md"
        assets = target.with_suffix(".assets")
        revision += 1
        if assets.exists():
            continue
        try:
            stream = target.open("x", encoding="utf-8")
            break
        except FileExistsError:
            continue
    copied_assets = False
    try:
        if original_assets.is_dir():
            shutil.copytree(original_assets, assets)
            copied_assets = True
            content = content.replace(original_assets.name + "/", assets.name + "/")
            content = content.replace(quote(original_assets.name) + "/", quote(assets.name) + "/")
        with stream:
            stream.write(content)
    except Exception:
        stream.close()
        target.unlink(missing_ok=True)
        if copied_assets:
            shutil.rmtree(assets)
        raise
    return str(target)


def copy_into_vault(markdown_path, vault_dir):
    original = Path(markdown_path).resolve()
    destination = Path(vault_dir).expanduser().resolve()
    if original.parent == destination:
        return str(markdown_path)
    return publish_bundle(original, destination)


def main():
    parser = argparse.ArgumentParser(description="Detect platform and run the matching chubbyskills workflow")
    parser.add_argument("source", help="URL, BV id, local audio file, or article PDF")
    parser.add_argument("--output", "-o", default="output", help="Working output directory")
    parser.add_argument("--skill", choices=sorted(SKILL_COMMANDS), help="Override platform detection")
    parser.add_argument("--enrich", action="store_true", help="Run content-enrich after capture")
    parser.add_argument("--vault", help="Copy final Markdown and assets into this vault/inbox directory")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")
    args, extra = parser.parse_known_args()

    skill = args.skill or detect_skill(args.source)
    if not skill:
        print("❌ 无法识别输入平台，请用 --skill 指定。", file=sys.stderr)
        return 2

    try:
        with tempfile.TemporaryDirectory(prefix="chubby-ingest-") as stage:
            adapter_output = args.output if args.dry_run else stage
            if skill in {"douyin", "podcast"}:
                cmd = [sys.executable, script_path(skill), args.source, adapter_output]
            else:
                cmd = [sys.executable, script_path(skill), args.source, "--output", adapter_output]
            cmd.extend(extra)
            staged_path = run_command(cmd, dry_run=args.dry_run)
            if args.dry_run:
                return 0
            if not staged_path or not Path(staged_path).is_file():
                raise RuntimeError(f"skill 未返回有效输出路径：{staged_path}")
            if not Path(staged_path).resolve().is_relative_to(Path(stage).resolve()):
                raise RuntimeError("skill 输出不在本次暂存目录内")
            if args.enrich:
                enrich_script = os.path.join(ROOT, "content-enrich", "scripts", "enrich.py")
                run_command([sys.executable, enrich_script, staged_path, "--force"], dry_run=False)
            output_path = publish_bundle(staged_path, args.output, source=args.source)
        print(f"Output: {output_path}", file=sys.stderr)
        final_path = output_path

        if args.vault:
            final_path = copy_into_vault(output_path, os.path.expanduser(args.vault))
            print(f"📥 已入库：{final_path}", file=sys.stderr)

        print(final_path)
        return 0
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
