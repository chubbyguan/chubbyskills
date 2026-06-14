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


def extract_initial_state(html):
    """从页面提取 window.__INITIAL_STATE__ 的 JSON。返回 dict 或 None。"""
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>", html, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    # 小红书的内联状态是 JS 对象，值位置的 undefined 需替换为合法 JSON null。
    # 只替换 :/,/[ 之后的 undefined，避免污染字符串正文里出现的该词。
    raw = re.sub(r"([:,\[]\s*)undefined\b", r"\1null", raw)
    try:
        return json.loads(raw)
    except Exception:
        return None


def find_note(state):
    """从 __INITIAL_STATE__ 里定位 note 详情对象。结构多变，做防御性遍历。"""
    try:
        note_map = state["note"]["noteDetailMap"]
        for v in note_map.values():
            if isinstance(v, dict) and v.get("note"):
                return v["note"]
    except Exception:
        pass
    return None


def parse_from_state(note):
    img_list = note.get("imageList") or []
    images = []
    for img in img_list:
        u = img.get("urlDefault") or img.get("url") or ""
        if u:
            images.append(u)
    interact = note.get("interactInfo") or {}
    return {
        "title": (note.get("title") or "").strip(),
        "desc": (note.get("desc") or "").strip(),
        "author": ((note.get("user") or {}).get("nickname") or "").strip(),
        "tags": [t.get("name", "") for t in (note.get("tagList") or []) if t.get("name")],
        "likes": interact.get("likedCount", ""),
        "collects": interact.get("collectedCount", ""),
        "comments": interact.get("commentCount", ""),
        "images": images,
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
            "likes": "", "collects": "", "comments": "", "images": []}


def build_markdown(data, url):
    now = datetime.now().strftime("%Y-%m-%d")
    title = data["title"] or (data["desc"][:30] if data["desc"] else "小红书笔记")
    tags = ["小红书"] + data["tags"]
    tags_yaml = ", ".join(tags)
    stat = f"👍 {data['likes']} · ⭐ {data['collects']} · 💬 {data['comments']}"

    lines = [
        "---",
        f"title: {title}",
        "type: note",
        "platform: xiaohongshu",
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
    if data["images"]:
        lines += ["", "## 图片"]
        lines += [f"- {u}" for u in data["images"]]
    lines.append("")
    return "\n".join(lines), title


def sanitize(name):
    s = re.sub(r'[<>:"/\\|?*\n]', "", name)
    s = re.sub(r"\s+", "-", s)
    return s[:50] or "xhs-note"


def main():
    parser = argparse.ArgumentParser(description="小红书笔记采集")
    parser.add_argument("url", help="小红书笔记链接或 xhslink 短链")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
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

    markdown, title = build_markdown(data, final_url)
    os.makedirs(args.output, exist_ok=True)
    output_path = os.path.join(args.output, f"{sanitize(title)}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"✅ Saved: {output_path}", file=sys.stderr)
    print(f"  作者：{data['author'] or '未知'} | 👍 {data['likes']} ⭐ {data['collects']}",
          file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
