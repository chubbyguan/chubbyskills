#!/usr/bin/env python3
"""Download audio from Douyin video — no cookies, no login, no yt-dlp."""

import subprocess
import re
import json
import os
import sys
import tempfile

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


def extract_video_id(url: str) -> str:
    """Extract video ID from Douyin URL (short or full)."""
    # Handle short link redirect
    if 'v.douyin.com' in url:
        result = subprocess.run(
            ["curl", "-sI", "-L", "-H", f"User-Agent: {MOBILE_UA}", url],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.split('\n'):
            if 'location:' in line.lower():
                url = line.split(':', 1)[1].strip()
                break
    # Extract ID from /video/XXXXX
    m = re.search(r'/video/(\d+)', url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")


def download_audio(video_id: str, output_dir: str = None) -> tuple:
    """Download audio from Douyin video. Returns (audio_path, title)."""
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}"

    # Fetch share page
    result = subprocess.run(
        ["curl", "-s", "-L", "-H", f"User-Agent: {MOBILE_UA}", share_url],
        capture_output=True, text=True, timeout=30
    )
    html = result.stdout

    # Extract ROUTER_DATA
    match = re.search(r'window\._ROUTER_DATA\s*=\s*(.*?)</script>', html, re.DOTALL)
    if not match:
        raise RuntimeError("_ROUTER_DATA not found in page")

    data = json.loads(match.group(1).strip())
    item = data["loaderData"]["video_(id)/page"]["videoInfoRes"]["item_list"][0]
    title = item.get("desc", "Untitled")
    video_url = item["video"]["play_addr"]["url_list"][0].replace("playwm", "play")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="dyt-")

    # Download video
    video_path = os.path.join(output_dir, f"{video_id}.mp4")
    print(f"Downloading: {title[:60]}...", file=sys.stderr)
    subprocess.run(
        ["curl", "-s", "-L", "-o", video_path,
         "-H", f"User-Agent: {MOBILE_UA}",
         "-H", "Referer: https://www.douyin.com/", video_url],
        timeout=300, check=True
    )

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"  Video: {size_mb:.1f} MB", file=sys.stderr)

    # Extract audio
    audio_path = os.path.join(output_dir, f"{video_id}.mp3")
    print("Extracting audio...", file=sys.stderr)
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path,
         "-vn", "-acodec", "libmp3lame", "-ab", "128k", audio_path],
        capture_output=True, timeout=60, check=True
    )

    os.remove(video_path)
    print(f"  Audio: {os.path.getsize(audio_path) / (1024 * 1024):.1f} MB", file=sys.stderr)

    return audio_path, title


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <douyin_url>")
        sys.exit(1)

    video_id = extract_video_id(sys.argv[1])
    audio_path, title = download_audio(video_id)
    print(audio_path)
    print(f"TITLE: {title}", file=sys.stderr)
