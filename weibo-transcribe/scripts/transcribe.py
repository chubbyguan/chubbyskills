#!/usr/bin/env python3
"""
微博视频一键转录工具

用法：
    python transcribe.py "https://weibo.com/xxxxx"
    python transcribe.py "https://m.weibo.cn/xxxxx" -o ./out

特点：
    - 同时支持 weibo.com（桌面）和 m.weibo.cn（移动）链接
    - 移动端 UA + Referer 伪装，规避微博常见的反爬拦截
    - 下载失败自动重试
"""

import argparse
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from chubby_common.config import PlatformConfig
from chubby_common import funasr, markdown, ytdlp

# 微博对移动端 UA 更宽容，桌面 UA 常被拦
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)

CFG = PlatformConfig(
    id="weibo",
    name="微博",
    tag="微博",
    default_title="微博视频",
    language="zh",  # 微博以中文为主
    ua=MOBILE_UA,
    referer="https://weibo.com/",
)


def main():
    parser = argparse.ArgumentParser(description=f"{CFG.name} 视频转录")
    parser.add_argument("url", help=f"{CFG.name} 视频链接")
    parser.add_argument("output", nargs="?", default=".", help="输出目录（位置参数，兼容旧用法）")
    parser.add_argument("--output", "-o", dest="output_opt", help="输出目录")
    args = parser.parse_args()
    output_dir = args.output_opt or args.output

    try:
        print("=" * 50, file=sys.stderr)
        print(f"Step 1: Getting {CFG.name} video info...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        title = ytdlp.get_title(CFG, args.url)
        print(f"  📺 Title: {title}", file=sys.stderr)

        tmpdir = tempfile.mkdtemp(prefix=f"{CFG.tmp_prefix}-")
        try:
            print("\n" + "=" * 50, file=sys.stderr)
            print("Step 2: Downloading audio...", file=sys.stderr)
            print("=" * 50, file=sys.stderr)
            audio_path = ytdlp.download_audio(CFG, args.url, tmpdir)

            print("\n" + "=" * 50, file=sys.stderr)
            print("Step 3: Transcribing...", file=sys.stderr)
            print("=" * 50, file=sys.stderr)
            text, _ = funasr.transcribe(audio_path, language=CFG.language)

            body = markdown.note_markdown(
                title,
                text,
                {
                    "type": "note",
                    "platform": CFG.id,
                    "tags": f"[{CFG.tag}]",
                    "source": args.url,
                    "author": "",
                    "transcriber": "SenseVoice-Small",
                },
            )
            safe_title = markdown.sanitize_filename(title, CFG.default_title)
            output_path = os.path.join(output_dir, f"{safe_title}.md")
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(body)

            print(f"\n✅ Saved: {output_path}", file=sys.stderr)
            print(output_path)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    except RuntimeError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
