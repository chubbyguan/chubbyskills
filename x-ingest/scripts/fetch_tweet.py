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
    python fetch_tweet.py "链接" --fallback-json tweet.json --fallback-only
    python fetch_tweet.py "链接" --cookies "auth_token=...; ct0=..."  # 长文章抓全文

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
import time
import urllib.request
import urllib.parse
from datetime import datetime


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"

# X Web 端公开 bearer token（匿名客户端凭证，不含用户身份）。
_GRAPHQL_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)
# TweetResultByRestId 的 queryId 会随 X 前端发版轮换，按新到旧依次尝试。
_TWEET_RESULT_QUERY_IDS = [
    "DJS3BdhUhcaEpZ7B7irJDg",
    "V3vfsYzNEyD9tsf4xoPhgw",
]
THREAD_REQUEST_DELAY_SECONDS = 1


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
    url = (
        f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
        f"&lang=en&token={token}"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def parse_syndication_timeline(html):
    """Extract tweets from the anonymous profile-timeline syndication page."""
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise ValueError("syndication profile timeline did not contain __NEXT_DATA__")
    payload = json.loads(match.group(1))
    page_props = ((payload.get("props") or {}).get("pageProps") or {})
    timeline = page_props.get("timeline")
    if not isinstance(timeline, dict) or not isinstance(timeline.get("entries"), list):
        raise ValueError("syndication profile timeline has an unexpected data shape")
    entries = timeline["entries"]
    tweets = []
    for entry in entries:
        tweet = ((entry.get("content") or {}).get("tweet"))
        if isinstance(tweet, dict):
            tweets.append(tweet)
    return tweets


def fetch_author_timeline(screen_name):
    """Fetch an author's public syndication timeline, including replies."""
    timeline_url = (
        "https://syndication.twitter.com/srv/timeline-profile/screen-name/"
        f"{urllib.parse.quote(screen_name)}"
    )
    query = urllib.parse.urlencode(
        {
            "lang": "en",
            "showReplies": "true",
            "showHeader": "false",
            "transparent": "false",
        }
    )
    req = urllib.request.Request(
        f"{timeline_url}?{query}",
        headers={"User-Agent": UA, "Accept": "text/html"},
    )
    time.sleep(THREAD_REQUEST_DELAY_SECONDS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", "replace")
    return parse_syndication_timeline(html)


def _tweet_id(tweet):
    return str(tweet.get("id_str") or tweet.get("id") or "")


def _reply_to_id(tweet):
    return str(
        tweet.get("in_reply_to_status_id_str")
        or tweet.get("in_reply_to_status_id")
        or ""
    )


def _conversation_id(tweet):
    return str(tweet.get("conversation_id_str") or tweet.get("conversation_id") or "")


def collect_thread_tweets(root_id, root_tweet, timeline_tweets):
    """Follow the author's direct self-reply chain from the root tweet."""
    root_user = root_tweet.get("user") or {}
    root_author_id = str(root_user.get("id_str") or root_user.get("id") or "")
    root_screen_name = str(root_user.get("screen_name") or "").casefold()
    conversation_id = _conversation_id(root_tweet) or str(root_id)
    candidates = {}
    for tweet in timeline_tweets:
        tweet_id = _tweet_id(tweet)
        user = tweet.get("user") or {}
        author_id = str(user.get("id_str") or user.get("id") or "")
        screen_name = str(user.get("screen_name") or "").casefold()
        same_author = (
            author_id == root_author_id
            if root_author_id and author_id
            else bool(root_screen_name and screen_name == root_screen_name)
        )
        conversation_id = _conversation_id(tweet)
        if (
            tweet_id
            and tweet_id != str(root_id)
            and same_author
            and (
                not _conversation_id(tweet)
                or _conversation_id(tweet) == conversation_id
            )
            and _reply_to_id(tweet)
        ):
            candidates[tweet_id] = tweet

    thread = [root_tweet]
    seen = {str(root_id)}
    parent_id = str(root_id)
    while True:
        replies = [
            tweet
            for tweet_id, tweet in candidates.items()
            if tweet_id not in seen and _reply_to_id(tweet) == parent_id
        ]
        if not replies:
            break
        replies.sort(
            key=lambda tweet: (
                0,
                int(_tweet_id(tweet)),
            )
            if _tweet_id(tweet).isdigit()
            else (1, _tweet_id(tweet))
        )
        next_tweet = replies[0]
        next_id = _tweet_id(next_tweet)
        thread.append(next_tweet)
        seen.add(next_id)
        parent_id = next_id
    return thread


def load_cookies(source):
    """从文件路径 / "k=v; k=v" 字符串解析出 auth_token 和 ct0。"""
    raw = source or ""
    if os.path.isfile(raw):
        with open(raw, encoding="utf-8") as f:
            raw = f.read().strip()
    jar = {}
    for part in re.split(r"[;\n]+", raw):
        if "=" in part:
            k, v = part.split("=", 1)
            jar[k.strip()] = v.strip()
    auth, ct0 = jar.get("auth_token"), jar.get("ct0")
    if not auth or not ct0:
        raise ValueError("cookies 中缺少 auth_token 或 ct0（从浏览器 DevTools 复制）")
    return auth, ct0


def fetch_article_graphql(rest_id, cookies):
    """登录态 GraphQL TweetResultByRestId 抓 Article 本体。返回 result dict 或 None。"""
    auth, ct0 = load_cookies(cookies)
    variables = {
        "tweetId": str(rest_id),
        "withCommunity": False,
        "includePromotedContent": False,
        "withVoice": False,
    }
    features = {
        "articles_preview_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Authorization": f"Bearer {_GRAPHQL_BEARER}",
        "X-Csrf-Token": ct0,
        "X-Twitter-Auth-Type": "OAuth2Session",
        "X-Twitter-Active-User": "yes",
        "Cookie": f"auth_token={auth}; ct0={ct0}",
    }
    for query_id in _TWEET_RESULT_QUERY_IDS:
        url = (
            f"https://x.com/i/api/graphql/{query_id}/TweetResultByRestId"
            f"?variables={urllib.parse.quote(json.dumps(variables))}"
            f"&features={urllib.parse.quote(json.dumps(features))}"
        )
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            print(f"  ⚠️  GraphQL queryId {query_id} 失败：{e}", file=sys.stderr)
            continue
        result = ((payload.get("data") or {}).get("tweetResult") or {}).get("result")
        if result:
            return result
    return None


def _blocks_text(content_state):
    """从 Article 的 content_state blocks 拼接纯文本。"""
    parts = []
    for block in (content_state or {}).get("blocks") or []:
        t = (block.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def extract_article_text(result):
    """从 GraphQL tweetResult.result 提取 Article 标题与全文。返回 (title, text)。"""
    article = (result or {}).get("article") or {}
    article_result = (article.get("article_results") or {}).get("result") or {}
    title = (article_result.get("title") or "").strip()
    text = (article_result.get("plain_text") or "").strip()
    if not text:
        text = _blocks_text(article_result.get("content_state"))
    return title, text


def extract_video_url(tw):
    """从推文 JSON 提取最高码率的 mp4 直链。返回 url 或 None。"""
    variants = []
    v = tw.get("video") or {}
    variants += v.get("variants") or []
    for md in tw.get("mediaDetails") or []:
        variants += (md.get("video_info") or {}).get("variants") or []
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
    for p in tw.get("photos") or []:
        u = p.get("url")
        if u and u not in seen:
            seen.add(u)
            photos.append(_big(u))
    for md in tw.get("mediaDetails") or []:  # 兜底：部分推文图片在 mediaDetails
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
    article_rest_id = ""
    if article:
        article_title = (article.get("title") or "").strip()
        article_rest_id = str(article.get("rest_id") or "")
        preview = (article.get("preview_text") or "").strip()
        if preview:
            text = preview
        cover = ((article.get("cover_media") or {}).get("media_info") or {}).get(
            "original_img_url"
        )
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
        "article_rest_id": article_rest_id,
        "article_is_preview": bool(article),
        "tweet_id": _tweet_id(tw),
    }


def download_images(urls, out_dir, base, filename_prefix=""):
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
            fn = f"{filename_prefix}img_{i}.jpg"
            with open(os.path.join(asset_dir, fn), "wb") as f:
                f.write(blob)
            print(
                f"  🖼️  图片 {i}/{len(urls)}（{len(blob) // 1024} KB）", file=sys.stderr
            )
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
        with (
            urllib.request.urlopen(req, timeout=180) as resp,
            open(video_path, "wb") as f,
        ):
            shutil.copyfileobj(resp, f)
        print(
            f"  ✅ 视频 {os.path.getsize(video_path) / 1048576:.1f} MB", file=sys.stderr
        )

        audio_path = os.path.join(tmp, "a.mp3")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "4",
                audio_path,
            ],
            capture_output=True,
            timeout=300,
            check=True,
        )

        print("  🎙️  SenseVoice 转录...", file=sys.stderr)
        from funasr import AutoModel
        from funasr.utils.postprocess_utils import rich_transcription_postprocess

        model = AutoModel(
            model="iic/SenseVoiceSmall",
            trust_remote_code=True,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cpu",
        )
        result = model.generate(
            input=audio_path, language="auto", use_itn=True, batch_size_s=60
        )
        text = ""
        for r in result or []:
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


def yaml_scalar(value):
    """Encode a string as a YAML-compatible double-quoted scalar."""
    return json.dumps(str(value), ensure_ascii=False)


def build_markdown(data, url, title, image_refs, transcript=None):
    now = datetime.now().strftime("%Y-%m-%d")
    tags = ["X"] + data["tags"]
    tags_yaml = ", ".join(tags)
    handle = f"@{data['screen_name']}" if data["screen_name"] else ""
    author_line = f"{data['author']} {handle}".strip() or "未知"
    likes = _safe_count(data.get("likes"))
    replies = _safe_count(data.get("replies"))
    stat = f"👍 {likes} · 💬 {replies}"
    body = data["text"] or "（推文无正文）"
    if data["note_type"] == "article" and data.get("article_is_preview"):
        body = "> 📄 X 长文章，以下为预览，全文见上方 source 链接\n\n" + body

    lines = [
        "---",
        f"title: {yaml_scalar(title)}",
        "type: note",
        "platform: x",
        f"note_type: {data['note_type']}",
        f"source: {yaml_scalar(url)}",
        f"author: {yaml_scalar(author_line)}",
        f"created: {_safe_date(data.get('created')) or now}",
        f"tags: [{tags_yaml}]",
        f"likes: {likes}",
        f"replies: {replies}",
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


def build_thread_markdown(sections, url, title):
    """Render processed tweets as ordered sections with aggregate thread metadata."""
    root = sections[0]["data"]
    tags = list(
        dict.fromkeys(tag for section in sections for tag in section["data"]["tags"])
    )
    handle = f"@{root['screen_name']}" if root["screen_name"] else ""
    author_line = f"{root['author']} {handle}".strip() or "未知"
    created = _safe_date(root.get("created")) or datetime.now().strftime("%Y-%m-%d")
    tweet_ids = [str(section["data"].get("tweet_id") or "") for section in sections]
    likes = [_safe_count(section["data"].get("likes")) for section in sections]
    replies = [_safe_count(section["data"].get("replies")) for section in sections]
    total_likes = sum(value for value in likes if value != "")
    total_replies = sum(value for value in replies if value != "")
    if not any(value != "" for value in likes):
        total_likes = ""
    if not any(value != "" for value in replies):
        total_replies = ""

    lines = [
        "---",
        f"title: {yaml_scalar(title)}",
        "type: note",
        "platform: x",
        "note_type: thread",
        f"source: {yaml_scalar(url)}",
        f"author: {yaml_scalar(author_line)}",
        f"created: {created}",
        f"tags: [{', '.join(yaml_scalar(tag) for tag in ['X'] + tags)}]",
        f"thread_count: {len(sections)}",
        f"thread_ids: [{', '.join(yaml_scalar(tweet_id) for tweet_id in tweet_ids)}]",
        f"likes: {total_likes}",
        f"replies: {total_replies}",
        "---",
        "",
        f"# {title}",
    ]
    for index, section in enumerate(sections, 1):
        data = section["data"]
        section_author = data["author"] or data["screen_name"] or "未知"
        section_handle = f"@{data['screen_name']}" if data["screen_name"] else ""
        section_author_line = f"{section_author} {section_handle}".strip()
        likes_count = _safe_count(data.get("likes"))
        replies_count = _safe_count(data.get("replies"))
        body = data["text"] or "（推文无正文）"
        if data["note_type"] == "article" and data.get("article_is_preview"):
            body = "> 📄 X 长文章，以下为预览，全文见原文链接\n\n" + body
        lines += [
            "",
            f"## 推文 {index}",
            "",
            f"> 👤 {section_author_line or '未知'} | 👍 {likes_count} · 💬 {replies_count}",
            "",
            body,
        ]
        if section.get("transcript"):
            lines += ["", "### 视频文字稿", "", section["transcript"]]
        elif data["note_type"] == "video" and data.get("video_url"):
            lines += ["", "### 视频", "", f"- {data['video_url']}"]
        if section.get("image_refs"):
            lines += ["", "### 图片", ""]
            for kind, value in section["image_refs"]:
                lines.append(f"![]({value})" if kind == "local" else f"- {value}")
    lines.append("")
    return "\n".join(lines)


def save_thread_markdown(sections, source_url, output_dir, title):
    base = sanitize(title)
    os.makedirs(output_dir, exist_ok=True)
    markdown = build_thread_markdown(sections, source_url, title)
    output_path = os.path.join(output_dir, f"{base}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return output_path


def read_fallback_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def read_fallback_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _first_present(mapping, *keys):
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return ""


def _safe_count(value):
    """Return a non-negative integer count or an empty value."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        return ""
    return count if count >= 0 else ""


def _safe_date(value):
    """Return a YYYY-MM-DD date without accepting frontmatter syntax."""
    candidate = str(value or "")[:10]
    return candidate if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate) else ""


def _first_record(value):
    if isinstance(value, list):
        return value[0] if value and isinstance(value[0], dict) else None
    return value if isinstance(value, dict) else None


def _tweet_record(payload):
    record = _first_record(payload)
    if record is None:
        raise ValueError(
            "fallback JSON must contain an object or a non-empty object list"
        )

    for _ in range(4):
        nested = next(
            (
                candidate
                for key in ("data", "result", "item")
                if (candidate := _first_record(record.get(key))) is not None
            ),
            None,
        )
        if nested is None:
            break
        record = nested

    tweet = _first_record(record.get("tweet"))
    if tweet is None:
        tweet = _first_record(record.get("tweets"))
    if tweet is not None:
        tweet = dict(tweet)
        if not _first_present(tweet, "author", "user"):
            outer_author = _first_present(record, "author", "user")
            if outer_author:
                tweet["author"] = outer_author
        return tweet
    return record


def build_json_fallback_data(payload, title):
    record = _tweet_record(payload)
    text = str(
        _first_present(record, "text", "fullText", "full_text", "content", "tweet_text")
    ).strip()
    if not text:
        raise ValueError("fallback JSON does not contain tweet text")

    author = _first_present(record, "author", "user")
    if isinstance(author, dict):
        author_name = str(
            _first_present(author, "name", "displayName", "display_name")
        ).strip()
        screen_name = (
            str(
                _first_present(
                    author,
                    "screenName",
                    "screen_name",
                    "userName",
                    "username",
                    "handle",
                )
            )
            .lstrip("@")
            .strip()
        )
    else:
        author_name = str(author).strip()
        screen_name = (
            str(
                _first_present(
                    record,
                    "screenName",
                    "screen_name",
                    "userName",
                    "username",
                    "handle",
                )
            )
            .lstrip("@")
            .strip()
        )

    metrics = record.get("public_metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    created = _safe_date(
        _first_present(record, "createdAt", "created_at", "created", "date")
    )
    likes = _first_present(
        record,
        "favoriteCount",
        "favorite_count",
        "likeCount",
        "like_count",
        "likes",
    )
    if likes == "":
        likes = _first_present(metrics, "likeCount", "like_count", "likes")
    replies = _first_present(
        record,
        "conversationCount",
        "conversation_count",
        "replyCount",
        "reply_count",
        "replies",
    )
    if replies == "":
        replies = _first_present(metrics, "replyCount", "reply_count", "replies")
    return {
        "text": text,
        "author": author_name,
        "screen_name": screen_name,
        "created": created,
        "likes": _safe_count(likes),
        "replies": _safe_count(replies),
        "tags": re.findall(r"#(\w+)", text),
        "photos": [],
        "video_url": None,
        "note_type": "text",
        "article_title": title or "",
        "article_rest_id": "",
        "article_is_preview": False,
    }


def build_fallback_data(text, title):
    return {
        "text": text,
        "author": "",
        "screen_name": "",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "likes": "",
        "replies": "",
        "tags": re.findall(r"#(\w+)", text),
        "photos": [],
        "video_url": None,
        "note_type": "text",
        "article_title": title or "",
        "article_rest_id": "",
        "article_is_preview": False,
    }


def load_fallback_data(args):
    if args.fallback_json:
        return build_json_fallback_data(
            read_fallback_json(args.fallback_json), args.fallback_title
        )
    return build_fallback_data(
        read_fallback_text(args.fallback_text), args.fallback_title
    )


def save_markdown(
    data, source_url, output_dir, title=None, image_refs=None, transcript=None
):
    title = title or compute_title(data)
    base = sanitize(title)
    os.makedirs(output_dir, exist_ok=True)
    markdown = build_markdown(data, source_url, title, image_refs or [], transcript)
    output_path = os.path.join(output_dir, f"{base}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="X(Twitter) 推文采集")
    parser.add_argument("url", help="推文链接（x.com / twitter.com）或纯推文 ID")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument(
        "--no-images", action="store_true", help="图文不下载图片，只留链接"
    )
    parser.add_argument(
        "--no-video", action="store_true", help="视频不转录，只留视频链接"
    )
    parser.add_argument(
        "--thread",
        action="store_true",
        help="沿作者自回复链采集可用的 thread 推文",
    )
    fallback = parser.add_mutually_exclusive_group()
    fallback.add_argument(
        "--fallback-text", help="抓取失败时使用这个 txt/md 文件生成标准 Markdown"
    )
    fallback.add_argument(
        "--fallback-json", help="抓取失败时使用结构化推文 JSON 生成标准 Markdown"
    )
    parser.add_argument("--fallback-title", help="fallback 模式下指定标题")
    parser.add_argument(
        "--cookies",
        help="X 登录 cookie（auth_token 与 ct0），可传文件路径或 'k=v; k=v' 字符串；"
        "也可用环境变量 X_COOKIES。仅用于抓取 X 长文章全文",
    )
    parser.add_argument(
        "--fallback-only",
        action="store_true",
        help="不访问网络，直接使用 fallback 数据",
    )
    args = parser.parse_args()

    if args.thread and (args.fallback_only or args.fallback_text or args.fallback_json):
        parser.error("--thread cannot be combined with fallback data")

    if args.fallback_only:
        if not (args.fallback_text or args.fallback_json):
            parser.error("--fallback-only requires --fallback-text or --fallback-json")
        data = load_fallback_data(args)
        output_path = save_markdown(data, args.url, args.output, args.fallback_title)
        print(f"✅ Saved fallback: {output_path}", file=sys.stderr)
        print(output_path)
        return

    tweet_id = extract_tweet_id(args.url)
    source_url = (
        args.url if not args.url.isdigit() else f"https://x.com/i/status/{tweet_id}"
    )
    print(f"  🌐 抓取推文 {tweet_id}...", file=sys.stderr)
    try:
        tw = fetch_tweet(tweet_id)
    except Exception as e:
        if args.fallback_text or args.fallback_json:
            print(f"  ⚠️  请求失败，改用 fallback 数据：{e}", file=sys.stderr)
            data = load_fallback_data(args)
            output_path = save_markdown(
                data, source_url, args.output, args.fallback_title
            )
            print(f"✅ Saved fallback: {output_path}", file=sys.stderr)
            print(output_path)
            return
        print(f"❌ 请求失败：{e}", file=sys.stderr)
        print(
            "   X syndication 端点可能临时不可用，或该推文受限/已删除。",
            file=sys.stderr,
        )
        print(
            "   可使用 --fallback-text 或 --fallback-json 继续生成标准 Markdown。",
            file=sys.stderr,
        )
        sys.exit(1)
    if not tw or (tw.get("text") is None and not tw.get("mediaDetails")):
        if args.fallback_text or args.fallback_json:
            print("  ⚠️  未取到推文内容，改用 fallback 数据", file=sys.stderr)
            data = load_fallback_data(args)
            output_path = save_markdown(
                data, source_url, args.output, args.fallback_title
            )
            print(f"✅ Saved fallback: {output_path}", file=sys.stderr)
            print(output_path)
            return
        print("❌ 未取到推文内容（受限/已删除/端点变化）。", file=sys.stderr)
        print(
            "   可使用 --fallback-text 或 --fallback-json 继续生成标准 Markdown。",
            file=sys.stderr,
        )
        sys.exit(1)

    data = parse_tweet(tw)
    if not data["tweet_id"]:
        data["tweet_id"] = tweet_id
    thread_tweets = [tw]
    if args.thread:
        screen_name = (tw.get("user") or {}).get("screen_name")
        if not screen_name:
            print(
                "❌ 无法采集 thread：首条推文没有作者用户名，无法读取公开时间线。",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"  🧵 查找 @{screen_name} 的自回复...", file=sys.stderr)
        try:
            timeline = fetch_author_timeline(screen_name)
        except Exception as e:
            print(f"❌ 获取作者公开时间线失败：{e}", file=sys.stderr)
            sys.exit(1)
        thread_tweets = collect_thread_tweets(tweet_id, tw, timeline)
        if len(thread_tweets) == 1:
            print(
                "  ⚠️  未找到后续自回复；公开 syndication 时间线可能不含完整或较早的回复。",
                file=sys.stderr,
            )
        else:
            print(f"  ✅ 找到 {len(thread_tweets)} 条 thread 推文", file=sys.stderr)

    if data["note_type"] == "article" and data.get("article_is_preview"):
        cookies = args.cookies or os.environ.get("X_COOKIES")
        if cookies and data.get("article_rest_id"):
            print("  📄 长文章，尝试登录态抓取全文...", file=sys.stderr)
            try:
                result = fetch_article_graphql(data["article_rest_id"], cookies)
                title, text = extract_article_text(result)
                if text:
                    data["text"] = text
                    data["article_is_preview"] = False
                    if title and not data["article_title"]:
                        data["article_title"] = title
                    print(f"  ✅ 抓到全文（{len(text)} 字）", file=sys.stderr)
                else:
                    print(
                        "  ⚠️  登录态返回中未找到 Article 全文，保留预览",
                        file=sys.stderr,
                    )
            except Exception as e:
                print(f"  ⚠️  登录态抓取失败：{e}，保留预览", file=sys.stderr)
        if data.get("article_is_preview"):
            print(
                "  ⚠️  这是 X 长文章（Article），syndication 端点只返回开头预览，"
                "正文全文缺失！",
                file=sys.stderr,
            )
            print(
                "     补全方式：--cookies 提供登录 cookie 抓全文；"
                "网络不可达 x.com 时手动复制正文用 --fallback-text",
                file=sys.stderr,
            )

    title = compute_title(data)
    base = sanitize(title)
    os.makedirs(args.output, exist_ok=True)

    if args.thread:
        sections = []
        for index, tweet in enumerate(thread_tweets, 1):
            section_data = data if index == 1 else parse_tweet(tweet)
            transcript = None
            if (
                section_data["note_type"] == "video"
                and section_data["video_url"]
                and not args.no_video
            ):
                print(
                    f"  🎬 推文 {index} 为视频，开始转录...", file=sys.stderr
                )
                try:
                    transcript = transcribe_video(section_data["video_url"])
                    print(
                        f"  ✅ 转录完成（{len(transcript)} 字）", file=sys.stderr
                    )
                except Exception as e:
                    print(f"  ⚠️  视频转录失败：{e}", file=sys.stderr)
                    print(
                        "     需 ffmpeg + funasr；或加 --no-video 只存视频链接",
                        file=sys.stderr,
                    )

            image_refs = []
            if not transcript and section_data["photos"] and not args.no_images:
                prefix = f"tweet_{index:02d}_"
                print(
                    f"  ⬇️  推文 {index} 下载 {len(section_data['photos'])} 张图片...",
                    file=sys.stderr,
                )
                image_refs = download_images(
                    section_data["photos"], args.output, base, prefix
                )
            elif not transcript and section_data["photos"]:
                image_refs = [("url", photo) for photo in section_data["photos"]]
            sections.append(
                {
                    "data": section_data,
                    "image_refs": image_refs,
                    "transcript": transcript,
                }
            )

        output_path = save_thread_markdown(
            sections, source_url, args.output, title
        )
        print(f"✅ Saved thread: {output_path}", file=sys.stderr)
        print(output_path)
        return

    transcript = None
    if data["note_type"] == "video" and data["video_url"] and not args.no_video:
        print("  🎬 视频推文，开始转录...", file=sys.stderr)
        try:
            transcript = transcribe_video(data["video_url"])
            print(f"  ✅ 转录完成（{len(transcript)} 字）", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️  视频转录失败：{e}", file=sys.stderr)
            print(
                "     需 ffmpeg + funasr；或加 --no-video 只存视频链接", file=sys.stderr
            )

    image_refs = []
    if not transcript and data["photos"] and not args.no_images:
        print(f"  ⬇️  下载 {len(data['photos'])} 张图片...", file=sys.stderr)
        image_refs = download_images(data["photos"], args.output, base)
    elif not transcript and data["photos"]:
        image_refs = [("url", u) for u in data["photos"]]

    output_path = save_markdown(
        data, source_url, args.output, title, image_refs, transcript
    )

    local_n = sum(1 for k, _ in image_refs if k == "local")
    kind = "视频(已转录)" if transcript else data["note_type"]
    print(f"✅ Saved: {output_path}", file=sys.stderr)
    summary_parts = [
        f"类型：{kind}",
        f"作者：{data['author'] or '未知'}",
        f"👍 {data['likes']} 💬 {data['replies']}",
        f"本地图片：{local_n} 张",
    ]
    print("  " + " | ".join(summary_parts), file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
