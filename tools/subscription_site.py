"""Static daily-report site generator for subscription entries.

`subscribe site build` renders a zero-JS, zero-template-engine static site
(Python `string.Template` only) from the subscription SQLite queue, suitable
for publishing to GitHub Pages.

Public-site content boundary (hard rule): entry titles, source names,
publish times, original links, cluster heat and source health stats only.
Never entry bodies/transcripts, local vault paths, related-note titles, or
any credentials.
"""

from __future__ import annotations

import hashlib
import html
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from string import Template
from typing import Any

try:
    from tools import subscription_digest, subscription_store
except ModuleNotFoundError:
    import subscription_digest
    import subscription_store

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "templates" / "site"

DEFAULT_SITE_NAME = "Chubby 情报站"
INDEX_WINDOW_DAYS = 7
ARCHIVE_WINDOW_DAYS = 30
ABOUT_TEXT = (
    "本站由 chubbyskills 订阅管线自动生成，汇总公开 RSS / Atom / YouTube 频道"
    "的更新并做事件聚簇。条目版权归原发布方所有；本站只做索引与导航，"
    "不转载正文，所有内容请通过原始链接访问来源。生成时间见页脚。"
)
PROJECT_URL = "https://github.com/chubbyguan/chubbyskills"


class SiteError(RuntimeError):
    pass


def collect_site_entries(
    store: "subscription_store.SubscriptionStore", days: int, *, now: str | None = None
) -> list[dict[str, Any]]:
    """All entries in the window regardless of state (site is read-only)."""
    if days < 1 or days > 90:
        raise SiteError("--days must be between 1 and 90")
    stamp = subscription_store.parse_iso(now or subscription_store.now_iso())
    cutoff = (stamp - timedelta(days=days)).replace(microsecond=0).isoformat()
    with store.session() as con:
        rows = con.execute(
            """SELECT id, subscription_id, title, canonical_url,
                      published_at, discovered_at, state
               FROM entries
               WHERE COALESCE(NULLIF(published_at, ''), discovered_at) >= ?
               ORDER BY COALESCE(NULLIF(published_at, ''), discovered_at) DESC, id DESC""",
            (cutoff,),
        ).fetchall()
    return [dict(row) for row in rows]


def compute_source_health(
    store: "subscription_store.SubscriptionStore",
    document: dict[str, Any],
    days: int = 7,
    *,
    now: str | None = None,
) -> list[dict[str, Any]]:
    """Per-source check counts and success rate over the last `days` days."""
    stamp = subscription_store.parse_iso(now or subscription_store.now_iso())
    since = (stamp - timedelta(days=days)).replace(microsecond=0).isoformat()
    with store.session() as con:
        checks = {
            row["subscription_id"]: dict(row)
            for row in con.execute(
                """SELECT subscription_id,
                          COUNT(*) AS checks,
                          SUM(CASE WHEN outcome = 'error' THEN 1 ELSE 0 END) AS errors,
                          MAX(checked_at) AS last_checked_at
                   FROM source_checks WHERE checked_at >= ?
                   GROUP BY subscription_id""",
                (since,),
            ).fetchall()
        }
        states = {
            row["subscription_id"]: dict(row)
            for row in con.execute("SELECT subscription_id, last_checked_at FROM source_state").fetchall()
        }
    rows = []
    for source in document["subscriptions"]:
        item = checks.get(source["id"], {})
        total = int(item.get("checks") or 0)
        errors = int(item.get("errors") or 0)
        rows.append(
            {
                "id": source["id"],
                "name": source["name"],
                "kind": source["kind"],
                "provider": source["provider"],
                "last_checked_at": item.get("last_checked_at")
                or states.get(source["id"], {}).get("last_checked_at")
                or "",
                "checks": total,
                "errors": errors,
                "success_rate": round((total - errors) / total * 100, 1) if total else None,
            }
        )
    return rows


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _safe_href(url: str) -> str:
    """Only http(s) links are emitted; anything else degrades to '#'."""
    if re.match(r"^https?://", url or "", re.IGNORECASE):
        return html.escape(url, quote=True)
    return "#"


def _entry_time(entry: dict[str, Any]) -> str:
    return (entry.get("published_at") or entry.get("discovered_at") or "")[:10]


CHIP_PALETTE = (
    "#e06c60", "#d19a66", "#e5c07b", "#98c379", "#56b6c2",
    "#61afef", "#c678dd", "#be5046", "#7fb5b5", "#c8ae7b",
)


def source_color(source_id: str) -> str:
    """Stable chip color per source, derived from its id."""
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
    return CHIP_PALETTE[int(digest[:8], 16) % len(CHIP_PALETTE)]


def _chip(label: str, color: str) -> str:
    return f'<span class="chip" style="--chip:{color}">{_escape(label)}</span>'


def _heat_badge(cluster: dict[str, Any]) -> str:
    if cluster["heat"] <= 1:
        return ""
    return f'<span class="heat-badge">🔥 ×{cluster["heat"]}</span>'


def _render_card(cluster: dict[str, Any], names: dict[str, str]) -> str:
    entries = cluster["entries"]

    def label(entry: dict[str, Any]) -> str:
        return names.get(entry["subscription_id"], entry["subscription_id"])

    top_chips = " ".join(
        _chip(name, source_color(source_id))
        for source_id, name in sorted(
            {(entry["subscription_id"], label(entry)) for entry in entries}
        )
    )
    latest = _entry_time(entries[0])
    header = (
        f'        <div class="card-top"><time>{_escape(latest)}</time>{top_chips}{_heat_badge(cluster)}</div>'
    )
    # Single-entry cluster whose entry is the representative title: render the
    # title once as the link instead of repeating it in an entries list.
    if len(entries) == 1 and entries[0]["title"] == cluster["title"]:
        entry = entries[0]
        return f"""      <article class="card">
{header}
        <h3 class="card-title"><a href="{_safe_href(entry["canonical_url"])}" rel="noopener">{_escape(entry['title'])}</a></h3>
      </article>"""
    links = "\n".join(
        f'        <li><a href="{_safe_href(entry["canonical_url"])}" rel="noopener">'
        f"{_escape(entry['title'])}</a>"
        f'<span class="entry-meta">{_escape(_entry_time(entry))} · {_escape(label(entry))}</span></li>'
        for entry in entries
    )
    return f"""      <article class="card">
{header}
        <h3 class="card-title">{_escape(cluster['title'])}</h3>
        <ul class="entries">
{links}
        </ul>
      </article>"""


def _render_day_groups(
    clusters: list[dict[str, Any]], names: dict[str, str], empty: str
) -> str:
    if not clusters:
        return f'    <p class="empty">{_escape(empty)}</p>'
    by_day: dict[str, list[dict[str, Any]]] = {}
    for cluster in clusters:
        day = max(_entry_time(entry) for entry in cluster["entries"])
        by_day.setdefault(day, []).append(cluster)
    sections = []
    for day in sorted(by_day, reverse=True):
        day_clusters = by_day[day]
        count = sum(len(cluster["entries"]) for cluster in day_clusters)
        try:
            parsed = datetime.strptime(day, "%Y-%m-%d")
            label = f"{parsed.month}月{parsed.day}日"
        except ValueError:
            label = day
        cards = "\n".join(_render_card(cluster, names) for cluster in day_clusters)
        sections.append(
            f'    <section class="day">\n'
            f'      <h2 class="day-title">{_escape(label)} · {count} 条</h2>\n'
            f"{cards}\n"
            f"    </section>"
        )
    return "\n".join(sections)


def _templates(template_dir: Path | None = None) -> dict[str, Template]:
    directory = Path(template_dir) if template_dir else TEMPLATE_DIR
    result = {}
    for name in ("layout", "index", "archive", "sources", "about"):
        path = directory / f"{name}.html"
        if not path.is_file():
            raise SiteError(f"缺少站点模板：{path}")
        result[name] = Template(path.read_text(encoding="utf-8"))
    return result


def _page(
    templates: dict[str, Template],
    body_template: str,
    *,
    site_name: str,
    base_url: str,
    generated_at: str,
    page_title: str,
    assets: str,
    active: str,
    **slots: str,
) -> str:
    nav = {f"nav_{key}": ' class="active"' if key == active else "" for key in ("today", "archive", "sources", "about")}
    body = templates[body_template].safe_substitute(
        site_name=_escape(site_name), base_url=base_url, assets=assets, **slots
    )
    return templates["layout"].safe_substitute(
        site_name=_escape(site_name),
        page_title=_escape(page_title),
        base_url=base_url,
        assets=assets,
        generated_at=_escape(generated_at),
        project_url=PROJECT_URL,
        content=body,
        **nav,
    )


def _normalize_base_url(value: str) -> str:
    base = (value or "").strip().rstrip("/")
    if base and not re.match(r"^(https?://|/)", base):
        base = "/" + base
    return base


def _assets_prefix(base_url: str, depth: int) -> str:
    """Prefix for CSS/nav links: explicit base-url, else depth-relative so
    the site also works over file:// (`../` from archive pages)."""
    if base_url:
        return base_url
    return "." if depth == 0 else "/".join(".." for _ in range(depth))


def build_site(
    args: Any,
    config: dict[str, Any],
    document: dict[str, Any],
    store,
    *,
    template_dir: Path | None = None,
) -> int:
    vault_root_value = config.get("vault_root")
    if not vault_root_value:
        raise SiteError("需要已配置知识库：先运行 chubby init --vault <知识库根目录>")
    vault_root = Path(vault_root_value).expanduser().resolve()
    days = int(getattr(args, "days", 7) or 7)
    site_name = (getattr(args, "site_name", "") or DEFAULT_SITE_NAME).strip()
    base_url = _normalize_base_url(getattr(args, "base_url", "") or "")
    output_arg = getattr(args, "output", "") or ""
    output_dir = (
        Path(output_arg).expanduser() if output_arg else vault_root / "30_Output" / "site"
    )
    # The site directory is a generated artifact and may be overwritten
    # (unlike digest Markdown, which never overwrites).
    now = subscription_store.now_iso()
    generated_at = now[:19].replace("T", " ")

    entries = collect_site_entries(store, days, now=now)
    names = {item["id"]: item["name"] for item in document["subscriptions"]}
    clusters = subscription_digest.cluster_entries(entries)
    index_cutoff = (
        subscription_store.parse_iso(now) - timedelta(days=INDEX_WINDOW_DAYS)
    ).isoformat()
    index_clusters = [
        cluster
        for cluster in clusters
        if any(
            (entry.get("published_at") or entry.get("discovered_at") or "") >= index_cutoff
            for entry in cluster["entries"]
        )
    ]

    by_date: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_date.setdefault(_entry_time(entry), []).append(entry)
    archive_dates = sorted((date for date in by_date if date), reverse=True)[
        :ARCHIVE_WINDOW_DAYS
    ]

    templates = _templates(template_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "archive").mkdir(exist_ok=True)
    root_assets = _assets_prefix(base_url, 0)
    sub_assets = _assets_prefix(base_url, 1)

    pages = {
        output_dir
        / "index.html": _page(
            templates,
            "index",
            site_name=site_name,
            base_url=base_url,
            generated_at=generated_at,
            page_title=site_name,
            assets=root_assets,
            active="today",
            cards=_render_day_groups(index_clusters, names, f"近 {INDEX_WINDOW_DAYS} 天没有订阅更新。"),
            window=str(INDEX_WINDOW_DAYS),
        ),
        output_dir
        / "sources.html": _page(
            templates,
            "sources",
            site_name=site_name,
            base_url=base_url,
            generated_at=generated_at,
            page_title=f"订阅源 · {site_name}",
            assets=root_assets,
            active="sources",
            rows=_render_source_rows(compute_source_health(store, document, now=now)),
        ),
        output_dir
        / "about.html": _page(
            templates,
            "about",
            site_name=site_name,
            base_url=base_url,
            generated_at=generated_at,
            page_title=f"关于 · {site_name}",
            assets=root_assets,
            active="about",
            about_text=_escape(ABOUT_TEXT),
        ),
    }
    for date in archive_dates:
        day_clusters = subscription_digest.cluster_entries(by_date[date])
        pages[output_dir / "archive" / f"{date}.html"] = _page(
            templates,
            "archive",
            site_name=site_name,
            base_url=base_url,
            generated_at=generated_at,
            page_title=f"{date} · {site_name}",
            assets=sub_assets,
            active="archive",
            date=date,
            cards=_render_day_groups(day_clusters, names, "这一天没有订阅更新。"),
        )

    archive_items = "\n".join(
        f'      <li><a href="{base_url}/archive/{date}.html">{_escape(date)}</a>'
        f'<span class="meta">{len(by_date[date])} 条</span></li>'
        if base_url
        else
        f'      <li><a href="./{date}.html">{_escape(date)}</a>'
        f'<span class="meta">{len(by_date[date])} 条</span></li>'
        for date in archive_dates
    )
    pages[output_dir / "archive" / "index.html"] = _page(
        templates,
        "archive",
        site_name=site_name,
        base_url=base_url,
        generated_at=generated_at,
        page_title=f"归档 · {site_name}",
        assets=sub_assets,
        active="archive",
        date="每日归档",
        cards=f'    <ul class="archive-list">\n{archive_items}\n    </ul>'
        if archive_dates
        else '    <p class="empty">暂无归档。</p>',
    )

    for path, content in pages.items():
        path.write_text(content, encoding="utf-8")
    css_source = (Path(template_dir) if template_dir else TEMPLATE_DIR) / "style.css"
    if not css_source.is_file():
        raise SiteError(f"缺少站点样式：{css_source}")
    shutil.copyfile(css_source, output_dir / "style.css")

    print(f"✅ 站点已生成：{output_dir}")
    print(
        f"   {len(entries)} 条 · {len(clusters)} 个事件 · "
        f"{len(archive_dates)} 天归档 · {len(document['subscriptions'])} 个来源"
    )
    return 0


def _render_source_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '      <tr><td colspan="6" class="empty">暂无订阅源。</td></tr>'
    rendered = []
    for row in rows:
        rate = f"{row['success_rate']}%" if row["success_rate"] is not None else "—"
        rendered.append(
            "      <tr>"
            f"<td>{_escape(row['name'])}</td>"
            f"<td>{_escape(row['kind'])}</td>"
            f"<td>{_escape((row['last_checked_at'] or '')[:16].replace('T', ' '))}</td>"
            f"<td>{row['checks']}</td>"
            f"<td>{row['errors']}</td>"
            f"<td>{rate}</td>"
            "</tr>"
        )
    return "\n".join(rendered)
