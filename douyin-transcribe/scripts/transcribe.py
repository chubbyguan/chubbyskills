#!/usr/bin/env python3
"""
抖音视频一键转录工具

用法：
    python transcribe.py "https://v.douyin.com/xxxxx"
    python transcribe.py "https://www.douyin.com/video/1234567890"
"""

import os
import shutil
import sys
import tempfile

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = SKILL_ROOT if os.path.isdir(os.path.join(SKILL_ROOT, "chubby_common")) else os.path.dirname(SKILL_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from chubby_common import funasr, markdown

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from download_douyin_audio import extract_video_id, download_audio


def clean_title(title: str) -> str:
    """清理标题：去掉重复的《》后缀。"""
    clean = title.split("《")[0] if "《" in title and title.count("《") > 1 else title
    if clean.count("《") > 1:
        first_end = clean.find("》")
        if first_end > 0:
            clean = clean[: first_end + 1]
    return clean


def transcribe(audio_path: str, output_path: str, title: str, source: str = ""):
    """Transcribe audio using SenseVoice-Small and save as Markdown."""
    clean = clean_title(title)
    text, elapsed = funasr.transcribe(audio_path, language="zh")

    body = markdown.note_markdown(
        clean,
        f"> 转录引擎：SenseVoice-Small | 耗时：{elapsed:.0f}秒\n\n{text}",
        {
            "type": "note",
            "platform": "douyin",
            "tags": ["抖音"],
            "source": source,
            "author": "",
            "transcriber": "SenseVoice-Small",
        },
    )

    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(body)

    return elapsed, len(text)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <douyin_url> [output_dir]")
        print("\nExample:")
        print(f'  {sys.argv[0]} "https://v.douyin.com/xxxxx"')
        print(f'  {sys.argv[0]} "https://v.douyin.com/xxxxx" ./output')
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    # Step 1: Extract video ID and download audio
    print("=" * 50, file=sys.stderr)
    print("Step 1: Downloading audio...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    tmpdir = None
    try:
        video_id = extract_video_id(url)
        tmpdir = tempfile.mkdtemp(prefix="dyt-")

        audio_path, title = download_audio(video_id, tmpdir)

        # Step 2: Transcribe
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 2: Transcribing...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        # Generate output filename
        safe_title = markdown.sanitize_filename(title, "抖音视频")
        output_filename = f"{safe_title}.md"
        output_path = os.path.join(output_dir, output_filename)

        elapsed, chars = transcribe(audio_path, output_path, title, url)

        print("\n" + "=" * 50, file=sys.stderr)
        print("✅ Done!", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print(f"  Title: {title}", file=sys.stderr)
        print(f"  Time: {elapsed:.0f}s", file=sys.stderr)
        print(f"  Chars: {chars}", file=sys.stderr)
        print(f"  Output: {output_path}", file=sys.stderr)

        # Print output path to stdout for scripting
        print(output_path)

    except (RuntimeError, ValueError) as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Cleanup
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
