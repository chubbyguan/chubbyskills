#!/usr/bin/env python3
"""
YouTube batch transcription wrapper.

Input is a plain text file with one YouTube URL per line. Empty lines and lines
starting with # are ignored.

Usage:
    python3 batch_transcribe.py urls.txt -o output/youtube
    python3 batch_transcribe.py urls.txt -o output/youtube --no-translate
"""

import argparse
import os
import subprocess
import sys


def read_sources(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            item = line.strip()
            if item and not item.startswith("#"):
                yield item


def main():
    parser = argparse.ArgumentParser(description="YouTube 批量转录/翻译")
    parser.add_argument("input", help="文本文件：每行一个 YouTube URL")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument("--no-translate", action="store_true", help="英文内容不翻译")
    parser.add_argument("--no-subtitle", action="store_true", help="跳过字幕，强制音频转录")
    parser.add_argument("--stop-on-error", action="store_true", help="遇到失败立即停止")
    args = parser.parse_args()

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcribe.py")
    sources = list(read_sources(args.input))
    os.makedirs(args.output, exist_ok=True)

    print(f"📦 YouTube 批量任务：{len(sources)} 条", file=sys.stderr)
    ok, failed = [], []
    for index, source in enumerate(sources, 1):
        print(f"\n[{index}/{len(sources)}] {source}", file=sys.stderr)
        cmd = [sys.executable, script, source, "--output", args.output]
        if args.no_translate:
            cmd.append("--no-translate")
        if args.no_subtitle:
            cmd.append("--no-subtitle")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        if result.returncode == 0:
            output = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            ok.append(output)
            print(f"  ✅ {output}", file=sys.stderr)
        else:
            failed.append(source)
            print(f"  ❌ 失败：{source}", file=sys.stderr)
            if args.stop_on_error:
                break

    print(f"\n🏁 完成：成功 {len(ok)} 条，失败 {len(failed)} 条", file=sys.stderr)
    for path in ok:
        print(path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
