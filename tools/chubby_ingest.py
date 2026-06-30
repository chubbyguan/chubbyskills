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
import shutil
import subprocess
import sys
from urllib.parse import urlparse


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_COMMANDS = {
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
    print("▶ " + " ".join(cmd), file=sys.stderr)
    if dry_run:
        return ""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or f"command failed: {' '.join(cmd)}")
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def copy_into_vault(markdown_path, vault_dir):
    os.makedirs(vault_dir, exist_ok=True)
    target = os.path.join(vault_dir, os.path.basename(markdown_path))
    if os.path.abspath(markdown_path) != os.path.abspath(target):
        shutil.copy2(markdown_path, target)

    asset_dir = os.path.splitext(markdown_path)[0] + ".assets"
    if os.path.isdir(asset_dir):
        target_assets = os.path.join(vault_dir, os.path.basename(asset_dir))
        if os.path.abspath(asset_dir) == os.path.abspath(target_assets):
            return target
        if os.path.exists(target_assets):
            shutil.rmtree(target_assets)
        shutil.copytree(asset_dir, target_assets)
    return target


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

    os.makedirs(args.output, exist_ok=True)
    if skill in {"douyin", "podcast"}:
        cmd = [sys.executable, script_path(skill), args.source, args.output]
    else:
        cmd = [sys.executable, script_path(skill), args.source, "--output", args.output]
    cmd.extend(extra)

    try:
        output_path = run_command(cmd, dry_run=args.dry_run)
        if args.dry_run:
            return 0
        if not output_path or not os.path.exists(output_path):
            raise RuntimeError(f"skill 未返回有效输出路径：{output_path}")

        final_path = output_path
        if args.enrich:
            enrich_script = os.path.join(ROOT, "content-enrich", "scripts", "enrich.py")
            run_command([sys.executable, enrich_script, output_path, "--force"], dry_run=False)

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
