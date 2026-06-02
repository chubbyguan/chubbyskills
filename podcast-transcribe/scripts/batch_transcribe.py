#!/usr/bin/env python3
"""
播客批量转录工具（RSS）

用法：
    python batch_transcribe.py --rss-url "http://www.ximalaya.com/album/xxxxx.xml" --count 10
    python batch_transcribe.py --rss-url "http://www.ximalaya.com/album/xxxxx.xml" --start 11 --count 30
"""

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
    result = subprocess.run(
        ['curl', '-s', '-L', '--max-time', '30',
         '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
         rss_url],
        capture_output=True, text=True, timeout=35
    )
    root = ET.fromstring(result.stdout)
    items = root.findall('.//item')
    
    episodes = []
    for item in items:
        title = item.find('title').text or ''
        pub_date = item.find('pubDate').text or ''
        duration = item.find('itunes:duration', NS)
        duration = duration.text if duration is not None else ''
        enclosure = item.find('enclosure')
        audio_url = enclosure.get('url') if enclosure is not None else ''
        ep_num = item.find('itunes:episode', NS)
        ep_num = ep_num.text if ep_num is not None else ''
        
        # Parse pubDate
        try:
            dt = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %Z')
            date_str = dt.strftime('%Y-%m-%d')
        except:
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
    
    if os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
        print(f"  ⏭ 已存在: {fname}")
        return fpath
    
    print(f"  ⬇ 下载中: {fname} ({ep['duration']})...")
    url = ep['audio_url'].replace('&amp;', '&')
    
    result = subprocess.run(
        ['curl', '-L', '-o', fpath, '--max-time', '1800', '-s', '-w', '%{http_code}', url],
        capture_output=True, text=True, timeout=1900
    )
    
    if result.returncode != 0 or result.stdout != '200':
        print(f"  ❌ 下载失败: HTTP {result.stdout.strip()}")
        if os.path.exists(fpath):
            os.remove(fpath)
        return None
    
    size_mb = os.path.getsize(fpath) / 1024 / 1024
    print(f"  ✅ 完成: {size_mb:.1f} MB")
    return fpath


def transcribe_episode(audio_path: str, output_dir: str, ep: dict) -> str:
    """Transcribe single episode using faster-whisper."""
    safe_name = sanitize_filename(ep['title'])
    txt_name = f"EP{ep['num']:03d}-{safe_name}.md"
    txt_path = os.path.join(output_dir, txt_name)
    
    if os.path.exists(txt_path) and os.path.getsize(txt_path) > 500:
        print(f"  ⏭ 转录已存在: {txt_name}")
        return txt_path
    
    print(f"  🎙 转录中: {safe_name[:50]}...")
    
    # Use the transcribe.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    transcribe_script = os.path.join(script_dir, 'transcribe.py')
    
    result = subprocess.run(
        [sys.executable, transcribe_script, audio_path, output_dir],
        capture_output=True, text=True, timeout=7200,
    )
    
    if result.returncode != 0:
        print(f"  ❌ 转录失败: {result.stderr[:300]}")
        return None
    
    print(f"  ✅ 转录完成")
    return txt_path


def main():
    parser = argparse.ArgumentParser(description='播客批量转录工具')
    parser.add_argument('--rss-url', required=True, help='RSS URL')
    parser.add_argument('--output', default='.', help='输出目录')
    parser.add_argument('--count', type=int, default=10, help='下载数量')
    parser.add_argument('--start', type=int, default=1, help='起始序号')
    parser.add_argument('--download-only', action='store_true', help='仅下载')
    parser.add_argument('--transcribe-only', action='store_true', help='仅转录')
    args = parser.parse_args()
    
    # Create directories
    audio_dir = os.path.join(args.output, 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(args.output, exist_ok=True)
    
    # Parse RSS
    episodes = parse_rss(args.rss_url)
    print(f"📡 共 {len(episodes)} 集")
    
    # Filter batch
    end = min(args.start + args.count - 1, len(episodes))
    batch_eps = [e for e in episodes if args.start <= e['num'] <= end]
    
    print(f"\n📦 批次: #{args.start}-#{end} ({len(batch_eps)} 集)")
    print(f"⏱ 预估时长: {sum(e['dur_sec'] for e in batch_eps)/3600:.1f} 小时\n")
    
    # Download
    if not args.transcribe_only:
        for ep in batch_eps:
            print(f"EP{ep['num']:03d}: {ep['title'][:60]} | {ep['date']} | {ep['duration']}")
            download_episode(ep, audio_dir)
    
    # Transcribe
    if not args.download_only:
        for ep in batch_eps:
            safe_name = sanitize_filename(ep['title'])
            fname = f"EP{ep['num']:03d}-{safe_name}.m4a"
            fpath = os.path.join(audio_dir, fname)
            
            if not os.path.exists(fpath):
                print(f"EP{ep['num']:03d}: ⚠️ 音频不存在，跳过")
                continue
            
            transcribe_episode(fpath, args.output, ep)
    
    print(f"\n🏁 批次完成")


if __name__ == '__main__':
    main()
