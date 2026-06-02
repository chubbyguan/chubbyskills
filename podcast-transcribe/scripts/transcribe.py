#!/usr/bin/env python3
"""
播客一键转录工具

用法：
    python transcribe.py "https://www.xiaoyuzhoufm.com/episode/xxxxx"
    python transcribe.py "https://www.ximalaya.com/xxxxx"
    python transcribe.py "path/to/audio.m4a"
"""

import sys
import os
import time
import subprocess
import tempfile
import shutil
import re
from datetime import datetime


def download_audio(url: str, output_dir: str) -> tuple:
    """Download audio from URL. Returns (audio_path, title)."""
    # Extract title from URL or use default
    title = "Podcast Episode"
    
    # Try to get title from page
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30", url],
            capture_output=True, text=True, timeout=35
        )
        # Try to extract title from HTML
        import re
        title_match = re.search(r'<title>(.*?)</title>', result.stdout, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # Clean up title
            title = title.split('|')[0].split('-')[0].strip()
    except:
        pass
    
    # Generate filename
    safe_title = "".join(c for c in title if c.isalnum() or c in "-_ ").strip()
    safe_title = safe_title[:50]
    
    # Determine file extension from URL
    ext = ".m4a"
    if ".mp3" in url:
        ext = ".mp3"
    elif ".wav" in url:
        ext = ".wav"
    
    audio_path = os.path.join(output_dir, f"{safe_title}{ext}")
    
    # Download
    print(f"Downloading: {title[:60]}...", file=sys.stderr)
    subprocess.run(
        ["curl", "-L", "-o", audio_path, "--max-time", "1800", "-s", url],
        timeout=1900, check=True
    )
    
    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  Audio: {size_mb:.1f} MB", file=sys.stderr)
    
    return audio_path, title


def transcribe_audio(audio_path: str, output_path: str, title: str):
    """Transcribe audio using faster-whisper and save as Markdown."""
    from faster_whisper import WhisperModel

    print("Loading faster-whisper model...", file=sys.stderr)
    model = WhisperModel('small', device='cpu', compute_type='int8')
    print("Model loaded. Transcribing...", file=sys.stderr)

    start = time.time()
    segments, info = model.transcribe(
        audio_path,
        language='zh',
        beam_size=5,
        vad_filter=True,
    )
    
    # Collect segments
    text_segments = []
    for segment in segments:
        ts = "[{:6.1f}s -> {:6.1f}s] ".format(segment.start, segment.end)
        text_segments.append(ts + segment.text.strip())
    
    elapsed = time.time() - start

    # Generate Markdown
    now = datetime.now().strftime("%Y-%m-%d")
    text = "\n".join(text_segments)
    
    markdown = f"""---
title: {title}
type: note
tags: [播客]
created: {now}
source: podcast
transcriber: faster-whisper-small
---

# {title}

> 转录引擎：faster-whisper small | 耗时：{elapsed:.0f}秒 | 段数：{len(text_segments)}

{text}"""

    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return elapsed, len(text_segments)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <audio_url_or_path> [output_dir]")
        print(f"\nExample:")
        print(f'  {sys.argv[0]} "https://www.xiaoyuzhoufm.com/episode/xxxxx"')
        print(f'  {sys.argv[0]} "path/to/audio.m4a" ./output')
        sys.exit(1)

    source = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    # Step 1: Get audio
    print("=" * 50, file=sys.stderr)
    print("Step 1: Getting audio...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    tmpdir = tempfile.mkdtemp(prefix="podcast-")

    try:
        if os.path.exists(source):
            # Local file
            audio_path = source
            title = os.path.splitext(os.path.basename(source))[0]
        else:
            # URL
            audio_path, title = download_audio(source, tmpdir)

        # Step 2: Transcribe
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 2: Transcribing...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        # Generate output filename
        safe_title = "".join(c for c in title if c.isalnum() or c in "-_ ").strip()
        safe_title = safe_title[:50]
        output_filename = f"{safe_title}.md"
        output_path = os.path.join(output_dir, output_filename)

        elapsed, seg_count = transcribe_audio(audio_path, output_path, title)

        print("\n" + "=" * 50, file=sys.stderr)
        print("✅ Done!", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print(f"  Title: {title}", file=sys.stderr)
        print(f"  Time: {elapsed:.0f}s", file=sys.stderr)
        print(f"  Segments: {seg_count}", file=sys.stderr)
        print(f"  Output: {output_path}", file=sys.stderr)

        # Print output path to stdout for scripting
        print(output_path)

    finally:
        # Cleanup
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
