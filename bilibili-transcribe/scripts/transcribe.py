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

import argparse
import os
import re
import shutil
import sys
import tempfile

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = SKILL_ROOT if os.path.isdir(os.path.join(SKILL_ROOT, "chubby_common")) else os.path.dirname(SKILL_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from chubby_common.config import PlatformConfig
from chubby_common import funasr, markdown, vtt, ytdlp

# 字幕语言优先级（中文优先）
SUB_LANGS = "zh-Hans,zh-CN,zh,zh-Hant,ai-zh,en,en-US"
SUB_PRIORITY = ("zh-hans", "zh-cn", "zh", "zh-hant", "ai-zh", "en")

CFG = PlatformConfig(
    id="bilibili",
    name="Bilibili",
    tag="B站",
    default_title="B站视频",
    language="zh",
    referer="https://www.bilibili.com",
)


def extract_bvid(url: str) -> str:
    m = re.search(r"(BV[\w]+)", url)
    if m:
        return m.group(1)
    raise ValueError(f"无法从输入中提取 BV 号：{url}")


def get_info(url: str, bvid: str) -> tuple:
    """返回 (title, uploader)。失败时回退到 bvid。"""
    try:
        r = ytdlp.run_ydl(
            CFG,
            ["--print", "%(title)s|||%(uploader)s", "--skip-download", url],
            timeout=CFG.info_timeout,
            capture=True,
        )
        line = r.stdout.strip().split("\n")[0]
        title, _, uploader = line.partition("|||")
        uploader = uploader.strip()
        if uploader in ("NA", "None"):  # yt-dlp 缺失字段会输出 NA
            uploader = ""
        return (title.strip() or bvid, uploader)
    except Exception:
        return bvid, ""


def try_subtitles(url: str, tmpdir: str):
    """尝试下载字幕。返回 (text, lang) 或 None。"""
    print("  💬 尝试抓取字幕...", file=sys.stderr)
    try:
        ytdlp.run_ydl(
            CFG,
            [
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                SUB_LANGS,
                "--sub-format",
                "vtt",
                "-o",
                os.path.join(tmpdir, "sub.%(ext)s"),
                url,
            ],
            timeout=CFG.subtitle_timeout,
        )
    except Exception:
        return None
    files = vtt.find_vtt_files(tmpdir)
    if not files:
        print("  💬 无字幕，回退音频转录", file=sys.stderr)
        return None
    chosen = vtt.pick_subtitle(files, SUB_PRIORITY)
    text = vtt.parse_vtt(chosen)
    if len(text) < 50:
        return None
    lang = "zh" if re.search(r"[一-鿿]", text) else "en"
    print(f"  ✅ 命中字幕（{lang}，{len(text)} 字）", file=sys.stderr)
    return text, lang


def download_audio(url: str, output_dir: str, title: str) -> str:
    safe = markdown.sanitize_filename(title, "audio")
    print(f"  ⬇️  下载音频：{title[:50]}...", file=sys.stderr)
    path = ytdlp.download_audio(CFG, url, output_dir, filename=f"{safe}.mp3")
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  ✅ 音频：{size_mb:.1f} MB", file=sys.stderr)
    return path


def transcribe_audio(audio_path: str) -> str:
    text, _ = funasr.transcribe(audio_path, language=CFG.language)
    return text


def build_markdown(title, text, url, uploader, transcriber, lang):
    return markdown.note_markdown(
        title,
        text,
        {
            "type": "note",
            "platform": "bilibili",
            "source": url,
            "author": uploader or "",
            "tags": ["B站"],
            "language": lang,
            "transcriber": transcriber,
        },
    )


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

        body = build_markdown(title, text, url, uploader, transcriber, lang)
        safe = markdown.sanitize_filename(title, bvid)
        output_path = os.path.join(output_dir, f"{safe}.md")
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(body)

        print("\n✅ Done!", file=sys.stderr)
        print(f"  来源：{transcriber} | 字数：{len(text)}", file=sys.stderr)
        print(f"  Output: {output_path}", file=sys.stderr)
        print(output_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
