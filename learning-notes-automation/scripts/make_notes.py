#!/usr/bin/env python3
"""
学习笔记自动化 - 从转录稿/文章生成知识点 + Anki 闪卡

输入一份转录文本或 Markdown（来自本仓库的任意 *-transcribe / wechat-article-ingest
skill），用 DeepSeek 提取知识点、生成 Anki 兼容闪卡，并输出学习笔记 Markdown。

用法：
    python make_notes.py 转录稿.md
    python make_notes.py 转录稿.md --output ./notes --max-cards 20

环境变量：
    DEEPSEEK_API_KEY   必填，DeepSeek API Key

输出（写入 --output 目录，默认当前目录）：
    <名字>-学习笔记.md      学习笔记（核心要点 + 闪卡 + 关联知识）
    <名字>-闪卡.csv         Anki 导入文件（问题,答案,标签）
"""

import sys
import os
import re
import json
import argparse
import urllib.request
from datetime import datetime


SYSTEM_PROMPT = """你是学习教练，擅长把内容提炼成可记忆的知识卡片。
只输出一个 JSON 对象，不要 markdown 代码块，不要额外解释。结构如下：
{
  "title": "内容标题（一句话）",
  "domain": "领域，如 AI / 半导体 / 商业",
  "notes": [
    {"point": "要点标题", "summary": "1-2句摘要", "importance": 1-5}
  ],
  "cards": [
    {"type": "concept|qa|compare|process", "q": "问题", "a": "答案", "tags": ["标签"]}
  ],
  "relations": [
    {"from": "概念A", "rel": "依赖于|属于|替代了|发明了", "to": "概念B"}
  ]
}
要求：
- 闪卡原子化，一张卡一个知识点，脱离上下文也能理解
- 优先「为什么/怎么做」类卡片，而非单纯「是什么」
- notes 5-15 条，cards 不超过用户指定上限
- 用中文"""


def call_deepseek(content: str, max_cards: int, api_key: str) -> dict:
    user = (f"从以下内容提取知识点并生成不超过 {max_cards} 张闪卡。"
            f"内容：\n\n{content}")
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())

    if "choices" not in result:
        raise RuntimeError(f"DeepSeek 返回异常：{json.dumps(result, ensure_ascii=False)[:300]}")
    raw = result["choices"][0]["message"]["content"]
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    """容错解析：去掉可能的代码块包裹。"""
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)


def strip_frontmatter(text: str) -> str:
    """去掉转录稿的 YAML frontmatter，只留正文。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip()
    return text


CARD_TYPE_CN = {"concept": "概念卡", "qa": "问答卡",
                "compare": "对比卡", "process": "步骤卡"}


def build_notes_md(data: dict, source_name: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    title = data.get("title", source_name)
    domain = data.get("domain", "")
    notes = data.get("notes", [])
    cards = data.get("cards", [])
    relations = data.get("relations", [])

    lines = [
        "---",
        f"title: {title} - 学习笔记",
        "type: knowledge-card",
        "platform: learning",
        f"tags: [学习{', ' + domain if domain else ''}]",
        f"source: {source_name}",
        f"created: {now}",
        "---",
        "",
        f"# {title} - 学习笔记",
        "",
        f"**领域**：{domain or '通用'} | **日期**：{now} | "
        f"**要点**：{len(notes)} | **闪卡**：{len(cards)} 张",
        "",
        "## 📝 核心要点",
        "",
    ]
    for i, n in enumerate(notes, 1):
        stars = "⭐" * int(n.get("importance", 3))
        lines.append(f"### {i}. {n.get('point', '')}")
        lines.append(f"- 摘要：{n.get('summary', '')}")
        lines.append(f"- 重要性：{stars}")
        lines.append("")

    lines += ["## 🃏 闪卡", ""]
    for i, c in enumerate(cards, 1):
        ctype = CARD_TYPE_CN.get(c.get("type", "qa"), "问答卡")
        lines.append(f"{i}. **[{ctype}]** Q: {c.get('q', '')}")
        lines.append(f"   A: {c.get('a', '')}")
    lines.append("")

    if relations:
        lines += ["## 🔗 关联知识", ""]
        for r in relations:
            lines.append(f"- [[{r.get('from', '')}]] —{r.get('rel', '')}→ "
                         f"[[{r.get('to', '')}]]")
        lines.append("")

    lines += ["## 💡 个人思考", "", "（待补充：这些知识能用在哪？与已知的什么冲突或印证？）", ""]
    return "\n".join(lines)


def build_cards_csv(data: dict) -> str:
    """Anki 兼容 CSV：问题,答案,标签。"""
    rows = ['"问题","答案","标签"']
    for c in data.get("cards", []):
        q = str(c.get("q", "")).replace('"', '""')
        a = str(c.get("a", "")).replace('"', '""')
        tags = " ".join(c.get("tags", [])).replace('"', '""')
        rows.append(f'"{q}","{a}","{tags}"')
    return "\n".join(rows) + "\n"


def sanitize(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "", name)
    s = re.sub(r"\s+", "-", s)
    return s[:50] or "notes"


def main():
    parser = argparse.ArgumentParser(description="学习笔记自动化")
    parser.add_argument("input", help="转录稿/文章文件（.md 或 .txt）")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    parser.add_argument("--max-cards", type=int, default=25, help="闪卡上限，默认 25")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 缺少 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        content = strip_frontmatter(f.read())
    if not content.strip():
        print("❌ 输入文件为空", file=sys.stderr)
        sys.exit(1)

    # DeepSeek 上下文够长，但过长时截断以保证响应稳定
    if len(content) > 12000:
        print(f"  ⚠️  内容较长（{len(content)} 字），截断至 12000 字", file=sys.stderr)
        content = content[:12000]

    print("🧠 调用 DeepSeek 提取知识点...", file=sys.stderr)
    data = call_deepseek(content, args.max_cards, api_key)

    source_name = os.path.basename(args.input)
    base = sanitize(data.get("title") or os.path.splitext(source_name)[0])
    os.makedirs(args.output, exist_ok=True)

    notes_path = os.path.join(args.output, f"{base}-学习笔记.md")
    cards_path = os.path.join(args.output, f"{base}-闪卡.csv")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(build_notes_md(data, source_name))
    with open(cards_path, "w", encoding="utf-8") as f:
        f.write(build_cards_csv(data))

    print("✅ Done!", file=sys.stderr)
    print(f"  要点：{len(data.get('notes', []))} | 闪卡：{len(data.get('cards', []))}",
          file=sys.stderr)
    print(f"  笔记：{notes_path}", file=sys.stderr)
    print(f"  闪卡：{cards_path}", file=sys.stderr)
    print(notes_path)


if __name__ == "__main__":
    main()
