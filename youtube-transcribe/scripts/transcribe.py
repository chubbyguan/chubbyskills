#!/usr/bin/env python3
"""
YouTube 视频转录 + 翻译工具

用法：
    python transcribe.py "https://www.youtube.com/watch?v=xxxxx"
    python transcribe.py "https://www.youtube.com/watch?v=xxxxx" --no-translate
"""

import sys
import os
import re
import time
import json
import subprocess
import tempfile
import shutil
from datetime import datetime


def get_video_info(url: str) -> dict:
    """Get video title and duration."""
    result = subprocess.run(
        ["yt-dlp", "--get-title", "--get-duration", "--no-check-certificates", url],
        capture_output=True, text=True, timeout=30
    )
    lines = result.stdout.strip().split('\n')
    return {
        'title': lines[0] if lines else 'Untitled',
        'duration': lines[1] if len(lines) > 1 else '',
    }


def download_audio(url: str, output_dir: str) -> str:
    """Download audio from YouTube."""
    print(f"  ⬇️  Downloading audio...", file=sys.stderr)
    
    audio_path = os.path.join(output_dir, "audio.mp3")
    subprocess.run(
        ["yt-dlp",
         "--extract-audio", "--audio-format", "mp3", "--audio-quality", "128K",
         "-o", audio_path,
         "--no-check-certificates",
         url],
        timeout=600, check=True
    )
    
    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  ✅ Audio: {size_mb:.1f} MB", file=sys.stderr)
    return audio_path


def transcribe_audio(audio_path: str) -> tuple:
    """Transcribe audio using SenseVoice-Small. Returns (text, language)."""
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    print("  🎙️  Loading model...", file=sys.stderr)
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        trust_remote_code=True,
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
    )

    print("  🎙️  Transcribing...", file=sys.stderr)
    start = time.time()
    
    # Auto detect language
    result = model.generate(
        input=audio_path,
        language="auto",  # Auto detect
        use_itn=True,
        batch_size_s=60
    )
    elapsed = time.time() - start

    # Extract text
    text = ""
    if result and len(result) > 0:
        for r in result:
            if "text" in r:
                text += rich_transcription_postprocess(r["text"]) + "\n\n"
    
    # Detect language (simple heuristic)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.strip())
    language = "zh" if chinese_chars / max(total_chars, 1) > 0.3 else "en"
    
    print(f"  ✅ Transcribed in {elapsed:.1f}s (detected: {language})", file=sys.stderr)
    return text.strip(), language


def translate_text(text: str, api_key: str = None) -> str:
    """Translate English to Chinese using DeepSeek API."""
    # Try to get API key from environment
    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
    
    if not api_key:
        print("  ⚠️  No DEEPSEEK_API_KEY, skipping translation", file=sys.stderr)
        return None
    
    print("  🌐 Translating to Chinese...", file=sys.stderr)
    
    # Split into chunks if too long
    chunks = []
    if len(text) > 4000:
        # Split by paragraphs
        paragraphs = text.split('\n\n')
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
            result = subprocess.run(
                ["curl", "-s", "https://api.deepseek.com/v1/chat/completions",
                 "-H", "Content-Type: application/json",
                 "-H", f"Authorization: Bearer {api_key}",
                 "-d", json.dumps({
                     "model": "deepseek-chat",
                     "messages": [
                         {"role": "system", "content": "你是专业翻译。将英文翻译成中文，保持原文风格和格式。不要添加额外解释。"},
                         {"role": "user", "content": f"翻译以下英文为中文：\n\n{chunk}"}
                     ],
                     "temperature": 0.3
                 })],
                capture_output=True, text=True, timeout=120
            )
            
            response = json.loads(result.stdout)
            translated = response['choices'][0]['message']['content']
            translated_chunks.append(translated)
        except Exception as e:
            print(f"  ⚠️  Translation failed: {e}", file=sys.stderr)
            return None
    
    print(f"  ✅ Translation done", file=sys.stderr)
    return "\n\n".join(translated_chunks)


def generate_markdown(title: str, original: str, translated: str, language: str, url: str) -> str:
    """Generate bilingual Markdown."""
    now = datetime.now().strftime("%Y-%m-%d")
    elapsed_note = ""
    
    if language == "en" and translated:
        return f"""---
title: {title}
type: note
tags: [YouTube]
created: {now}
source: {url}
language: en
translated: true
---

# {title}

> 🌐 英文视频，已翻译为中文

---

## 中文翻译

{translated}

---

## English Original

{original}
"""
    else:
        return f"""---
title: {title}
type: note
tags: [YouTube]
created: {now}
source: {url}
language: {language}
---

# {title}

{original}
"""


def sanitize_filename(name: str) -> str:
    """Clean filename."""
    s = re.sub(r'[<>:"/\\|?*]', '', name)
    s = re.sub(r'\s+', '-', s)
    return s[:50]


def main():
    import argparse
    parser = argparse.ArgumentParser(description='YouTube 视频转录 + 翻译')
    parser.add_argument('url', help='YouTube URL')
    parser.add_argument('--output', '-o', default='.', help='输出目录')
    parser.add_argument('--no-translate', action='store_true', help='不翻译')
    args = parser.parse_args()
    
    # Step 1: Get video info
    print("=" * 50, file=sys.stderr)
    print("Step 1: Getting video info...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    
    info = get_video_info(args.url)
    title = info['title']
    print(f"  📺 Title: {title}", file=sys.stderr)
    print(f"  ⏱️  Duration: {info['duration']}", file=sys.stderr)
    
    # Step 2: Download audio
    print("\n" + "=" * 50, file=sys.stderr)
    print("Step 2: Downloading audio...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    
    tmpdir = tempfile.mkdtemp(prefix="youtube-")
    try:
        audio_path = download_audio(args.url, tmpdir)
        
        # Step 3: Transcribe
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 3: Transcribing...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        
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
        
        markdown = generate_markdown(title, text, translated, language, args.url)
        
        # Save
        safe_title = sanitize_filename(title)
        output_path = os.path.join(args.output, f"{safe_title}.md")
        os.makedirs(args.output, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
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
