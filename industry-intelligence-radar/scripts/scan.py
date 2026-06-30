#!/usr/bin/env python3
"""
行业情报雷达 - 多源扫描器

零依赖（仅标准库）。从 Hacker News、V2EX 及任意 RSS 源抓取最近内容，
按关键词矩阵过滤、按信号强度分级，输出 Markdown 情报简报。

用法：
    python scan.py                              # 用内置关键词，扫最近 24 小时
    python scan.py --hours 12                   # 只看最近 12 小时
    python scan.py --config keywords.json       # 自定义关键词矩阵 + RSS 源
    python scan.py --output 简报.md             # 写入文件（默认打印到 stdout）

配置文件格式（JSON，全部字段可选）：
    {
      "keywords": {"AI/Agent": ["AI agent", "LLM", "Claude"], ...},
      "high_signal": ["融资", "发布", "launch", "raise"],
      "rss": ["https://www.36kr.com/feed", "https://sspai.com/feed"]
    }
"""

import sys
import json
import argparse
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 chubbyskills-radar"

# 默认关键词矩阵（与 SKILL.md 保持一致，可用 --config 覆盖）
DEFAULT_KEYWORDS = {
    "AI/Agent": ["AI agent", "LLM", "大模型", "Claude", "GPT", "Gemini",
                 "DeepSeek", "MCP", "function calling"],
    "半导体": ["半导体", "芯片", "chip", "semiconductor", "TSMC", "台积电",
             "NVIDIA", "英伟达"],
    "航天": ["航天", "火箭", "卫星", "SpaceX", "星链", "Starlink"],
    "新能源": ["新能源", "电动车", "电池", "特斯拉", "Tesla", "比亚迪"],
    "游戏": ["Steam", "Switch", "PS5", "米哈游", "原神", "黑神话"],
    "跨境电商": ["跨境电商", "TikTok Shop", "SHEIN", "独立站", "DTC"],
    "创业/投资": ["创业", "融资", "投资", "YC", "a16z", "红杉"],
}

# 高信号关键词：命中则标记为 🔴
DEFAULT_HIGH_SIGNAL = [
    "融资", "发布", "政策", "收购", "合作", "IPO", "突破", "开源",
    "raise", "funding", "launch", "release", "acqui", "policy", "breakthrough",
]


def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_hackernews(keywords, since_ts):
    """Hacker News via Algolia API（免费、无需 key）。每个关键词搜近期 story。"""
    items = []
    seen = set()
    for kw in keywords:
        q = urllib.parse.quote(kw)
        url = (f"https://hn.algolia.com/api/v1/search_by_date?query={q}"
               f"&tags=story&numericFilters=created_at_i>{since_ts}&hitsPerPage=15")
        try:
            data = json.loads(http_get(url))
        except Exception as e:
            print(f"  ⚠️  HN 抓取失败 [{kw}]: {e}", file=sys.stderr)
            continue
        for hit in data.get("hits", []):
            oid = hit.get("objectID")
            if not oid or oid in seen:
                continue
            seen.add(oid)
            title = hit.get("title") or hit.get("story_title") or ""
            if not title:
                continue
            link = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
            items.append({
                "title": title,
                "url": link,
                "source": "Hacker News",
                "author": hit.get("author", ""),
                "ts": hit.get("created_at_i", 0),
                "points": hit.get("points", 0),
            })
    return items


def fetch_v2ex():
    """V2EX 官方热门主题 API（无需 key，可能限流，容错处理）。"""
    items = []
    try:
        data = json.loads(http_get("https://www.v2ex.com/api/topics/hot.json"))
    except Exception as e:
        print(f"  ⚠️  V2EX 抓取失败: {e}", file=sys.stderr)
        return items
    for t in data:
        items.append({
            "title": t.get("title", ""),
            "url": t.get("url", ""),
            "source": "V2EX",
            "author": (t.get("member") or {}).get("username", ""),
            "ts": t.get("created", 0),
            "points": t.get("replies", 0),
        })
    return items


def fetch_rss(url):
    """通用 RSS/Atom 抓取（标准库解析，无需 feedparser）。"""
    items = []
    try:
        raw = http_get(url)
        root = ET.fromstring(raw)
    except Exception as e:
        print(f"  ⚠️  RSS 抓取失败 [{url}]: {e}", file=sys.stderr)
        return items

    # RSS 2.0: channel/item ; Atom: entry
    nodes = root.findall(".//item")
    is_atom = False
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        is_atom = True

    for n in nodes:
        if is_atom:
            title = _text(n, "{http://www.w3.org/2005/Atom}title")
            link_el = n.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.get("href") if link_el is not None else ""
            pub = _text(n, "{http://www.w3.org/2005/Atom}updated") or \
                _text(n, "{http://www.w3.org/2005/Atom}published")
        else:
            title = _text(n, "title")
            link = _text(n, "link")
            pub = _text(n, "pubDate")
        items.append({
            "title": title,
            "url": link,
            "source": _domain(url),
            "author": "",
            "ts": _parse_date(pub),
            "points": 0,
        })
    return items


def _text(node, tag):
    el = node.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def _domain(url):
    try:
        return urllib.parse.urlparse(url).netloc or "RSS"
    except Exception:
        return "RSS"


def _parse_date(s):
    if not s:
        return 0
    try:
        return int(parsedate_to_datetime(s).timestamp())
    except Exception:
        return 0


def match_keywords(title, keyword_map):
    """返回命中的领域列表。"""
    hits = []
    low = title.lower()
    for domain, words in keyword_map.items():
        for w in words:
            if w.lower() in low:
                hits.append(domain)
                break
    return hits


def signal_level(title, high_signal):
    low = title.lower()
    return "🔴" if any(w.lower() in low for w in high_signal) else "🟡"


def build_report(items, hours):
    now = datetime.now()
    high = [i for i in items if i["level"] == "🔴"]
    mid = [i for i in items if i["level"] == "🟡"]
    sources = sorted({i["source"] for i in items})

    lines = [f"# 📡 行业情报简报 - {now.strftime('%Y-%m-%d %H:%M')}", ""]
    lines.append(f"> 扫描窗口：最近 {hours} 小时 | 来源：{', '.join(sources) or '无'} "
                 f"| 命中条目：{len(items)}")
    lines.append("")

    def block(title, group):
        out = [f"## {title}", ""]
        if not group:
            out.append("_（无）_\n")
            return out
        for n, it in enumerate(group, 1):
            out.append(f"### {n}. {it['title']}")
            out.append(f"- **来源**：{it['source']}"
                       + (f" @{it['author']}" if it["author"] else ""))
            out.append(f"- **领域**：{', '.join(it['domains']) or '通用'}")
            if it["url"]:
                out.append(f"- **链接**：{it['url']}")
            if it["ts"]:
                t = datetime.fromtimestamp(it["ts"])
                out.append(f"- **时间**：{t.strftime('%m-%d %H:%M')}")
            out.append("")
        return out

    lines += block("🔴 高信号（必须关注）", high)
    lines += block("🟡 中信号（值得了解）", mid)

    # 领域趋势统计
    domain_count = {}
    for it in items:
        for d in it["domains"]:
            domain_count[d] = domain_count.get(d, 0) + 1
    lines += ["## 📈 领域热度", ""]
    if domain_count:
        for d, c in sorted(domain_count.items(), key=lambda x: -x[1]):
            lines.append(f"- {d}：{c} 条")
    else:
        lines.append("_（无）_")
    lines += ["", "## 📊 数据统计", "",
              f"- 扫描源：{len(sources)} 个",
              f"- 命中条目：{len(items)} 条",
              f"- 高信号：{len(high)} 条 | 中信号：{len(mid)} 条", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="行业情报雷达 - 多源扫描器")
    parser.add_argument("--hours", type=int, default=24, help="时效窗口（小时），默认 24")
    parser.add_argument("--config", help="自定义关键词/RSS 源 JSON 文件")
    parser.add_argument("--output", "-o", help="输出文件（默认打印到 stdout）")
    parser.add_argument("--no-v2ex", action="store_true", help="跳过 V2EX")
    args = parser.parse_args()

    keyword_map = DEFAULT_KEYWORDS
    high_signal = DEFAULT_HIGH_SIGNAL
    rss_sources = []
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
        keyword_map = cfg.get("keywords", keyword_map)
        high_signal = cfg.get("high_signal", high_signal)
        rss_sources = cfg.get("rss", [])

    all_keywords = sorted({w for words in keyword_map.values() for w in words})
    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    since_ts = int(since.timestamp())

    print("=" * 50, file=sys.stderr)
    print(f"Phase 1: 多源扫描（最近 {args.hours} 小时）...", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    raw = []
    print("  🔍 Hacker News...", file=sys.stderr)
    raw += fetch_hackernews(all_keywords, since_ts)
    if not args.no_v2ex:
        print("  🔍 V2EX...", file=sys.stderr)
        raw += fetch_v2ex()
    for url in rss_sources:
        print(f"  🔍 RSS {_domain(url)}...", file=sys.stderr)
        raw += fetch_rss(url)

    print(f"  原始条目：{len(raw)}", file=sys.stderr)

    # Phase 2: 过滤（时效 + 关键词 + 去重）
    print("Phase 2: 信号过滤...", file=sys.stderr)
    seen_titles = set()
    items = []
    for it in raw:
        title = (it["title"] or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen_titles:
            continue
        # 时效：有时间戳的才按窗口过滤，无时间戳的（如热门榜）保留
        if it["ts"] and it["ts"] < since_ts:
            continue
        domains = match_keywords(title, keyword_map)
        if not domains:
            continue
        seen_titles.add(key)
        items.append({
            **it,
            "domains": domains,
            "level": signal_level(title, high_signal),
        })

    # 高信号在前，再按热度/时间排序
    items.sort(key=lambda x: (x["level"] != "🔴", -(x["points"] or 0), -(x["ts"] or 0)))
    print(f"  筛选后：{len(items)} 条", file=sys.stderr)

    report = build_report(items, args.hours)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ 简报已写入：{args.output}", file=sys.stderr)
        print(args.output)
    else:
        print(report)


if __name__ == "__main__":
    main()
