"""Daily intelligence digest for subscription entries.

Zero-LLM by default: a plain brief (title / time / source / link) built from the
subscription SQLite queue. `--enrich` adds an optional DeepSeek layer
(prescreen -> score -> Chinese summary) whose prompts live in
`templates/digest-prompts/` so standards can change without code changes.
Model-generated content is always marked, and every item keeps its original
link; entries already ingested link to the local note instead.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from tools import subscription_store, vault_index
except ModuleNotFoundError:
    import subscription_store
    import vault_index

REPO_ROOT = Path(__file__).resolve().parents[1]
try:
    from chubby_common import llm
except ModuleNotFoundError:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from chubby_common import llm

PROMPT_DIR = REPO_ROOT / "templates" / "digest-prompts"
PROMPT_FILES = ("prescreen", "score", "summary")

# Entries worth reporting: anything actively flowing through the queue or
# already processed. `seen` baseline rows and user-skipped rows are noise here.
DIGEST_STATES = (
    "discovered",
    "queued",
    "ingesting",
    "succeeded",
    "retry_wait",
    "index_retry",
    "failed_terminal",
)

DEFAULT_CLUSTER_THRESHOLD = 0.5
MAX_ENRICH_CLUSTERS = 10

# Cluster heat decays with age (adapted from AIHOT's event-based trending):
# inside HEAT_FRESH_HOURS every distinct source counts once, up to
# HEAT_WINDOW_HOURS it counts half, and past that it stops contributing.
# Without this a five-source story from last week outranks a three-source
# story from this morning, which is exactly the multi-day site view.
HEAT_FRESH_HOURS = 24
HEAT_WINDOW_HOURS = 48
HEAT_AGED_WEIGHT = 0.5

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "how", "i", "in", "is", "it", "its", "my", "not", "of", "on",
    "or", "so", "the", "this", "to", "was", "what", "why", "with", "you",
    "your",
}

WORD_RE = re.compile(r"[a-z0-9]+")
CJK_RE = re.compile(r"[一-鿿]")


class DigestError(RuntimeError):
    pass


def title_tokens(title: str) -> set[str]:
    """Normalized keyword tokens: lowercase ASCII words plus CJK bigrams."""
    lowered = (title or "").lower()
    tokens = {word for word in WORD_RE.findall(lowered) if word not in STOPWORDS}
    cjk = "".join(CJK_RE.findall(lowered))
    tokens.update(cjk[index : index + 2] for index in range(len(cjk) - 1))
    return tokens


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def collect_window_entries(
    store: "subscription_store.SubscriptionStore", days: int, *, now: str | None = None
) -> list[dict[str, Any]]:
    """Entries whose publish/discovery time falls inside the last `days` days."""
    if days < 1 or days > 30:
        raise DigestError("--days must be between 1 and 30")
    stamp = subscription_store.parse_iso(now or subscription_store.now_iso())
    cutoff = (stamp - timedelta(days=days)).replace(microsecond=0).isoformat()
    placeholders = ",".join("?" for _ in DIGEST_STATES)
    with store.session() as con:
        rows = con.execute(
            f"""SELECT id, subscription_id, title, author, canonical_url,
                       published_at, updated_at, discovered_at, state, output_path,
                       content_kind, completeness
                FROM entries
                WHERE state IN ({placeholders})
                  AND COALESCE(NULLIF(published_at, ''), discovered_at) >= ?
                ORDER BY COALESCE(NULLIF(published_at, ''), discovered_at) DESC, id DESC""",
            (*DIGEST_STATES, cutoff),
        ).fetchall()
    return [dict(row) for row in rows]


def entry_stamp(entry: dict[str, Any]) -> datetime | None:
    """Publish time, falling back to discovery time; naive values are UTC."""
    raw = entry.get("published_at") or entry.get("discovered_at") or ""
    if not raw:
        return None
    try:
        stamp = subscription_store.parse_iso(raw)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def heat_weight(age_hours: float) -> float:
    """Recency weight for one reporting source."""
    if age_hours <= HEAT_FRESH_HOURS:
        return 1.0
    if age_hours <= HEAT_WINDOW_HOURS:
        return HEAT_AGED_WEIGHT
    return 0.0


def _cluster_heat(entries: list[dict[str, Any]], reference: datetime) -> float:
    """Each distinct source counts once, weighted by its freshest report."""
    weights = []
    for source in {entry["subscription_id"] for entry in entries}:
        freshest = max(
            (
                stamp
                for stamp in (
                    entry_stamp(entry)
                    for entry in entries
                    if entry["subscription_id"] == source
                )
                if stamp is not None
            ),
            default=None,
        )
        if freshest is None:
            weights.append(1.0)
            continue
        age_hours = max((reference - freshest).total_seconds() / 3600.0, 0.0)
        weights.append(heat_weight(age_hours))
    return round(sum(weights), 1)


def cluster_entries(
    entries: list[dict[str, Any]],
    threshold: float = DEFAULT_CLUSTER_THRESHOLD,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Greedy title-similarity clustering.

    `heat` is the recency-weighted distinct source count (see HEAT_* above);
    `source_count` keeps the raw count for display.
    """
    if not 0.1 <= threshold <= 1.0:
        raise DigestError("--cluster-threshold must be between 0.1 and 1.0")
    reference = now or datetime.now(timezone.utc)
    clusters: list[dict[str, Any]] = []
    for entry in entries:
        tokens = title_tokens(entry["title"])
        target = None
        for cluster in clusters:
            if jaccard(tokens, cluster["tokens"]) >= threshold:
                target = cluster
                break
        if target is None:
            target = {"tokens": set(tokens), "entries": []}
            clusters.append(target)
        else:
            target["tokens"] |= tokens
        target["entries"].append(entry)
    for cluster in clusters:
        sources = {entry["subscription_id"] for entry in cluster["entries"]}
        cluster["sources"] = sorted(sources)
        cluster["source_count"] = len(sources)
        cluster["heat"] = _cluster_heat(cluster["entries"], reference)
        cluster["title"] = cluster["entries"][0]["title"]
        cluster["tokens"] = frozenset(cluster["tokens"])
    clusters.sort(
        key=lambda cluster: (
            -cluster["heat"],
            -max(
                (
                    subscription_store.parse_iso(
                        entry["published_at"] or entry["discovered_at"]
                    ).timestamp()
                    for entry in cluster["entries"]
                ),
                default=0,
            ),
        )
    )
    return clusters


def vault_query_candidates(title: str) -> list[str]:
    """Phrase queries for the FTS-backed vault index, longest first.

    The vault FTS matches exact phrases, so fall back by dropping words from
    the tail of the entry title until a short but meaningful prefix remains.
    """
    words = [word for word in re.split(r"\s+", (title or "").strip()) if word]
    candidates = []
    for length in range(len(words), 1, -1):
        candidate = " ".join(words[:length])
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


# The digest cites source material. Its own output, and the briefs built from
# it, are views over that material — linking them back produces "related note:
# last week's digest", which is noise rather than provenance. Both live in the
# vault's generated-output directory and both carry a type marker, so the
# exclusion is by type rather than by path: a vault may point `--output`
# anywhere.
GENERATED_CONTENT_TYPES = ("subscription-digest", "research_brief")


def attach_vault_links(
    clusters: list[dict[str, Any]], index_db: str, *, limit: int = 3
) -> None:
    if not index_db or not Path(index_db).exists():
        return
    for cluster in clusters:
        hits = []
        for query in vault_query_candidates(cluster["title"]):
            try:
                rows = vault_index.search(
                    db_path=index_db,
                    query=query,
                    limit=limit,
                    exclude_content_types=GENERATED_CONTENT_TYPES,
                )
            except Exception:
                rows = []
            if rows:
                hits = [
                    {"title": row.get("title") or row.get("path", ""), "path": row.get("path", "")}
                    for row in rows
                ]
                break
        cluster["vault_hits"] = hits


def load_prompts(prompt_dir: Path | None = None) -> dict[str, str]:
    directory = Path(prompt_dir) if prompt_dir else PROMPT_DIR
    prompts = {}
    for name in PROMPT_FILES:
        path = directory / f"{name}.txt"
        if not path.is_file():
            raise DigestError(f"缺少提示词文件：{path}（可复制 templates/digest-prompts/ 后自定义）")
        prompts[name] = path.read_text(encoding="utf-8").strip()
    return prompts


def call_deepseek(system: str, user: str, api_key: str) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read())
    raw = data["choices"][0]["message"]["content"].strip()
    return llm.parse_json_response(raw)


def _entry_line(index: int, entry: dict[str, Any]) -> str:
    return f"{index}. {entry['title']}（{entry['subscription_id']}）"


def enrich_clusters(
    clusters: list[dict[str, Any]], api_key: str, *, prompts: dict[str, str] | None = None
) -> int:
    """Prescreen -> score -> summarize. Returns the number of enriched clusters."""
    prompts = prompts or load_prompts()
    flat = [entry for cluster in clusters for entry in cluster["entries"]]
    listing = "\n".join(
        _entry_line(index, entry) for index, entry in enumerate(flat, start=1)
    )
    kept_data = call_deepseek(
        prompts["prescreen"], f"候选条目：\n{listing}", api_key
    )
    keep = {llm.safe_int(value, default=-1) for value in kept_data.get("keep", [])}
    keep.discard(-1)
    if not keep:
        return 0
    kept_listing = "\n".join(
        _entry_line(index, entry)
        for index, entry in enumerate(flat, start=1)
        if index in keep
    )
    score_data = call_deepseek(
        prompts["score"], f"待评分条目：\n{kept_listing}", api_key
    )
    scores = {
        llm.safe_int(key, default=-1): llm.safe_int(value, default=0)
        for key, value in (score_data.get("scores") or {}).items()
    }
    enriched = 0
    for cluster in clusters[:MAX_ENRICH_CLUSTERS]:
        indices = [
            flat.index(entry) + 1
            for entry in cluster["entries"]
            if flat.index(entry) + 1 in keep
        ]
        if not indices:
            continue
        cluster["llm_score"] = max(scores.get(index, 0) for index in indices)
        titles = "\n".join(f"- {entry['title']}" for entry in cluster["entries"])
        try:
            summary = call_deepseek(
                prompts["summary"],
                f"事件包含 {len(cluster['entries'])} 条报道：\n{titles}",
                api_key,
            )
        except Exception:
            continue
        headline = str(summary.get("headline") or "").strip()
        text = str(summary.get("summary") or "").strip()
        if headline or text:
            cluster["llm_headline"] = headline
            cluster["llm_summary"] = text
            enriched += 1
    return enriched


def _yaml(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _entry_link(entry: dict[str, Any], vault_root: Path) -> str:
    title = (entry["title"] or "Untitled").replace("[", "\\[").replace("]", "\\]")
    if entry["state"] == "succeeded" and entry.get("output_path"):
        note = Path(entry["output_path"])
        try:
            relative = note.resolve().relative_to(vault_root.resolve())
            target = str(relative)
        except ValueError:
            target = str(note)
        return f"[{title}]({target})（已入库笔记）"
    return f"[{title}]({entry['canonical_url']})"


def heat_label(cluster: dict[str, Any]) -> str:
    """`热度 3.5`, or "" once every report is older than the decay window."""
    heat = cluster["heat"]
    return "" if heat < 1 else f"热度 {heat:g}"


def _heat_suffix(cluster: dict[str, Any]) -> str:
    """` · 热度 3.5（6 条 / 5 源）`.

    Heat below 1 means every report is older than the decay window, so only
    the raw counts are shown rather than a misleading "热度 0".
    """
    counts = f"{len(cluster['entries'])} 条 / {cluster['source_count']} 源"
    label = heat_label(cluster)
    return f" · {counts}" if not label else f" · {label}（{counts}）"


def render_markdown(
    clusters: list[dict[str, Any]],
    *,
    days: int,
    source_count: int,
    entry_count: int,
    enriched: bool,
    threshold: float,
    vault_root: Path,
    names: dict[str, str],
    now: str,
) -> str:
    frontmatter = {
        "type": "subscription-digest",
        "generated_at": now,
        "window_days": days,
        "source_count": source_count,
        "entry_count": entry_count,
        "cluster_count": len(clusters),
        "cluster_threshold": threshold,
        "enriched": enriched,
    }
    lines = ["---"]
    lines += [f"{key}: {_yaml(value)}" for key, value in frontmatter.items()]
    lines += ["---", "", f"# 订阅情报简报（近 {days} 天）", ""]
    if enriched:
        lines += [
            "> 🤖 标注「🤖」的标题/摘要/评分由 DeepSeek 生成，可能有误；每条均保留原始链接供回查。",
            "",
        ]
    for rank, cluster in enumerate(clusters, start=1):
        entries = cluster["entries"]
        headline = cluster.get("llm_headline") or entries[0]["title"]
        marker = "🤖 " if cluster.get("llm_headline") else ""
        heat = _heat_suffix(cluster)
        score = (
            f" · 🤖 评分 {cluster['llm_score']}/10" if "llm_score" in cluster else ""
        )
        lines.append(f"## {rank}. {marker}{headline}{heat}{score}")
        lines.append("")
        if cluster.get("llm_summary"):
            lines += [f"🤖 {cluster['llm_summary']}", ""]
        for entry in entries:
            source = names.get(entry["subscription_id"], entry["subscription_id"])
            stamp = entry["published_at"] or entry["discovered_at"] or ""
            lines.append(
                f"- {_entry_link(entry, vault_root)} — {source} · {stamp[:10]} · {entry['state']}"
            )
        hits = cluster.get("vault_hits") or []
        if hits:
            lines.append(f"- 📚 知识库已有 {len(hits)} 篇相关笔记：")
            for hit in hits:
                lines.append(f"  - [{hit['title']}]({hit['path']})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def digest_output_path(vault_root: Path, now: str) -> Path:
    stamp = subscription_store.parse_iso(now)
    output_dir = vault_root / "30_Output"
    base = output_dir / f"subscription-digest-{stamp:%Y-%m-%d}.md"
    if not base.exists():
        return base
    # Never overwrite an existing digest (same safety rule as other outputs).
    candidate = output_dir / f"subscription-digest-{stamp:%Y-%m-%d-%H%M%S}.md"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"subscription-digest-{stamp:%Y-%m-%d-%H%M%S}-{suffix}.md"
        suffix += 1
    return candidate


def run_digest(args: Any, config: dict[str, Any], document: dict[str, Any], store) -> int:
    chubby_root = config.get("vault_root")
    if not chubby_root:
        raise DigestError("需要已配置知识库：先运行 chubby init --vault <知识库根目录>")
    vault_root = Path(chubby_root).expanduser().resolve()
    days = int(getattr(args, "days", 1) or 1)
    threshold = float(getattr(args, "cluster_threshold", DEFAULT_CLUSTER_THRESHOLD))
    now = subscription_store.now_iso()

    entries = collect_window_entries(store, days, now=now)
    if not entries:
        print(f"ℹ️  近 {days} 天窗口内没有订阅条目；先运行 subscribe sync 积累数据。")
        return 0

    clusters = cluster_entries(entries, threshold=threshold, now=subscription_store.parse_iso(now))
    names = {item["id"]: item["name"] for item in document["subscriptions"]}
    source_count = len({entry["subscription_id"] for entry in entries})

    if not getattr(args, "no_vault_links", False):
        attach_vault_links(clusters, str(config.get("index_db") or ""))

    enriched = False
    if getattr(args, "enrich", False):
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise DigestError(
                "--enrich 需要 DEEPSEEK_API_KEY 环境变量；去掉 --enrich 可使用零 LLM 简报"
            )
        enriched_count = enrich_clusters(clusters, api_key)
        enriched = enriched_count > 0
        print(f"🤖 enrich 完成：{enriched_count} 个事件获得模型摘要")

    markdown = render_markdown(
        clusters,
        days=days,
        source_count=source_count,
        entry_count=len(entries),
        enriched=enriched,
        threshold=threshold,
        vault_root=vault_root,
        names=names,
        now=now,
    )
    output_arg = getattr(args, "output", "") or ""
    if output_arg:
        target = Path(output_arg).expanduser()
        if target.exists():
            raise DigestError(f"输出文件已存在，不会覆盖：{target}")
    else:
        target = digest_output_path(vault_root, now)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    print(f"✅ 简报已生成：{target}")
    print(f"   窗口 {days} 天 · {len(entries)} 条 · {len(clusters)} 个事件 · {source_count} 个来源")
    return 0
