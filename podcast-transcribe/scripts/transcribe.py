#!/usr/bin/env python3
"""
播客一键转录工具

用法：
    python transcribe.py "https://www.xiaoyuzhoufm.com/episode/xxxxx"
    python transcribe.py "https://www.ximalaya.com/xxxxx"
    python transcribe.py "path/to/audio.m4a"
"""

import argparse
import sys
import os
import time
import subprocess
import tempfile
import shutil
import re
from datetime import datetime

from atlas_transcribe import DEFAULT_MODEL, transcribe_file


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
        print("  Fetching page...", file=sys.stderr)
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


def write_transcript_markdown(
    output_path: str,
    title: str,
    source: str,
    text_segments: list,
    elapsed: float,
    transcriber: str,
):
    """Write transcript segments using the skill's Markdown contract."""
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
transcriber: {transcriber}
---

# {title}

> 转录引擎：{transcriber} | 耗时：{elapsed:.0f}秒 | 段数：{len(text_segments)}

{text}"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write(markdown)

    return elapsed, len(text_segments)


def transcribe_audio_local(audio_path: str, output_path: str, title: str, source: str = ""):
    """Transcribe audio using faster-whisper and save as Markdown."""
    from faster_whisper import WhisperModel

    print("Loading faster-whisper model...", file=sys.stderr)
    model = WhisperModel('small', device='cpu', compute_type='int8')
    print("Model loaded. Transcribing...", file=sys.stderr)

    start = time.time()
    segments, _info = model.transcribe(
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

    return write_transcript_markdown(
        output_path,
        title,
        source,
        text_segments,
        elapsed,
        "faster-whisper small",
    )


def transcribe_audio_atlas(
    audio_path: str,
    output_path: str,
    title: str,
    source: str,
    api_key: str,
    language: str,
    timeout: float,
):
    """Transcribe audio through the optional Atlas Cloud provider."""
    with tempfile.TemporaryDirectory(prefix="podcast-atlas-") as temp_dir:
        extension = os.path.splitext(audio_path)[1].lower()
        if extension in {".mp3", ".wav", ".ogg", ".raw"}:
            upload_path = audio_path
        else:
            upload_path = os.path.join(temp_dir, "audio.mp3")
            print("Converting audio to MP3 for Atlas Cloud...", file=sys.stderr)
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", audio_path, "-vn",
                    "-acodec", "libmp3lame", upload_path,
                ],
                capture_output=True,
                text=True,
                timeout=3600,
                check=True,
            )

        print(f"Submitting one Atlas Cloud transcription ({DEFAULT_MODEL})...", file=sys.stderr)
        start = time.time()
        text = transcribe_file(
            audio_path=upload_path,
            api_key=api_key,
            language=language,
            timeout=timeout,
        )
        elapsed = time.time() - start

    return write_transcript_markdown(
        output_path,
        title,
        source,
        [text],
        elapsed,
        f"Atlas Cloud ({DEFAULT_MODEL})",
    )


def main():
    parser = argparse.ArgumentParser(description="播客单集转录工具")
    parser.add_argument("source", help="播客页面、音频 URL 或本地音频路径")
    parser.add_argument("output_dir", nargs="?", default=".", help="输出目录")
    parser.add_argument(
        "--provider",
        choices=("local", "atlas"),
        default=os.environ.get("PODCAST_TRANSCRIBE_PROVIDER", "local"),
        help="转录提供商，默认 local",
    )
    parser.add_argument("--language", default="", help="可选语言代码，例如 zh-CN")
    parser.add_argument("--atlas-timeout", type=float, default=1800, help="Atlas 轮询超时秒数")
    args = parser.parse_args()

    source = args.source
    output_dir = args.output_dir

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

        if args.provider == "atlas":
            api_key = os.environ.get("ATLASCLOUD_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("ATLASCLOUD_API_KEY is required for --provider atlas")
            elapsed, seg_count = transcribe_audio_atlas(
                audio_path,
                output_path,
                title,
                source,
                api_key,
                args.language,
                args.atlas_timeout,
            )
        else:
            elapsed, seg_count = transcribe_audio_local(audio_path, output_path, title, source)

        print("\n" + "=" * 50, file=sys.stderr)
        print("✅ Done!", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print(f"  Title: {title}", file=sys.stderr)
        print(f"  Time: {elapsed:.0f}s", file=sys.stderr)
        print(f"  Segments: {seg_count}", file=sys.stderr)
        print(f"  Output: {output_path}", file=sys.stderr)

        # Print output path to stdout for scripting
        print(output_path)

    except Exception as exc:
        print(f"\n❌ 转录失败：{exc}", file=sys.stderr)
        return 1

    finally:
        # Cleanup
        shutil.rmtree(tmpdir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
