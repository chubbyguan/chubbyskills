#!/usr/bin/env python3
"""
YouTube 视频转录 + 翻译工具

用法：
    python transcribe.py "https://www.youtube.com/watch?v=xxxxx"
    python transcribe.py "https://www.youtube.com/watch?v=xxxxx" --no-translate
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from chubby_common.config import PlatformConfig
from chubby_common import funasr, markdown, vtt, ytdlp

SUB_LANGS = "en,en-US,en-orig,zh-Hans,zh-CN,zh,zh-Hant"
SUB_PRIORITY = ("en", "zh-hans", "zh-cn", "zh")

CFG = PlatformConfig(
    id="youtube",
    name="YouTube",
    tag="YouTube",
    default_title="YouTube Video",
    language="auto",  # 中英内容混杂，自动检测
    referer="https://www.youtube.com/",
)


def get_video_info(url: str) -> dict:
    """Get video title and duration; fall back to defaults on any failure."""
    try:
        result = ytdlp.run_ydl(
            CFG, ["--get-title", "--get-duration", url], timeout=CFG.info_timeout, capture=True
        )
        lines = result.stdout.strip().split("\n")
        return {
            "title": lines[0] if lines else CFG.default_title,
            "duration": lines[1] if len(lines) > 1 else "",
        }
    except Exception:
        return {"title": CFG.default_title, "duration": ""}


def download_audio(url: str, output_dir: str) -> str:
    """Download audio from YouTube."""
    return ytdlp.download_audio(CFG, url, output_dir)


def try_subtitles(url: str, tmpdir: str):
    """字幕优先：抓官方/自动字幕，免下载+转录。返回 (text, language) 或 None。"""
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
    chinese = len(re.findall(r"[一-鿿]", text))
    language = "zh" if chinese / max(len(text), 1) > 0.3 else "en"
    print(f"  ✅ 命中字幕（{language}，{len(text)} 字）", file=sys.stderr)
    return text, language


def transcribe_audio(audio_path: str) -> tuple:
    """Transcribe audio using SenseVoice-Small. Returns (text, language)."""
    text, _ = funasr.transcribe(audio_path, language="auto")

    # Detect language (simple heuristic)
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    total_chars = len(text.strip())
    language = "zh" if chinese_chars / max(total_chars, 1) > 0.3 else "en"
    return text.strip(), language


def translate_text(text: str, api_key: str = None) -> str:
    """Translate English to Chinese using DeepSeek API."""
    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY")

    if not api_key:
        print("  ⚠️  No DEEPSEEK_API_KEY, skipping translation", file=sys.stderr)
        return None

    print("  🌐 Translating to Chinese...", file=sys.stderr)

    # Split into chunks if too long
    chunks = []
    if len(text) > 4000:
        paragraphs = text.split("\n\n")
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) > 3500:
                chunks.append(current_chunk)
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        if current_chunk:
            chunks.append(current_chunk)
    else:
        chunks = [text]

    translated_chunks = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"  🌐 Translating chunk {i+1}/{len(chunks)}...", file=sys.stderr)

        try:
            payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是专业翻译。将英文翻译成中文，保持原文风格和格式。不要添加额外解释。"},
                    {"role": "user", "content": f"翻译以下英文为中文：\n\n{chunk}"}
                ],
                "temperature": 0.3
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                response = json.loads(resp.read())

            translated = response["choices"][0]["message"]["content"]
            translated_chunks.append(translated)
        except Exception as e:
            print(f"  ⚠️  Translation failed: {e}", file=sys.stderr)
            return None

    print("  ✅ Translation done", file=sys.stderr)
    return "\n\n".join(translated_chunks)


def generate_markdown(title: str, original: str, translated: str, language: str, url: str, transcriber: str = "SenseVoice-Small") -> str:
    """Generate bilingual Markdown."""
    fields = {
        "type": "note",
        "platform": "youtube",
        "tags": "[YouTube]",
        "source": url,
        "author": "",
        "language": language,
        "transcriber": transcriber,
    }
    if language == "en" and translated:
        fields["translated"] = "true"
        body = (
            "> 🌐 英文视频，已翻译为中文\n\n"
            "---\n\n"
            "## 中文翻译\n\n"
            f"{translated}\n\n"
            "---\n\n"
            "## English Original\n\n"
            f"{original}"
        )
        return markdown.note_markdown(title, body, fields)
    return markdown.note_markdown(title, original, fields)


def main():
    parser = argparse.ArgumentParser(description="YouTube 视频转录 + 翻译")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument("--no-translate", action="store_true", help="不翻译")
    parser.add_argument("--no-subtitle", action="store_true", help="跳过字幕，强制音频转录")
    args = parser.parse_args()

    # Step 1: Get video info
    print("=" * 50, file=sys.stderr)
    print("Step 1: Getting video info...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    info = get_video_info(args.url)
    title = info["title"]
    print(f"  📺 Title: {title}", file=sys.stderr)
    print(f"  ⏱️  Duration: {info['duration']}", file=sys.stderr)

    # Step 2: Get transcript (subtitle-first, fallback to audio)
    print("\n" + "=" * 50, file=sys.stderr)
    print("Step 2: Getting transcript...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    tmpdir = tempfile.mkdtemp(prefix="youtube-")
    try:
        transcriber = "SenseVoice-Small"
        sub = None if args.no_subtitle else try_subtitles(args.url, tmpdir)
        if sub:
            transcriber = "字幕"
        else:
            audio_path = download_audio(args.url, tmpdir)

        # Step 3: Build transcript
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 3: Building transcript...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        if sub:
            text, language = sub
        else:
            text, language = transcribe_audio(audio_path)

        # Step 4: Translate if English
        translated = None
        if language == "en" and not args.no_translate:
            print("\n" + "=" * 50, file=sys.stderr)
            print("Step 4: Translating...", file=sys.stderr)
            print("=" * 50, file=sys.stderr)
            translated = translate_text(text)

        # Step 5: Generate Markdown
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 5: Generating Markdown...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)

        markdown_text = generate_markdown(title, text, translated, language, args.url, transcriber)

        # Save
        safe_title = markdown.sanitize_filename(title, CFG.default_title)
        output_path = os.path.join(args.output, f"{safe_title}.md")
        os.makedirs(args.output, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        print("\n" + "=" * 50, file=sys.stderr)
        print("✅ Done!", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        print(f"  Title: {title}", file=sys.stderr)
        print(f"  Language: {language}", file=sys.stderr)
        print(f"  Translated: {'Yes' if translated else 'No'}", file=sys.stderr)
        print(f"  Output: {output_path}", file=sys.stderr)

        print(output_path)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
