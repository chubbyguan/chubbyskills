#!/usr/bin/env python3
"""
X（Twitter）推文采集 → 统一 frontmatter Markdown

输入推文链接，通过 X 官方嵌入用的 syndication API（无需登录）抓取正文、作者、
互动数据、图片、视频，并按内容类型分流：
  - 图文/纯文字推文：保存正文 + 图片下载到本地嵌入
  - 视频推文：提取视频直链 → ffmpeg 抽音频 → SenseVoice 转录为文字稿

用法：
    python fetch_tweet.py "https://x.com/user/status/1234567890"
    python fetch_tweet.py "https://twitter.com/user/status/1234567890" -o ./out
    python fetch_tweet.py "链接" --no-images   # 图文只留图片链接
    python fetch_tweet.py "链接" --no-video    # 视频不转录，只留视频链接

图文采集零依赖；视频转录需要 funasr + ffmpeg（与抖音/B站/小红书同一套，延迟导入）。
注：syndication 是非官方公开端点，受限/已删/成人内容可能取不到。
"""

import sys
import os
import re
import json
import math
import argparse
import subprocess
import tempfile
import shutil
import urllib.request
from datetime import datetime


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def extract_tweet_id(url):
    m = re.search(r"/status(?:es)?/(\d+)", url)
    if m:
        return m.group(1)
    if url.isdigit():
        return url
    raise ValueError(f"无法从输入中提取推文 ID：{url}")


def _to_base36(n):
    """模拟 JS Number.prototype.toString(36)（含小数部分）。"""
    int_part = int(n)
    frac = n - int_part
    s = ""
    ip = int_part
    if ip == 0:
        s = "0"
    while ip > 0:
        s = _B36[ip % 36] + s
        ip //= 36
    fs = ""
    cnt = 0
    while frac > 0 and cnt < 30:
        frac *= 36
        d = int(frac)
        fs += _B36[d]
        frac -= d
        cnt += 1
    return s + ("." + fs if fs else "")


def make_token(tweet_id):
    """X 嵌入端点要求的 token：((id/1e15)*pi) 转 base36 后去掉 0 和小数点。"""
    n = (int(tweet_id) / 1e15) * math.pi
    return _to_base36(n).replace("0", "").replace(".", "")


def fetch_tweet(tweet_id):
    token = make_token(tweet_id)
    url = (f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
           f"&lang=en&token={token}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def extract_video_url(tw):
    """从推文 JSON 提取最高码率的 mp4 直链。返回 url 或 None。"""
    variants = []
    v = tw.get("video") or {}
    variants += v.get("variants") or []
    for md in (tw.get("mediaDetails") or []):
        variants += ((md.get("video_info") or {}).get("variants") or [])
    mp4 = []
    for x in variants:
        ctype = x.get("type") or x.get("content_type") or ""
        src = x.get("src") or x.get("url")
        if "mp4" in ctype and src:
            mp4.append((x.get("bitrate", 0), src))
    if not mp4:
        return None
    mp4.sort(reverse=True)
    return mp4[0][1]


def _big(u):
    return re.sub(r"name=\w+", "name=large", u) if "name=" in u else u


def extract_photos(tw):
    photos, seen = [], set()
    for p in (tw.get("photos") or []):
        u = p.get("url")
        if u and u not in seen:
            seen.add(u)
            photos.append(_big(u))
    for md in (tw.get("mediaDetails") or []):  # 兜底：部分推文图片在 mediaDetails
        if md.get("type") == "photo":
            u = md.get("media_url_https")
            if u and u not in seen:
                seen.add(u)
                photos.append(_big(u))
    return photos


def parse_tweet(tw):
    user = tw.get("user") or {}
    text = (tw.get("text") or tw.get("full_text") or "").strip()
    video_url = extract_video_url(tw)
    photos = extract_photos(tw)

    # X Article（长文章）：syndication 只给标题+预览+封面，全文需登录另抓
    article = tw.get("article") or {}
    article_title = ""
    if article:
        article_title = (article.get("title") or "").strip()
        preview = (article.get("preview_text") or "").strip()
        if preview:
            text = preview
        cover = ((article.get("cover_media") or {}).get("media_info") or {}).get("original_img_url")
        if cover and not photos:
            photos = [cover]

    tags = re.findall(r"#(\w+)", text)
    if article:
        note_type = "article"
    elif video_url:
        note_type = "video"
    elif photos:
        note_type = "image"
    else:
        note_type = "text"
    created = (tw.get("created_at") or "")[:10]
    return {
        "text": text,
        "author": (user.get("name") or "").strip(),
        "screen_name": (user.get("screen_name") or "").strip(),
        "created": created,
        "likes": tw.get("favorite_count", ""),
        "replies": tw.get("conversation_count", ""),
        "tags": tags,
        "photos": photos,
        "video_url": video_url,
        "note_type": note_type,
        "article_title": article_title,
    }


def download_images(urls, out_dir, base):
    refs = []
    if not urls:
        return refs
    asset_dir = os.path.join(out_dir, f"{base}.assets")
    for i, u in enumerate(urls, 1):
        try:
            os.makedirs(asset_dir, exist_ok=True)
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                blob = resp.read()
            fn = f"img_{i}.jpg"
            with open(os.path.join(asset_dir, fn), "wb") as f:
                f.write(blob)
            print(f"  🖼️  图片 {i}/{len(urls)}（{len(blob) // 1024} KB）", file=sys.stderr)
            refs.append(("local", f"{base}.assets/{fn}"))
        except Exception as e:
            print(f"  ⚠️  图片 {i} 下载失败，保留链接：{e}", file=sys.stderr)
            refs.append(("url", u))
    return refs


def transcribe_video(video_url):
    """下载视频 → ffmpeg 抽音频 → SenseVoice 转录（language=auto，X 多英文）。"""
    tmp = tempfile.mkdtemp(prefix="x-video-")
    try:
        video_path = os.path.join(tmp, "v.mp4")
        print("  ⬇️  下载视频...", file=sys.stderr)
        req = urllib.request.Request(video_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp, open(video_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        print(f"  ✅ 视频 {os.path.getsize(video_path) / 1048576:.1f} MB", file=sys.stderr)

        audio_path = os.path.join(tmp, "a.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "libmp3lame",
             "-q:a", "4", audio_path],
            capture_output=True, timeout=300, check=True)

        print("  🎙️  SenseVoice 转录...", file=sys.stderr)
        from funasr import AutoModel
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
        model = AutoModel(
            model="iic/SenseVoiceSmall", trust_remote_code=True,
            vad_model="fsmn-vad", vad_kwargs={"max_single_segment_time": 30000},
            device="cpu")
        result = model.generate(input=audio_path, language="auto", use_itn=True, batch_size_s=60)
        text = ""
        for r in (result or []):
            if "text" in r:
                text += rich_transcription_postprocess(r["text"]) + "\n\n"
        return text.strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sanitize(name):
    s = re.sub(r'[<>:"/\\|?*\n]', "", name)
    s = re.sub(r"\s+", "-", s)
    return s[:50] or "tweet"


def compute_title(data):
    if data.get("article_title"):
        return data["article_title"][:60]
    first_line = (data["text"].splitlines() or [""])[0].strip()
    if first_line and not first_line.startswith("http"):
        return first_line[:40]
    who = data["author"] or data["screen_name"] or "X"
    return f"{who}的推文"


def build_markdown(data, url, title, image_refs, transcript=None):
    now = datetime.now().strftime("%Y-%m-%d")
    tags = ["X"] + data["tags"]
    tags_yaml = ", ".join(tags)
    handle = f"@{data['screen_name']}" if data["screen_name"] else ""
    author_line = f"{data['author']} {handle}".strip() or "未知"
    stat = f"👍 {data['likes']} · 💬 {data['replies']}"
    body = data["text"] or "（推文无正文）"
    if data["note_type"] == "article":
        body = "> 📄 X 长文章，以下为预览，全文见上方 source 链接\n\n" + body

    lines = [
        "---",
        f"title: {title}",
        "type: note",
        "platform: x",
        f"note_type: {data['note_type']}",
        f"source: {url}",
        f"author: {author_line}",
        f"created: {data['created'] or now}",
        f"tags: [{tags_yaml}]",
        f"likes: {data['likes']}",
        f"replies: {data['replies']}",
        "---",
        "",
        f"# {title}",
        "",
        f"> 👤 {author_line} | {stat}",
        "",
        body,
    ]
    if transcript:
        lines += ["", "## 视频文字稿", "", transcript]
    elif data["note_type"] == "video" and data["video_url"]:
        lines += ["", "## 视频", "", f"- {data['video_url']}"]
    if image_refs:
        lines += ["", "## 图片", ""]
        for kind, val in image_refs:
            lines.append(f"![]({val})" if kind == "local" else f"- {val}")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="X(Twitter) 推文采集")
    parser.add_argument("url", help="推文链接（x.com / twitter.com）或纯推文 ID")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument("--no-images", action="store_true", help="图文不下载图片，只留链接")
    parser.add_argument("--no-video", action="store_true", help="视频不转录，只留视频链接")
    args = parser.parse_args()

    tweet_id = extract_tweet_id(args.url)
    source_url = args.url if not args.url.isdigit() else f"https://x.com/i/status/{tweet_id}"
    print(f"  🌐 抓取推文 {tweet_id}...", file=sys.stderr)
    try:
        tw = fetch_tweet(tweet_id)
    except Exception as e:
        print(f"❌ 请求失败：{e}", file=sys.stderr)
        print("   X syndication 端点可能临时不可用，或该推文受限/已删除。", file=sys.stderr)
        sys.exit(1)
    if not tw or (tw.get("text") is None and not tw.get("mediaDetails")):
        print("❌ 未取到推文内容（受限/已删除/端点变化）。", file=sys.stderr)
        sys.exit(1)

    data = parse_tweet(tw)
    title = compute_title(data)
    base = sanitize(title)
    os.makedirs(args.output, exist_ok=True)

    transcript = None
    if data["note_type"] == "video" and data["video_url"] and not args.no_video:
        print("  🎬 视频推文，开始转录...", file=sys.stderr)
        try:
            transcript = transcribe_video(data["video_url"])
            print(f"  ✅ 转录完成（{len(transcript)} 字）", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️  视频转录失败：{e}", file=sys.stderr)
            print("     需 ffmpeg + funasr；或加 --no-video 只存视频链接", file=sys.stderr)

    image_refs = []
    if not transcript and data["photos"] and not args.no_images:
        print(f"  ⬇️  下载 {len(data['photos'])} 张图片...", file=sys.stderr)
        image_refs = download_images(data["photos"], args.output, base)
    elif not transcript and data["photos"]:
        image_refs = [("url", u) for u in data["photos"]]

    markdown = build_markdown(data, source_url, title, image_refs, transcript)
    output_path = os.path.join(args.output, f"{base}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    local_n = sum(1 for k, _ in image_refs if k == "local")
    kind = "视频(已转录)" if transcript else data["note_type"]
    print(f"✅ Saved: {output_path}", file=sys.stderr)
    print(f"  类型：{kind} | 作者：{data['author'] or '未知'} | 👍 {data['likes']} 💬 {data['replies']} "
          f"| 本地图片：{local_n} 张", file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
