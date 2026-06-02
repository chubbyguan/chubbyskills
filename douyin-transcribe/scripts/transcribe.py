#!/usr/bin/env python3
"""
抖音视频一键转录工具

用法：
    python transcribe.py "https://v.douyin.com/xxxxx"
    python transcribe.py "https://www.douyin.com/video/1234567890"
"""

import sys
import os
import time
import tempfile
import shutil
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from download_douyin_audio import extract_video_id, download_audio


def transcribe(audio_path: str, output_path: str, title: str):
    """Transcribe audio using SenseVoice-Small and save as Markdown."""
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    print("Loading SenseVoice-Small model...", file=sys.stderr)
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        trust_remote_code=True,
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
    )
    print("Model loaded. Transcribing...", file=sys.stderr)

    start = time.time()
    result = model.generate(
        input=audio_path,
        language="zh",
        use_itn=True,
        batch_size_s=60
    )
    elapsed = time.time() - start

    # Extract text
    text = ""
    if result and len(result) > 0:
        for r in result:
            if "text" in r:
                text += rich_transcription_postprocess(r["text"]) + "\n\n"

    # Clean title (remove duplicate suffix)
    clean_title = title.split("《")[0] if "《" in title and title.count("《") > 1 else title
    if clean_title.count("《") > 1:
        first_end = clean_title.find("》")
        if first_end > 0:
            clean_title = clean_title[:first_end + 1]

    # Generate Markdown
    now = datetime.now().strftime("%Y-%m-%d")
    markdown = f"""---
title: {clean_title}
type: note
tags: [抖音]
created: {now}
source: 抖音
transcriber: SenseVoice-Small
---

# {clean_title}

> 转录引擎：SenseVoice-Small | 耗时：{elapsed:.0f}秒

{text}"""

    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return elapsed, len(text)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <douyin_url> [output_dir]")
        print(f"\nExample:")
        print(f'  {sys.argv[0]} "https://v.douyin.com/xxxxx"')
        print(f'  {sys.argv[0]} "https://v.douyin.com/xxxxx" ./output')
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    # Step 1: Extract video ID and download audio
    print("=" * 50, file=sys.stderr)
    print("Step 1: Downloading audio...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    video_id = extract_video_id(url)
    tmpdir = tempfile.mkdtemp(prefix="dyt-")

    try:
        audio_path, title = download_audio(video_id, tmpdir)

        # Step 2: Transcribe
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 2: Transcribing...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        # Generate output filename
        safe_title = "".join(c for c in title if c.isalnum() or c in "《》-_ ").strip()
        safe_title = safe_title[:50]  # Limit length
        output_filename = f"{safe_title}.md"
        output_path = os.path.join(output_dir, output_filename)

        elapsed, chars = transcribe(audio_path, output_path, title)

        print("\n" + "=" * 50, file=sys.stderr)
        print("✅ Done!", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print(f"  Title: {title}", file=sys.stderr)
        print(f"  Time: {elapsed:.0f}s", file=sys.stderr)
        print(f"  Chars: {chars}", file=sys.stderr)
        print(f"  Output: {output_path}", file=sys.stderr)

        # Print output path to stdout for scripting
        print(output_path)

    finally:
        # Cleanup
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
