#!/usr/bin/env python3
"""Chubby Skills 讨论区活跃度监控。

用法:
    python tools/discussions_radar.py [--days 7] [--output docs/discussion-radar.md]

输出:
    Markdown 简报，包含最近 N 天的讨论数、评论数、最新话题列表。
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "chubbyguan/chubbyskills"
RADAR_PATH = Path(__file__).resolve().parents[1] / "docs" / "discussion-radar.md"


def gh(*args: str) -> dict:
    """Run a gh CLI command and return parsed JSON."""
    p = subprocess.run(
        ["gh"] + list(args),
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        sys.stderr.write(f"gh failed: {p.stderr[:300]}\n")
        return {}
    try:
        return json.loads(p.stdout) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"raw": p.stdout.strip()}


def fetch_discussions(days: int) -> list[dict]:
    """Fetch recent discussions and filter to the last N days on the client side."""
    query = """query {
  repository(owner: "chubbyguan", name: "chubbyskills") {
    discussions(first: 50, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        number
        title
        createdAt
        updatedAt
        comments { totalCount }
        author { login }
        category { name }
      }
    }
  }
}"""
    data = gh("api", "graphql", "-f", f"query={query}")
    nodes = data.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = []
    for d in nodes:
        created = d.get("createdAt") or d.get("updatedAt")
        if not created:
            continue
        try:
            ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts >= cutoff:
            filtered.append(d)
    return filtered


def latest_ts(disc: dict) -> datetime | None:
    raw = disc.get("updatedAt") or disc.get("createdAt")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_report(days: int, discussions: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    total_discussions = len(discussions)
    total_comments = sum(d["comments"]["totalCount"] for d in discussions)

    topics = []
    for d in discussions:
        ts = latest_ts(d)
        age = ""
        if ts:
            delta = now - ts
            age = f"{delta.days}d ago" if delta.days else "today"
        topics.append(
            f"- #{d['number']} [{d['category']['name']}] {d['title']} "
            f"by @{d['author']['login']} — {d['comments']['totalCount']} comments, {age}"
        )

    lines = [
        f"# Discussion Radar — {now.strftime('%Y-%m-%d %H:%M CST')}",
        "",
        f"窗口：最近 {days} 天 | 仓库：{REPO}",
        "",
        "## 指标",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| 讨论数 | {total_discussions} |",
        f"| 评论数 | {total_comments} |",
        "",
    ]

    if total_discussions > 0:
        lines += [
            "## 最新话题",
            "",
            "\n".join(sorted(topics, reverse=True)[:10]),
            "",
        ]
    else:
        lines += [
            "## 结论",
            "",
            "[SILENT] 最近窗口内无新讨论。",
            "",
        ]

    lines += ["---", f"generated_at: {now.isoformat()}", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discussion radar for chubbyskills")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output", type=str, default=str(RADAR_PATH))
    args = parser.parse_args()

    discussions = fetch_discussions(args.days)
    report = build_report(args.days, discussions)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"✅ wrote {out} ({len(discussions)} discussions, {sum(d['comments']['totalCount'] for d in discussions)} comments)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
