#!/usr/bin/env python3
"""
知乎视频一键转录工具

用法：
    python transcribe.py "https://www.zhihu.com/video/xxxxx"
    python transcribe.py "https://www.zhihu.com/question/xxx/answer/yyy" -o ./out
    python transcribe.py "https://zhuanlan.zhihu.com/p/xxxxx"

特点：
    - 兼容 zhihu.com/video、问答内嵌视频、zhuanlan 专栏多种链接形态
    - Referer + UA 伪装，规避知乎反爬
    - 下载失败自动重试
"""

import sys
import os
import re
import time
import argparse
import subprocess
import tempfile
import shutil
from datetime import datetime


# 平台配置
PLATFORM = "知乎"
TAG = "知乎"
TMP_PREFIX = "zhihu"
DEFAULT_TITLE = "知乎视频"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
REFERER = "https://www.zhihu.com/"
LANGUAGE = "zh"  # 知乎以中文为主
EXTRA_YDL_ARGS = []
DOWNLOAD_TIMEOUT = 300
MAX_RETRY = 3


def run_ydl(args, timeout, capture=False):
    """统一的 yt-dlp 调用，带平台 UA / Referer / 额外参数。"""
    cmd = ["yt-dlp", "--no-check-certificates",
           "--user-agent", UA, "--referer", REFERER] + EXTRA_YDL_ARGS + args
    return subprocess.run(cmd, capture_output=capture, text=True,
                          timeout=timeout, check=not capture)


def get_video_info(url: str) -> dict:
    try:
        result = run_ydl(["--get-title", url], timeout=30, capture=True)
        title = result.stdout.strip() or DEFAULT_TITLE
    except Exception:
        title = DEFAULT_TITLE
    return {"title": title}


def download_audio(url: str, output_dir: str) -> str:
    """下载音频，失败自动重试。"""
    audio_path = os.path.join(output_dir, "audio.mp3")
    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            print(f"  ⬇️  Downloading (attempt {attempt}/{MAX_RETRY})...",
                  file=sys.stderr)
            run_ydl(["--extract-audio", "--audio-format", "mp3",
                     "--audio-quality", "128K", "-o", audio_path, url],
                    timeout=DOWNLOAD_TIMEOUT)
            size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            print(f"  ✅ Audio: {size_mb:.1f} MB", file=sys.stderr)
            return audio_path
        except subprocess.CalledProcessError as e:
            last_err = e
            print(f"  ⚠️  下载失败，{2 * attempt}s 后重试...", file=sys.stderr)
            time.sleep(2 * attempt)
        except subprocess.TimeoutExpired as e:
            last_err = e
            print(f"  ⚠️  下载超时，重试...", file=sys.stderr)
    raise RuntimeError(
        f"{PLATFORM} 下载失败（已重试 {MAX_RETRY} 次）。"
        f"可能原因：链接非视频内容、需要登录 cookie、或视频已删除。原始错误：{last_err}"
    )


def transcribe_audio(audio_path: str) -> str:
    """SenseVoice-Small 转录，返回纯文本。"""
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
    result = model.generate(input=audio_path, language=LANGUAGE,
                            use_itn=True, batch_size_s=60)
    elapsed = time.time() - start

    text = ""
    if result and len(result) > 0:
        for r in result:
            if "text" in r:
                text += rich_transcription_postprocess(r["text"]) + "\n\n"

    print(f"  ✅ Done in {elapsed:.1f}s", file=sys.stderr)
    return text.strip()


def sanitize_filename(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "", name)
    s = re.sub(r"\s+", "-", s)
    return s[:50] or DEFAULT_TITLE


def build_markdown(title: str, text: str, url: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    return f"""---
title: {title}
type: note
platform: zhihu
tags: [{TAG}]
created: {now}
source: {url}
author:
transcriber: SenseVoice-Small
---

# {title}

{text}"""


def main():
    parser = argparse.ArgumentParser(description=f"{PLATFORM} 视频转录")
    parser.add_argument("url", help=f"{PLATFORM} 视频链接")
    parser.add_argument("output", nargs="?", default=".", help="输出目录（位置参数，兼容旧用法）")
    parser.add_argument("--output", "-o", dest="output_opt", help="输出目录")
    args = parser.parse_args()
    output_dir = args.output_opt or args.output

    print("=" * 50, file=sys.stderr)
    print(f"Step 1: Getting {PLATFORM} video info...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    info = get_video_info(args.url)
    title = info["title"]
    print(f"  📺 Title: {title}", file=sys.stderr)

    tmpdir = tempfile.mkdtemp(prefix=f"{TMP_PREFIX}-")
    try:
        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 2: Downloading audio...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        audio_path = download_audio(args.url, tmpdir)

        print("\n" + "=" * 50, file=sys.stderr)
        print("Step 3: Transcribing...", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        text = transcribe_audio(audio_path)

        markdown = build_markdown(title, text, args.url)
        safe_title = sanitize_filename(title)
        output_path = os.path.join(output_dir, f"{safe_title}.md")
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"\n✅ Saved: {output_path}", file=sys.stderr)
        print(output_path)
    except RuntimeError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
