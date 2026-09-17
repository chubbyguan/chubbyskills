#!/usr/bin/env python3
"""
播客批量转录工具（RSS）

用法：
    python batch_transcribe.py --rss-url "http://www.ximalaya.com/album/xxxxx.xml" --count 10
    python batch_transcribe.py --rss-url "http://www.ximalaya.com/album/xxxxx.xml" --start 11 --count 30
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

NS = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}


def parse_rss(rss_url: str):
    """Parse RSS XML and return episode list sorted by episode number."""
    root = ET.fromstring(_sibling("safe_download").fetch_text(rss_url))
    items = root.findall('.//item')

    episodes = []
    for item in items:
        title = item.findtext('title') or ''
        pub_date = item.findtext('pubDate') or ''
        duration = item.findtext('itunes:duration', default='', namespaces=NS) or ''
        enclosure = item.find('enclosure')
        audio_url = enclosure.get('url') if enclosure is not None else ''
        ep_num = item.findtext('itunes:episode', default='', namespaces=NS) or ''

        # Parse pubDate
        try:
            dt = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %Z')
            date_str = dt.strftime('%Y-%m-%d')
        except ValueError:
            date_str = pub_date[:16]

        # Duration in seconds
        dur_sec = 0
        if duration:
            parts = duration.split(':')
            if len(parts) == 2:
                dur_sec = int(parts[0])*60 + int(parts[1])
            elif len(parts) == 3:
                dur_sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])

        episodes.append({
            'num': int(ep_num) if ep_num and ep_num.isdigit() else len(episodes) + 1,
            'title': title,
            'date': date_str,
            'duration': duration,
            'dur_sec': dur_sec,
            'audio_url': audio_url,
        })

    # Sort by episode number
    episodes.sort(key=lambda x: x['num'])
    return episodes


def sanitize_filename(title: str) -> str:
    """Clean filename."""
    s = re.sub(r'[<>:"/\\|?*]', '', title)
    s = re.sub(r'\s+', '-', s)
    return s[:80]


def download_episode(ep: dict, audio_dir: str) -> str:
    """Download single episode audio. Returns file path."""
    safe_name = sanitize_filename(ep['title'])
    fname = f"EP{ep['num']:03d}-{safe_name}.m4a"
    fpath = os.path.join(audio_dir, fname)

    # An old cache must not bypass validation of new untrusted RSS metadata.
    url = ep['audio_url'].replace('&amp;', '&')
    try:
        _sibling("safe_download").public_url(url)
    except (ValueError, RuntimeError) as exc:
        print(f"  下载失败：{exc}", file=sys.stderr)
        return None
    if os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
        print(f"  ⏭ 已存在: {fname}")
        return fpath

    print(f"  ⬇ 下载中: {fname} ({ep['duration']})...")
    url = ep['audio_url'].replace('&amp;', '&')

    try:
        _sibling("safe_download").download(url, fpath)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"  下载失败：{exc}", file=sys.stderr)
        return None

    size_mb = os.path.getsize(fpath) / 1024 / 1024
    print(f"  ✅ 完成: {size_mb:.1f} MB")
    return fpath


def _sibling(name):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("podcast_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _settings():
    return _sibling("provider_config")


def transcribe_episode(audio_path: str, output_dir: str, ep: dict, *, provider=None,
                       model=None, language=None, base_url=None, state_dir=None,
                       cloud_timeout=1800, poll_interval=3, resubmit=False) -> str | None:
    """Run the chosen provider and use its actual output path, never a guessed cache."""
    from pathlib import Path
    settings = _settings()
    config = settings.resolve_provider_config(provider, model, language, base_url, state_dir)
    settings.positive_seconds(cloud_timeout, "cloud-timeout")
    settings.positive_seconds(poll_interval, "poll-interval", maximum=60)
    script = Path(__file__).with_name("transcribe.py")
    command = [sys.executable, str(script), audio_path, output_dir,
               "--provider", config["provider"], "--model", config["model"],
               "--language", config["language"], "--state-dir", config["state_dir"],
               "--cloud-timeout", str(cloud_timeout), "--poll-interval", str(poll_interval)]
    if config["base_url"]:
        command.extend(["--base-url", config["base_url"]])
    if ep.get("audio_url"):
        command.extend(["--source-url", ep["audio_url"]])
    if resubmit:
        command.append("--resubmit")
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=max(7200, cloud_timeout + 2000))
    except (OSError, subprocess.SubprocessError):
        print("  转录进程中断，已提交云任务可使用同一命令恢复", file=sys.stderr)
        return None
    if result.returncode != 0:
        # Child stderr is intentionally suppressed: local dependencies can echo signed source URLs.
        print("  转录失败，请用单集命令查看错误；云任务状态已保留", file=sys.stderr)
        return None
    lines = result.stdout.strip().splitlines()
    if not lines:
        print("  转录失败：未返回输出文件", file=sys.stderr)
        return None
    actual = Path(lines[-1]).expanduser().resolve()
    output_root = Path(output_dir).expanduser().resolve()
    if not actual.is_file() or actual.suffix != ".md" or not actual.is_relative_to(output_root):
        print("  转录失败：返回的输出文件无效", file=sys.stderr)
        return None
    print("  转录完成")
    return str(actual)


def main(argv=None):
    parser = argparse.ArgumentParser(description='播客批量转录工具', allow_abbrev=False)
    parser.add_argument('--rss-url', required=True, help='RSS URL')
    parser.add_argument('--output', default='.', help='输出目录')
    parser.add_argument('--count', type=int, default=10, help='下载数量')
    parser.add_argument('--start', type=int, default=1, help='起始序号')
    parser.add_argument('--download-only', action='store_true', help='仅下载')
    parser.add_argument('--transcribe-only', action='store_true', help='仅转录')
    settings = _settings()
    settings.add_provider_arguments(parser)
    args = parser.parse_args(argv)
    try:
        config = settings.resolve_provider_config(args.provider, args.model, args.language, args.base_url, args.state_dir)
        settings.positive_seconds(args.cloud_timeout, "cloud-timeout")
        settings.positive_seconds(args.poll_interval, "poll-interval", maximum=60)
    except ValueError as exc:
        parser.error(str(exc))
    failures = 0

    # Create directories
    audio_dir = os.path.join(args.output, 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(args.output, exist_ok=True)

    # Parse RSS
    try:
        episodes = parse_rss(args.rss_url)
    except (ValueError, RuntimeError, OSError, ET.ParseError) as exc:
        print(f"RSS 读取失败：{exc}", file=sys.stderr)
        return 1
    print(f"📡 共 {len(episodes)} 集")

    # Filter batch
    end = min(args.start + args.count - 1, len(episodes))
    batch_eps = [e for e in episodes if args.start <= e['num'] <= end]

    print(f"\n📦 批次: #{args.start}-#{end} ({len(batch_eps)} 集)")
    print(f"⏱ 预估时长: {sum(e['dur_sec'] for e in batch_eps)/3600:.1f} 小时\n")

    # Download
    downloaded = {}
    if not args.transcribe_only:
        for ep in batch_eps:
            print(f"EP{ep['num']:03d}: {ep['title'][:60]} | {ep['date']} | {ep['duration']}")
            downloaded[ep['num']] = download_episode(ep, audio_dir)
            if not downloaded[ep['num']]:
                failures += 1

    # Transcribe
    if not args.download_only:
        for ep in batch_eps:
            if not args.transcribe_only and not downloaded.get(ep['num']):
                continue
            if args.transcribe_only:
                try:
                    _sibling("safe_download").public_url(ep['audio_url'])
                except (ValueError, RuntimeError) as exc:
                    print(f"  音频来源无效：{exc}", file=sys.stderr)
                    failures += 1
                    continue
            safe_name = sanitize_filename(ep['title'])
            fname = f"EP{ep['num']:03d}-{safe_name}.m4a"
            fpath = os.path.join(audio_dir, fname)

            if not os.path.exists(fpath):
                print(f"EP{ep['num']:03d}: ⚠️ 音频不存在，跳过")
                failures += 1
                continue

            if not transcribe_episode(
                fpath, args.output, ep, provider=config["provider"], model=config["model"],
                language=config["language"], base_url=config["base_url"], state_dir=config["state_dir"],
                cloud_timeout=args.cloud_timeout, poll_interval=args.poll_interval, resubmit=args.resubmit,
            ):
                failures += 1

    print(f"\n🏁 批次完成，失败：{failures}")
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
