#!/usr/bin/env python3
"""
B 站视频一键转录工具（字幕优先）

策略：先尝试抓官方/自动字幕（秒级、免 GPU、免 funasr）；
抓不到再回退到下载音频 + SenseVoice-Small 转录。

用法：
    python transcribe.py "https://www.bilibili.com/video/BV1rrQGBeEen/"
    python transcribe.py "BV1rrQGBeEen" ./output
    python transcribe.py "BV1rrQGBeEen" --no-subtitle   # 强制走音频转录
"""

import sys
import os
import re
import glob
import argparse
import subprocess
import tempfile
import shutil
from datetime import datetime


MOBILE_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com"
# 字幕语言优先级（中文优先）
SUB_LANGS = "zh-Hans,zh-CN,zh,zh-Hant,ai-zh,en,en-US"


def extract_bvid(url: str) -> str:
    m = re.search(r"(BV[\w]+)", url)
    if m:
        return m.group(1)
    raise ValueError(f"无法从输入中提取 BV 号：{url}")


def ydl_base():
    return ["yt-dlp", "--no-check-certificates",
            "--user-agent", MOBILE_UA, "--referer", REFERER]


def get_info(url: str, bvid: str) -> tuple:
    """返回 (title, uploader)。失败时回退到 bvid。"""
    try:
        r = subprocess.run(
            ydl_base() + ["--print", "%(title)s|||%(uploader)s", "--skip-download", url],
            capture_output=True, text=True, timeout=40,
        )
        line = r.stdout.strip().split("\n")[0]
        title, _, uploader = line.partition("|||")
        uploader = uploader.strip()
        if uploader in ("NA", "None"):  # yt-dlp 缺失字段会输出 NA
            uploader = ""
        return (title.strip() or bvid, uploader)
    except Exception:
        return bvid, ""


def parse_vtt(path: str) -> str:
    """把 vtt 字幕解析成纯文本，去时间轴、去标签、去连续重复行。"""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line:
            continue
        if line.isdigit() or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        line = re.sub(r"<[^>]+>", "", line).replace("&nbsp;", " ").strip()
        if not line or (out and out[-1] == line):
            continue
        out.append(line)
    return "\n".join(out)


def try_subtitles(url: str, tmpdir: str):
    """尝试下载字幕。返回 (text, lang) 或 None。"""
    print("  💬 尝试抓取字幕...", file=sys.stderr)
    try:
        subprocess.run(
            ydl_base() + ["--skip-download", "--write-subs", "--write-auto-subs",
                          "--sub-langs", SUB_LANGS, "--sub-format", "vtt",
                          "-o", os.path.join(tmpdir, "sub.%(ext)s"), url],
            capture_output=True, text=True, timeout=120,
        )
    except Exception:
        return None
    files = glob.glob(os.path.join(tmpdir, "*.vtt"))
    if not files:
        print("  💬 无字幕，回退音频转录", file=sys.stderr)
        return None
    # 按语言优先级挑文件：中文优先
    def rank(p):
        name = os.path.basename(p).lower()
        for i, tag in enumerate(["zh-hans", "zh-cn", "zh", "zh-hant", "ai-zh", "en"]):
            if tag in name:
                return i
        return 99
    chosen = sorted(files, key=rank)[0]
    text = parse_vtt(chosen)
    if len(text) < 50:
        return None
    lang = "zh" if re.search(r"[一-鿿]", text) else "en"
    print(f"  ✅ 命中字幕（{lang}，{len(text)} 字）", file=sys.stderr)
    return text, lang


def download_audio(url: str, output_dir: str, title: str) -> str:
    safe = "".join(c for c in title if c.isalnum() or c in "-_ 《》").strip()[:50]
    audio_path = os.path.join(output_dir, f"{safe or 'audio'}.mp3")
    print(f"  ⬇️  下载音频：{title[:50]}...", file=sys.stderr)
    subprocess.run(
        ydl_base() + ["--extract-audio", "--audio-format", "mp3",
                      "--audio-quality", "128K", "-o", audio_path, url],
        timeout=600, check=True,
    )
    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  ✅ 音频：{size_mb:.1f} MB", file=sys.stderr)
    return audio_path


def transcribe_audio(audio_path: str) -> str:
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    print("  🎙️  加载 SenseVoice-Small...", file=sys.stderr)
    model = AutoModel(
        model="iic/SenseVoiceSmall", trust_remote_code=True,
        vad_model="fsmn-vad", vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
    )
    print("  🎙️  转录中...", file=sys.stderr)
    result = model.generate(input=audio_path, language="zh", use_itn=True, batch_size_s=60)
    text = ""
    for r in (result or []):
        if "text" in r:
            text += rich_transcription_postprocess(r["text"]) + "\n\n"
    return text.strip()


def build_markdown(title, text, url, uploader, transcriber, lang):
    now = datetime.now().strftime("%Y-%m-%d")
    return f"""---
title: {title}
type: note
platform: bilibili
source: {url}
author: {uploader}
created: {now}
tags: [B站]
language: {lang}
transcriber: {transcriber}
---

# {title}

{text}"""


def main():
    parser = argparse.ArgumentParser(description="B 站视频转录（字幕优先）")
    parser.add_argument("url", help="B 站链接或 BV 号")
    parser.add_argument("output", nargs="?", default=".", help="输出目录")
    parser.add_argument("--output", "-o", dest="output_opt", help="输出目录")
    parser.add_argument("--no-subtitle", action="store_true", help="跳过字幕，强制音频转录")
    args = parser.parse_args()
    output_dir = args.output_opt or args.output

    bvid = extract_bvid(args.url)
    url = f"https://www.bilibili.com/video/{bvid}/"

    print("=" * 50, file=sys.stderr)
    print("Step 1: 获取视频信息...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    title, uploader = get_info(url, bvid)
    print(f"  📺 {title}  | UP: {uploader or '未知'}", file=sys.stderr)

    tmpdir = tempfile.mkdtemp(prefix="bilibili-")
    try:
        text, lang, transcriber = None, "zh", "SenseVoice-Small"

        if not args.no_subtitle:
            print("\n" + "=" * 50, file=sys.stderr)
            print("Step 2: 字幕优先...", file=sys.stderr)
            print("=" * 50, file=sys.stderr)
            sub = try_subtitles(url, tmpdir)
            if sub:
                text, lang = sub
                transcriber = "字幕"

        if text is None:
            print("\n" + "=" * 50, file=sys.stderr)
            print("Step 2b: 下载 + 转录...", file=sys.stderr)
            print("=" * 50, file=sys.stderr)
            audio_path = download_audio(url, tmpdir, title)
            text = transcribe_audio(audio_path)

        markdown = build_markdown(title, text, url, uploader, transcriber, lang)
        safe = "".join(c for c in title if c.isalnum() or c in "-_ 《》").strip()[:50]
        output_path = os.path.join(output_dir, f"{safe or bvid}.md")
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        print("\n✅ Done!", file=sys.stderr)
        print(f"  来源：{transcriber} | 字数：{len(text)}", file=sys.stderr)
        print(f"  Output: {output_path}", file=sys.stderr)
        print(output_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
