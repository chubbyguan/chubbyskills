#!/usr/bin/env python3
"""Download audio from Douyin video — no cookies, no login, no yt-dlp."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from chubby_common import deps

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


def extract_video_id(url: str) -> str:
    """Extract video ID from Douyin URL (short or full)."""
    # Handle short link redirect
    if "v.douyin.com" in url:
        result = subprocess.run(
            ["curl", "-sI", "-L", "-H", f"User-Agent: {MOBILE_UA}", url],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.split("\n"):
            if "location:" in line.lower():
                url = line.split(":", 1)[1].strip()
                break
    # Extract ID from /video/XXXXX
    m = re.search(r"/video/(\d+)", url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")


def parse_share_page(html: str) -> dict:
    """从分享页 HTML 提取 (title, video_url)，页面结构变化时给出可读错误。"""
    match = re.search(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", html, re.DOTALL)
    if not match:
        raise RuntimeError("页面未包含 _ROUTER_DATA，可能已被风控或链接失效")
    try:
        data = json.loads(match.group(1).strip())
        item = data["loaderData"]["video_(id)/page"]["videoInfoRes"]["item_list"][0]
        title = item.get("desc") or "Untitled"
        play_addr = item["video"]["play_addr"]["url_list"]
        video_url = play_addr[0].replace("playwm", "play")
        return {"title": title, "video_url": video_url}
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"页面结构解析失败（{exc}），可能已被风控或链接失效") from exc


def download_audio(video_id: str, output_dir: str = None) -> tuple:
    """Download audio from Douyin video. Returns (audio_path, title)."""
    deps.ensure_ffmpeg()
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}"

    # Fetch share page
    result = subprocess.run(
        ["curl", "-s", "-L", "-H", f"User-Agent: {MOBILE_UA}", share_url],
        capture_output=True, text=True, timeout=30
    )
    info = parse_share_page(result.stdout)

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="dyt-")

    # Download video
    video_path = os.path.join(output_dir, f"{video_id}.mp4")
    print(f"Downloading: {info['title'][:60]}...", file=sys.stderr)
    subprocess.run(
        ["curl", "-s", "-L", "-o", video_path,
         "-H", f"User-Agent: {MOBILE_UA}",
         "-H", "Referer: https://www.douyin.com/", info["video_url"]],
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

    return audio_path, info["title"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <douyin_url>")
        sys.exit(1)

    tmpdir = tempfile.mkdtemp(prefix="dyt-")
    try:
        video_id = extract_video_id(sys.argv[1])
        audio_path, title = download_audio(video_id, tmpdir)
        print(audio_path)
        print(f"TITLE: {title}", file=sys.stderr)
    except (RuntimeError, ValueError) as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
