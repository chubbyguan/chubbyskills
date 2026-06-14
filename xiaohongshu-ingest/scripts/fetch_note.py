#!/usr/bin/env python3
"""
小红书笔记采集 → 统一 frontmatter Markdown

输入笔记链接（含 xhslink.com 短链），抓取标题、正文、标签、作者、互动数据、
图片链接，输出统一 frontmatter 的 Markdown，便于入库与后续爆款拆解。

用法：
    python fetch_note.py "https://www.xiaohongshu.com/explore/xxxx"
    python fetch_note.py "http://xhslink.com/xxxx" -o ./out

⚠️ 小红书反爬严格：未登录访问常被风控墙拦。强烈建议提供 cookie：
    export XHS_COOKIE="从浏览器复制的 cookie 字符串"

零依赖（仅标准库）。若页面结构变化导致解析失败，脚本会回退到 og 元标签，
仍失败时给出明确提示——可手动粘贴正文交给 analyze_hook.py 继续拆解。
"""

import sys
import os
import re
import json
import argparse
import subprocess
import tempfile
import shutil
import urllib.request
from datetime import datetime


# 小红书对移动端 UA 更宽容
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")


def http_get(url, cookie=None, timeout=20):
    headers = {"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace"), resp.geturl()


def _balanced_json(s):
    """从首个 '{' 起做括号配平提取（正确跳过字符串内的花括号），返回 JSON 文本。"""
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(s):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[:i + 1]
    return None


def extract_initial_state(html):
    """从页面提取 window.__INITIAL_STATE__ 的 JSON。返回 dict 或 None。

    用括号配平而非 `}</script>` 正则——真实页面里 JSON 后面常紧跟其它 JS，
    正则会失配。配平能稳定截出完整对象。
    """
    idx = html.find("__INITIAL_STATE__")
    if idx == -1:
        return None
    brace = html.find("{", idx)
    if brace == -1:
        return None
    raw = _balanced_json(html[brace:])
    if not raw:
        return None
    # 值位置的 undefined 替换为合法 JSON null，避免污染字符串正文里出现的该词。
    raw = re.sub(r"([:,\[]\s*)undefined\b", r"\1null", raw)
    try:
        return json.loads(raw)
    except Exception:
        return None


def find_note(state):
    """从 __INITIAL_STATE__ 里定位 note 详情对象。

    小红书的 state 结构随版本/端变化（note.noteDetailMap / noteData.data / ...），
    所以先走已知路径，再用递归兜底：搜整个 state 找含 interactInfo + (desc/title)
    的对象——即笔记本体。这样结构怎么变都能命中。
    """
    try:
        note_map = state["note"]["noteDetailMap"]
        for v in note_map.values():
            if isinstance(v, dict) and v.get("note"):
                return v["note"]
    except Exception:
        pass

    found = [None]

    def walk(o):
        if found[0] is not None:
            return
        if isinstance(o, dict):
            if "interactInfo" in o and ("desc" in o or "title" in o):
                found[0] = o
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(state)
    return found[0]


def extract_video_url(note):
    """从 note.video 提取可下载的视频直链（masterUrl）。结构多变，做防御性遍历。"""
    video = note.get("video") or {}
    stream = (video.get("media") or {}).get("stream") or {}
    for codec in ("h264", "h265", "h266", "av1"):
        for item in (stream.get(codec) or []):
            if item.get("masterUrl"):
                return item["masterUrl"]
    found = [None]

    def walk(o):
        if found[0] is not None:
            return
        if isinstance(o, dict):
            if isinstance(o.get("masterUrl"), str):
                found[0] = o["masterUrl"]
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(video)
    return found[0]


def transcribe_video(video_url, cookie):
    """下载小红书视频 → ffmpeg 抽音频 → SenseVoice 转录，返回文字稿。

    需要 ffmpeg 与 funasr（与抖音/B站转录同一套依赖）；funasr 延迟导入，
    图文笔记完全不触发，因此纯图文使用者无需安装。
    """
    tmp = tempfile.mkdtemp(prefix="xhs-video-")
    try:
        headers = {"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"}
        if cookie:
            headers["Cookie"] = cookie
        video_path = os.path.join(tmp, "v.mp4")
        print("  ⬇️  下载视频...", file=sys.stderr)
        req = urllib.request.Request(video_url, headers=headers)
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
        result = model.generate(input=audio_path, language="zh", use_itn=True, batch_size_s=60)
        text = ""
        for r in (result or []):
            if "text" in r:
                text += rich_transcription_postprocess(r["text"]) + "\n\n"
        return text.strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def parse_from_state(note):
    img_list = note.get("imageList") or []
    images = []
    for img in img_list:
        u = img.get("urlDefault") or img.get("url") or ""
        if not u:
            for info in (img.get("infoList") or []):
                if info.get("url"):
                    u = info["url"]
                    break
        if u:
            images.append(u)
    interact = note.get("interactInfo") or {}
    user = note.get("user") or {}
    return {
        "title": (note.get("title") or "").strip(),
        "desc": (note.get("desc") or "").strip().replace("\xa0", " "),
        "author": (user.get("nickName") or user.get("nickname") or "").strip(),
        "tags": [t.get("name", "") for t in (note.get("tagList") or []) if t.get("name")],
        "likes": interact.get("likedCount", ""),
        "collects": interact.get("collectedCount", ""),
        "comments": interact.get("commentCount", ""),
        "images": images,
        "video_url": extract_video_url(note),
        "note_type": "video" if (note.get("type") == "video" or extract_video_url(note)) else "image",
    }


def parse_from_meta(html):
    """兜底：从 og 元标签提取标题/正文。"""
    def meta(prop):
        m = re.search(
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\'](.*?)["\']',
            html, re.IGNORECASE)
        return (m.group(1).strip() if m else "")
    title = meta("og:title")
    desc = meta("og:description")
    if not title and not desc:
        return None
    return {"title": title, "desc": desc, "author": "", "tags": [],
            "likes": "", "collects": "", "comments": "", "images": [],
            "video_url": None, "note_type": "image"}


def build_markdown(data, url, title, image_refs, transcript=None):
    now = datetime.now().strftime("%Y-%m-%d")
    tags = ["小红书"] + data["tags"]
    tags_yaml = ", ".join(tags)
    stat = f"👍 {data['likes']} · ⭐ {data['collects']} · 💬 {data['comments']}"

    lines = [
        "---",
        f"title: {title}",
        "type: note",
        "platform: xiaohongshu",
        f"note_type: {data['note_type']}",
        f"source: {url}",
        f"author: {data['author']}",
        f"created: {now}",
        f"tags: [{tags_yaml}]",
        f"likes: {data['likes']}",
        f"collects: {data['collects']}",
        f"comments: {data['comments']}",
        "---",
        "",
        f"# {title}",
        "",
        f"> 👤 {data['author'] or '未知'} | {stat}",
        "",
        data["desc"] or "（正文为空，可能被反爬拦截，建议配置 XHS_COOKIE）",
    ]
    if transcript:
        lines += ["", "## 视频文字稿", "", transcript]
    elif data["note_type"] == "video" and data["video_url"]:
        lines += ["", "## 视频", "", f"- {data['video_url']}"]
    if image_refs:
        lines += ["", "## 图片", ""]
        for kind, val in image_refs:
            # 图文笔记的正文常在图里，本地化嵌入后在 Markdown 直接可见
            lines.append(f"![]({val})" if kind == "local" else f"- {val}")
    lines.append("")
    return "\n".join(lines)


def sanitize(name):
    s = re.sub(r'[<>:"/\\|?*\n]', "", name)
    s = re.sub(r"\s+", "-", s)
    return s[:50] or "xhs-note"


def compute_title(data):
    return data["title"] or (data["desc"][:30] if data["desc"] else "小红书笔记")


def download_images(urls, out_dir, base, cookie):
    """下载图片到 <base>.assets/ 子目录。返回 [(kind, value)]：
    kind=local 用本地相对路径嵌入；某张下载失败则回退 kind=url 保留链接。"""
    refs = []
    if not urls:
        return refs
    asset_dir = os.path.join(out_dir, f"{base}.assets")
    for i, u in enumerate(urls, 1):
        try:
            os.makedirs(asset_dir, exist_ok=True)
            headers = {"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"}
            if cookie:
                headers["Cookie"] = cookie
            req = urllib.request.Request(u, headers=headers)
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


def main():
    parser = argparse.ArgumentParser(description="小红书笔记采集")
    parser.add_argument("url", help="小红书笔记链接或 xhslink 短链")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument("--no-images", action="store_true", help="不下载图片，只在 Markdown 里保留图片链接")
    parser.add_argument("--no-video", action="store_true", help="视频笔记不转录，只在 Markdown 里保留视频链接")
    args = parser.parse_args()

    cookie = os.environ.get("XHS_COOKIE")
    if not cookie:
        print("  ⚠️  未设置 XHS_COOKIE，未登录访问可能被风控拦截", file=sys.stderr)

    print(f"  🌐 抓取：{args.url}", file=sys.stderr)
    try:
        html, final_url = http_get(args.url, cookie)
    except Exception as e:
        print(f"❌ 请求失败：{e}", file=sys.stderr)
        sys.exit(1)

    if "请通过小红书" in html or "verify" in final_url.lower():
        print("❌ 被风控拦截。请设置 XHS_COOKIE 后重试，或手动复制正文交给 analyze_hook.py",
              file=sys.stderr)
        sys.exit(1)

    state = extract_initial_state(html)
    data = None
    if state:
        note = find_note(state)
        if note:
            data = parse_from_state(note)
    if not data or not (data["desc"] or data["title"]):
        print("  ⚠️  结构化解析失败，回退 og 元标签", file=sys.stderr)
        data = parse_from_meta(html) or data
    if not data or not (data["desc"] or data["title"]):
        print("❌ 无法解析笔记内容（页面结构可能已变化或被拦截）。"
              "建议：① 设置 XHS_COOKIE；② 手动复制正文走 analyze_hook.py", file=sys.stderr)
        sys.exit(1)

    title = compute_title(data)
    base = sanitize(title)
    os.makedirs(args.output, exist_ok=True)

    transcript = None
    if data["note_type"] == "video" and data["video_url"] and not args.no_video:
        print("  🎬 视频笔记，开始转录...", file=sys.stderr)
        try:
            transcript = transcribe_video(data["video_url"], cookie)
            print(f"  ✅ 转录完成（{len(transcript)} 字）", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️  视频转录失败：{e}", file=sys.stderr)
            print("     需 ffmpeg + funasr；或加 --no-video 只存视频链接", file=sys.stderr)

    image_refs = []
    if not transcript and data["images"] and not args.no_images:
        print(f"  ⬇️  下载 {len(data['images'])} 张图片...", file=sys.stderr)
        image_refs = download_images(data["images"], args.output, base, cookie)
    elif not transcript and data["images"]:
        image_refs = [("url", u) for u in data["images"]]

    markdown = build_markdown(data, final_url, title, image_refs, transcript)
    output_path = os.path.join(args.output, f"{base}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    local_n = sum(1 for k, _ in image_refs if k == "local")
    kind = "视频(已转录)" if transcript else data["note_type"]
    print(f"✅ Saved: {output_path}", file=sys.stderr)
    print(f"  类型：{kind} | 作者：{data['author'] or '未知'} | 👍 {data['likes']} ⭐ {data['collects']} "
          f"| 本地图片：{local_n} 张", file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
