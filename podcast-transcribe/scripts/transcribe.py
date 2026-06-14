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
    """Download audio from podcast URL. Returns (audio_path, title).

    Supports: direct audio URLs (.mp3/.m4a/.wav), 小宇宙, 喜马拉雅, RSS feeds.
    """
    title = "Podcast Episode"
    audio_url = url

    # If it's already a direct audio link, skip page parsing
    if re.search(r'\.(mp3|m4a|wav|ogg|aac)(\?|$)', url, re.IGNORECASE):
        try:
            head = subprocess.run(
                ["curl", "-sI", "-L", "--max-time", "15", url],
                capture_output=True, text=True, timeout=20
            )
            for line in head.stdout.split('\n'):
                if line.lower().startswith('content-disposition'):
                    m = re.search(r'filename[*]?=["\']?([^"\';\r\n]+)', line)
                    if m:
                        title = m.group(1).strip()
        except Exception:
            pass
    else:
        # Fetch page HTML to extract audio URL and title
        print(f"  Fetching page...", file=sys.stderr)
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", "--max-time", "30", url],
                capture_output=True, text=True, timeout=35
            )
            html = result.stdout
        except Exception as e:
            raise RuntimeError(f"Failed to fetch page: {e}")

        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'\s*[-|—].*$', '', title)  # remove site suffix

        # Try og:audio meta tag (小宇宙、喜马拉雅等常用)
        og_audio = re.search(
            r'<meta\s+(?:property|name)=["\']og:audio["\']\s+content=["\'](.*?)["\']',
            html, re.IGNORECASE
        )
        if og_audio:
            audio_url = og_audio.group(1)
        else:
            # Try <audio> tag src
            audio_tag = re.search(r'<audio[^>]+src=["\'](.*?)["\']', html, re.IGNORECASE)
            if audio_tag:
                audio_url = audio_tag.group(1)
            else:
                # Try JSON-LD or inline JSON with audioUrl / mediaSrc
                json_audio = re.search(
                    r'["\'](?:audioUrl|mediaSrc|enclosure|url)["\']\s*:\s*["\']'
                    r'(https?://[^"\']+\.(?:mp3|m4a|wav|ogg|aac)[^"\']*)["\']',
                    html, re.IGNORECASE
                )
                if json_audio:
                    audio_url = json_audio.group(1)
                else:
                    # Try any .mp3/.m4a URL in the page
                    any_audio = re.search(
                        r'(https?://[^\s"\'<>]+\.(?:mp3|m4a|wav|ogg|aac)(?:\?[^\s"\'<>]*)?)',
                        html, re.IGNORECASE
                    )
                    if any_audio:
                        audio_url = any_audio.group(1)
                    else:
                        raise RuntimeError(
                            "Cannot extract audio URL from page. "
                            "Try passing the direct audio link instead."
                        )

        print(f"  Audio URL: {audio_url[:80]}...", file=sys.stderr)

    # Generate filename
    safe_title = "".join(c for c in title if c.isalnum() or c in "-_ ").strip()
    safe_title = safe_title[:50] or "episode"

    # Determine file extension
    ext = ".m4a"
    url_lower = audio_url.lower()
    if ".mp3" in url_lower:
        ext = ".mp3"
    elif ".wav" in url_lower:
        ext = ".wav"
    elif ".ogg" in url_lower:
        ext = ".ogg"

    audio_path = os.path.join(output_dir, f"{safe_title}{ext}")

    # Download
    print(f"  Downloading: {title[:60]}...", file=sys.stderr)
    subprocess.run(
        ["curl", "-L", "-o", audio_path, "--max-time", "1800", "-s",
         "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
         audio_url],
        timeout=1900, check=True
    )

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb < 0.01:
        os.remove(audio_path)
        raise RuntimeError(
            f"Downloaded file is too small ({size_mb:.2f} MB), "
            "likely not an audio file. Check the URL."
        )
    print(f"  Audio: {size_mb:.1f} MB", file=sys.stderr)

    return audio_path, title


def transcribe_audio(audio_path: str, output_path: str, title: str, source: str = ""):
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
platform: podcast
tags: [播客]
created: {now}
source: {source}
author:
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

        elapsed, seg_count = transcribe_audio(audio_path, output_path, title, source)

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
