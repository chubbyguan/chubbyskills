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
import re
from datetime import datetime


def download_audio(url: str, output_dir: str) -> tuple:
    """Download audio from podcast URL. Returns (audio_path, title).

    Supports: direct audio URLs (.mp3/.m4a/.wav), 小宇宙, 喜马拉雅, RSS feeds.
    """
    title = "Podcast Episode"
    audio_url = url

    downloader = _sibling("safe_download")
    # Every media URL is independently validated, including extracted page metadata.
    if not re.search(r'\.(mp3|m4a|wav|ogg|aac)(\?|$)', url, re.IGNORECASE):
        print("  Fetching page...", file=sys.stderr)
        html = downloader.fetch_text(url)

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

        print("  Audio link resolved.", file=sys.stderr)

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
    downloader.download(audio_url, audio_path)

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb < 0.01:
        os.remove(audio_path)
        raise RuntimeError(
            f"Downloaded file is too small ({size_mb:.2f} MB), "
            "likely not an audio file. Check the URL."
        )
    print(f"  Audio: {size_mb:.1f} MB", file=sys.stderr)

    return audio_path, title


def _sibling(name):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("podcast_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transcribe_audio(audio_path: str, output_path: str, title: str, source: str = "",
                     provider: str = "local", language: str = "zh", model_name=None,
                     base_url=None, state_dir=None, cloud_timeout=1800,
                     poll_interval=3, resubmit=False):
    """Transcribe through one provider and create a new Markdown file exclusively.

    Cloud result caching precedes export, so a failed write can be retried without
    submitting another paid task. Existing output files are never overwritten.
    """
    import json
    settings = _sibling("provider_config")
    config = settings.resolve_provider_config(provider, model_name, language, base_url, state_dir)
    settings.positive_seconds(cloud_timeout, "cloud-timeout")
    settings.positive_seconds(poll_interval, "poll-interval", maximum=60)
    if os.path.lexists(output_path):
        raise FileExistsError("Output already exists; choose a new path")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    start = time.monotonic()
    if config["provider"] == "local":
        from faster_whisper import WhisperModel
        print("Loading local faster-whisper model...", file=sys.stderr)
        model = WhisperModel(config["model"], device="cpu", compute_type="int8")
        segments, _info = model.transcribe(audio_path, language=config["language"] or None, beam_size=5, vad_filter=True)
        text_segments = [f"[{segment.start:6.1f}s -> {segment.end:6.1f}s] {segment.text.strip()}" for segment in segments]
        text = "\n".join(text_segments)
        segment_count = len(text_segments)
        transcriber = f"faster-whisper-{config['model']}"
    else:
        result = _sibling("cloud_transcribe").transcribe_cloud(
            audio_path, provider=config["provider"], model=config["model"],
            language=config["language"], base_url=config["base_url"],
            state_dir=config["state_dir"], cloud_timeout=cloud_timeout,
            poll_interval=poll_interval, resubmit=resubmit,
        )
        text_segments = [f"[{segment['start']:6.1f}s -> {segment['end']:6.1f}s] {segment['text']}" for segment in result.get("segments", [])]
        # Full provider text is authoritative; validated timestamps may be incomplete.
        text = result["text"]
        if text_segments:
            text += "\n\n## 时间戳参考（可能不完整）\n\n" + "\n".join(text_segments)
        segment_count = len(text_segments) or 1
        transcriber = f"{config['provider']}-{config['model']}"
    if not text.strip():
        raise RuntimeError("Transcription returned no speech text")
    elapsed = time.monotonic() - start
    now = datetime.now().strftime("%Y-%m-%d")
    def scalar(value):
        return json.dumps(value, ensure_ascii=False)
    markdown = f"""---
title: {scalar(title)}
type: note
platform: podcast
tags: [播客]
created: {now}
source: {scalar(source)}
author:
transcriber: {scalar(transcriber)}
transcription_provider: {config['provider']}
transcription_model: {scalar(config['model'])}
---

# {title.replace(chr(10), ' ').replace(chr(13), ' ')}

> 转录引擎：{transcriber} | 耗时：{elapsed:.0f}秒 | 段数：{segment_count}

{text}
"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    # Exclusive create makes concurrent exports safe and preserves user edits.
    with open(output_path, "x", encoding="utf-8") as stream:
        try:
            stream.write(markdown)
        except BaseException:
            stream.close()
            os.unlink(output_path)
            raise
    return elapsed, segment_count


def _output_path(output_dir, title, audio_path, config):
    import hashlib
    import json
    from pathlib import Path
    digest = hashlib.sha256()
    with open(audio_path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    digest.update(json.dumps({key: config[key] for key in ("provider", "model", "language", "base_url")}, sort_keys=True).encode())
    safe_title = "".join(char for char in title if char.isalnum() or char in "-_ ").strip()[:50] or "episode"
    base = Path(output_dir).expanduser().resolve() / f"{safe_title}-{digest.hexdigest()[:12]}"
    candidate = base.with_suffix(".md")
    number = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = base.with_name(f"{base.name}-{number}").with_suffix(".md")
        number += 1
    return str(candidate)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="播客一键转录工具；local 默认，云转录为可选实验功能", allow_abbrev=False)
    parser.add_argument("source", help="音频 URL 或本地文件")
    parser.add_argument("output_dir", nargs="?", default=".", help="Markdown 输出目录")
    parser.add_argument("--source-url", help="批量模式保留原始音频来源")
    settings = _sibling("provider_config")
    settings.add_provider_arguments(parser)
    args = parser.parse_args(argv)
    try:
        config = settings.resolve_provider_config(args.provider, args.model, args.language, args.base_url, args.state_dir)
        settings.positive_seconds(args.cloud_timeout, "cloud-timeout")
        settings.positive_seconds(args.poll_interval, "poll-interval", maximum=60)
    except ValueError as exc:
        parser.error(str(exc))
    with tempfile.TemporaryDirectory(prefix="podcast-") as temporary:
        try:
            if os.path.isfile(args.source):
                audio_path = os.path.abspath(args.source)
                title = os.path.splitext(os.path.basename(args.source))[0]
            else:
                from urllib.parse import urlsplit
                if urlsplit(args.source).scheme not in ("http", "https"):
                    raise ValueError("Source must be an existing audio file or HTTP(S) URL")
                audio_path, title = download_audio(args.source, temporary)
            output_path = _output_path(args.output_dir, title, audio_path, config)
            elapsed, count = transcribe_audio(
                audio_path, output_path, title, args.source_url or args.source,
                provider=config["provider"], model_name=config["model"], language=config["language"],
                base_url=config["base_url"], state_dir=config["state_dir"],
                cloud_timeout=args.cloud_timeout, poll_interval=args.poll_interval, resubmit=args.resubmit,
            )
        except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
            if isinstance(exc, (RuntimeError, ValueError)):
                print(f"Transcription failed: {exc}", file=sys.stderr)
            else:
                # Raw process/OS errors can contain a signed URL or private source path.
                print("Transcription failed while reading, downloading or exporting; cloud job state is retained for retry", file=sys.stderr)
            return 1
    print(f"Done: provider={config['provider']}, {count} segments, {elapsed:.0f}s", file=sys.stderr)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
