#!/usr/bin/env python3
"""
播客一键转录工具

用法：
    python transcribe.py "https://www.xiaoyuzhoufm.com/episode/xxxxx"
    python transcribe.py "https://www.ximalaya.com/xxxxx"
    python transcribe.py "path/to/audio.m4a"
"""

import argparse
import json
import mimetypes
import sys
import os
import time
import subprocess
import tempfile
import shutil
import re
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


MUAPI_BASE_URL = "https://api.muapi.ai/api/v1"
MUAPI_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MUAPI_POLL_INTERVAL = 2
MUAPI_POLL_TIMEOUT = 600


def _muapi_key() -> str:
    return os.environ.get("MUAPI_API_KEY") or os.environ.get("MU_API_KEY") or ""


def _muapi_base_url() -> str:
    return os.environ.get("MUAPI_BASE_URL", MUAPI_BASE_URL).rstrip("/")


def _muapi_json_request(path: str, api_key: str, payload=None, timeout: int = 30):
    """Call a MuAPI JSON endpoint without exposing the key to result hosts."""
    body = None
    headers = {"x-api-key": api_key}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{_muapi_base_url()}/{path.lstrip('/')}", data=body, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"MuAPI request failed ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"MuAPI request failed: {exc}") from exc


def _upload_audio_to_muapi(audio_path: str, api_key: str) -> str:
    """Upload one local audio file using the standard multipart endpoint."""
    file_size = os.path.getsize(audio_path)
    if file_size > MUAPI_MAX_UPLOAD_BYTES:
        raise RuntimeError(
            f"MuAPI accepts audio files under 25 MB; this file is {file_size / 1024 / 1024:.1f} MB. "
            "Use the local provider or provide a shorter audio file."
        )

    boundary = f"----chubbyskills-{int(time.time() * 1000)}"
    filename = os.path.basename(audio_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(audio_path, "rb") as audio_file:
        audio_bytes = audio_file.read()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode(),
            audio_bytes,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    request = Request(
        f"{_muapi_base_url()}/upload_file",
        data=body,
        headers={
            "x-api-key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"MuAPI audio upload failed ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"MuAPI audio upload failed: {exc}") from exc

    if not isinstance(result, dict):
        raise RuntimeError("MuAPI audio upload returned an invalid response")
    audio_url = result.get("url") or result.get("audio_url")
    parsed = urlparse(audio_url or "")
    if not audio_url or parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("MuAPI audio upload returned an invalid HTTPS URL")
    return audio_url


def _muapi_request_id(result):
    if not isinstance(result, dict):
        return None
    for key in ("request_id", "id", "task_id"):
        if isinstance(result.get(key), str) and result[key]:
            return result[key]
    for key in ("data", "output"):
        nested = _muapi_request_id(result.get(key))
        if nested:
            return nested
    return None


def _muapi_status(result):
    if not isinstance(result, dict):
        return None
    if isinstance(result.get("status"), str):
        return result["status"].lower()
    return _muapi_status(result.get("data")) or _muapi_status(result.get("output"))


def _muapi_error(result):
    if not isinstance(result, dict):
        return None
    for key in ("error", "message", "detail"):
        if isinstance(result.get(key), str) and result[key]:
            return result[key]
    return _muapi_error(result.get("data")) or _muapi_error(result.get("output"))


def _muapi_transcript(result):
    """Return (text, segments) from the completed Whisper result envelope."""
    if isinstance(result, str):
        return result, []
    if not isinstance(result, dict):
        if isinstance(result, list):
            segments = [item for item in result if isinstance(item, dict)]
            text = " ".join(
                item["text"].strip()
                for item in segments
                if isinstance(item.get("text"), str) and item["text"].strip()
            )
            return text, segments
        return "", []
    text = result.get("text")
    segments = result.get("segments")
    if isinstance(text, str):
        return text.strip(), segments if isinstance(segments, list) else []
    for key in ("output", "output_data", "data"):
        nested_text, nested_segments = _muapi_transcript(result.get(key))
        if nested_text:
            return nested_text, nested_segments
    return "", []


def _format_muapi_transcript(text: str, segments: list) -> tuple[str, int]:
    """Prefer timestamped segments when the API returned verbose JSON."""
    rendered = []
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            continue
        start = float(segment.get("start") or 0)
        end = float(segment.get("end") or start)
        rendered.append(f"[{start:6.1f}s -> {end:6.1f}s] {segment['text'].strip()}")
    if rendered:
        return "\n".join(rendered), len(rendered)
    return text, 1 if text else 0


def transcribe_audio_muapi(
    audio_path: str,
    output_path: str,
    title: str,
    source: str = "",
    language: str = "",
):
    """Transcribe through MuAPI's hosted openai-whisper endpoint."""
    api_key = _muapi_key()
    if not api_key:
        raise RuntimeError(
            "MuAPI provider selected but MUAPI_API_KEY (or MU_API_KEY) is not set. "
            "Get a key at https://muapi.ai/access-keys."
        )

    started = time.time()
    audio_url = _upload_audio_to_muapi(audio_path, api_key)
    payload = {"audio_url": audio_url, "response_format": "verbose_json"}
    if language:
        payload["language"] = language
    submitted = _muapi_json_request("openai-whisper", api_key, payload)
    request_id = _muapi_request_id(submitted)
    if not request_id:
        raise RuntimeError("MuAPI Whisper request returned no request ID")

    deadline = time.time() + MUAPI_POLL_TIMEOUT
    result = None
    while time.time() < deadline:
        result = _muapi_json_request(
            f"predictions/{quote(request_id, safe='')}/result", api_key, timeout=30
        )
        status = _muapi_status(result)
        if status in {"completed", "succeeded", "success"}:
            break
        if status in {"failed", "error", "cancelled", "canceled"}:
            raise RuntimeError(f"MuAPI Whisper failed: {_muapi_error(result) or 'unknown error'}")
        if status not in {"pending", "queued", "processing", "starting", "in_queue"}:
            raise RuntimeError(
                f"MuAPI Whisper returned an unrecognized status: {status or '(none)'}"
            )
        time.sleep(MUAPI_POLL_INTERVAL)
    else:
        raise TimeoutError(f"MuAPI Whisper timed out after {MUAPI_POLL_TIMEOUT}s")

    text, segments = _muapi_transcript(result)
    transcript, segment_count = _format_muapi_transcript(text, segments)
    if not transcript:
        raise RuntimeError("MuAPI Whisper completed without transcript text")
    elapsed = time.time() - started
    now = datetime.now().strftime("%Y-%m-%d")
    markdown = f"""---
title: {title}
type: note
platform: podcast
tags: [播客]
created: {now}
source: {source}
author:
transcriber: muapi-openai-whisper
---

# {title}

> 转录引擎：MuAPI openai-whisper | 耗时：{elapsed:.0f}秒 | 段数：{segment_count}

{transcript}"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(markdown)
    return elapsed, segment_count


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


def transcribe_audio(
    audio_path: str,
    output_path: str,
    title: str,
    source: str = "",
    provider: str = "local",
    language: str = "zh",
    model_name: str = "small",
):
    """Transcribe audio with the selected backend and save as Markdown."""
    if provider == "muapi":
        return transcribe_audio_muapi(
            audio_path, output_path, title, source=source, language=language
        )
    if provider != "local":
        raise ValueError(f"Unsupported transcription provider: {provider}")

    from faster_whisper import WhisperModel

    print("Loading faster-whisper model...", file=sys.stderr)
    model = WhisperModel(model_name, device='cpu', compute_type='int8')
    print("Model loaded. Transcribing...", file=sys.stderr)

    start = time.time()
    segments, info = model.transcribe(
        audio_path,
        language=language or None,
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
transcriber: faster-whisper-{model_name}
---

# {title}

> 转录引擎：faster-whisper {model_name} | 耗时：{elapsed:.0f}秒 | 段数：{len(text_segments)}

{text}"""

    # Save to file
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    return elapsed, len(text_segments)


def main():
    parser = argparse.ArgumentParser(description="播客一键转录工具")
    parser.add_argument("source", help="音频 URL 或本地文件路径")
    parser.add_argument("output_dir", nargs="?", default=".", help="Markdown 输出目录")
    parser.add_argument(
        "--provider",
        choices=("local", "muapi"),
        default=os.environ.get("PODCAST_TRANSCRIBE_PROVIDER", "local"),
        help="转录后端，默认使用本地 faster-whisper",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="语言代码，默认 zh；MuAPI 可留空自动检测",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="本地 faster-whisper 模型，默认 small",
    )
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

        elapsed, seg_count = transcribe_audio(
            audio_path,
            output_path,
            title,
            source,
            provider=args.provider,
            language=args.language,
            model_name=args.model,
        )

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
