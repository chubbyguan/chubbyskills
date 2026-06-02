#!/usr/bin/env python3
"""
微博视频一键转录工具

用法：
    python transcribe.py "https://weibo.com/xxxxx"
    python transcribe.py "https://m.weibo.cn/xxxxx"
"""

import sys
import os
import re
import time
import subprocess
import tempfile
import shutil
from datetime import datetime


def get_video_info(url: str) -> dict:
    """Get video title."""
    result = subprocess.run(
        ["yt-dlp", "--get-title", "--no-check-certificates", url],
        capture_output=True, text=True, timeout=30
    )
    title = result.stdout.strip() or "微博视频"
    return {'title': title}


def download_audio(url: str, output_dir: str) -> str:
    """Download audio from Weibo."""
    print(f"  ⬇️  Downloading...", file=sys.stderr)
    
    audio_path = os.path.join(output_dir, "audio.mp3")
    subprocess.run(
        ["yt-dlp",
         "--extract-audio", "--audio-format", "mp3", "--audio-quality", "128K",
         "-o", audio_path,
         "--no-check-certificates",
         url],
        timeout=300, check=True
    )
    
    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  ✅ Audio: {size_mb:.1f} MB", file=sys.stderr)
    return audio_path


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using SenseVoice-Small."""
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    print("  🎙️  Loading model...", file=sys.stderr)
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        trust_remote_code=True,
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
    )

    print("  🎙️  Transcribing...", file=sys.stderr)
    start = time.time()
    result = model.generate(input=audio_path, language="zh", use_itn=True, batch_size_s=60)
    elapsed = time.time() - start

    text = ""
    if result and len(result) > 0:
        for r in result:
            if "text" in r:
                text += rich_transcription_postprocess(r["text"]) + "\n\n"

    print(f"  ✅ Done in {elapsed:.1f}s", file=sys.stderr)
    return text.strip()


def sanitize_filename(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', '', name)
    s = re.sub(r'\s+', '-', s)
    return s[:50]


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <weibo_url> [output_dir]")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    print("=" * 50, file=sys.stderr)
    print("Step 1: Getting video info...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    
    info = get_video_info(url)
    title = info['title']
    print(f"  📺 Title: {title}", file=sys.stderr)

    tmpdir = tempfile.mkdtemp(prefix="weibo-")
    try:
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 2: Downloading audio...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        audio_path = download_audio(url, tmpdir)

        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 3: Transcribing...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        text = transcribe_audio(audio_path)

        # Generate Markdown
        now = datetime.now().strftime("%Y-%m-%d")
        markdown = f"""---
title: {title}
type: note
tags: [微博]
created: {now}
source: {url}
transcriber: SenseVoice-Small
---

# {title}

{text}"""

        safe_title = sanitize_filename(title)
        output_path = os.path.join(output_dir, f"{safe_title}.md")
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"\n✅ Saved: {output_path}", file=sys.stderr)
        print(output_path)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
