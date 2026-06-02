#!/usr/bin/env python3
"""
B 站视频一键转录工具

用法：
    python transcribe.py "https://www.bilibili.com/video/BV1rrQGBeEen/"
    python transcribe.py "BV1rrQGBeEen"
"""

import sys
import os
import re
import time
import subprocess
import tempfile
import shutil
from datetime import datetime


MOBILE_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def extract_bvid(url: str) -> str:
    """Extract BV ID from Bilibili URL."""
    # Full URL
    m = re.search(r'(BV[\w]+)', url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract BV ID from: {url}")


def download_audio(bvid: str, output_dir: str) -> tuple:
    """Download audio from Bilibili video. Returns (audio_path, title)."""
    url = f"https://www.bilibili.com/video/{bvid}/"
    
    # First get title
    print(f"Getting video info: {bvid}...", file=sys.stderr)
    result = subprocess.run(
        ["yt-dlp", "--get-title", "--no-check-certificates",
         "--user-agent", MOBILE_UA,
         "--referer", "https://www.bilibili.com",
         url],
        capture_output=True, text=True, timeout=60
    )
    title = result.stdout.strip() or bvid
    
    # Download audio
    safe_title = "".join(c for c in title if c.isalnum() or c in "-_ 《》").strip()
    safe_title = safe_title[:50]
    audio_path = os.path.join(output_dir, f"{safe_title}.mp3")
    
    print(f"Downloading: {title[:60]}...", file=sys.stderr)
    subprocess.run(
        ["yt-dlp",
         "--extract-audio", "--audio-format", "mp3", "--audio-quality", "128K",
         "-o", audio_path,
         "--no-check-certificates",
         "--user-agent", MOBILE_UA,
         "--referer", "https://www.bilibili.com",
         url],
        timeout=600, check=True
    )
    
    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  Audio: {size_mb:.1f} MB", file=sys.stderr)
    
    return audio_path, title


def transcribe_audio(audio_path: str, output_path: str, title: str):
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

    # Generate Markdown
    now = datetime.now().strftime("%Y-%m-%d")
    markdown = f"""---
title: {title}
type: note
tags: [B站]
created: {now}
source: bilibili
transcriber: SenseVoice-Small
---

# {title}

> 转录引擎：SenseVoice-Small | 耗时：{elapsed:.0f}秒

{text}"""

    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return elapsed, len(text)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <bilibili_url_or_bvid> [output_dir]")
        print(f"\nExample:")
        print(f'  {sys.argv[0]} "https://www.bilibili.com/video/BV1rrQGBeEen/"')
        print(f'  {sys.argv[0]} "BV1rrQGBeEen" ./output')
        sys.exit(1)

    source = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    # Step 1: Extract BV ID and download audio
    print("=" * 50, file=sys.stderr)
    print("Step 1: Downloading audio...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    bvid = extract_bvid(source)
    tmpdir = tempfile.mkdtemp(prefix="bilibili-")

    try:
        audio_path, title = download_audio(bvid, tmpdir)

        # Step 2: Transcribe
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 2: Transcribing...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        # Generate output filename
        safe_title = "".join(c for c in title if c.isalnum() or c in "-_ 《》").strip()
        safe_title = safe_title[:50]
        output_filename = f"{safe_title}.md"
        output_path = os.path.join(output_dir, output_filename)

        elapsed, chars = transcribe_audio(audio_path, output_path, title)

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
