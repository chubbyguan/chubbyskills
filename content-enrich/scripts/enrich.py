#!/usr/bin/env python3
"""
内容加工（enrich）—— 让任意采集产物自动带上「摘要 + 要点 + 标签 + 价值判断」

把仓库里任何采集 skill 产出的 Markdown（转录稿、文章、笔记…）盘活：用 DeepSeek
提炼出一句话总结、3-5 条要点、领域、标签、值不值得深读，写进 frontmatter 并在
正文顶部插入「## 📝 摘要」区块。原内容完整保留。

用法：
    export DEEPSEEK_API_KEY=***
    python enrich.py 某篇笔记.md                 # 就地增强
    python enrich.py ./vault/外部输入/           # 批量增强目录下所有 .md
    python enrich.py 某篇.md --output ./out       # 不改原文件，写到 out/
    python enrich.py 某篇.md --force              # 已加工过的也重新加工

零 pip 依赖（仅标准库）；幂等：默认跳过已加工（frontmatter 有 enriched: true）的文件。
"""

import sys
import os
import re
import json
import argparse
import urllib.request


SYSTEM_PROMPT = """你是知识管理助手。把一篇采集来的内容提炼成可快速消化的元信息。
只输出一个 JSON 对象，不要 markdown 代码块、不要多余解释：
{
  "tldr": "一句话总结，≤40字",
  "points": ["要点，3-5条，每条≤30字"],
  "domain": "领域，如 AI / 商业 / 科技 / 内容创作",
  "tags": ["3-6个标签，不带#"],
  "worth": "一句话：值不值得深读、对谁有用"
}
用中文。"""

ENRICH_KEYS = ("summary", "domain", "auto_tags", "enriched")


def split_frontmatter(text):
    """返回 (frontmatter文本 或 None, 正文)。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end].strip("\n"), text[end + 4:].lstrip("\n")
    return None, text


def already_enriched(text):
    fm, _ = split_frontmatter(text)
    if fm and re.search(r"^enriched:\s*true", fm, re.MULTILINE):
        return True
    return "## 📝 摘要" in text


def inject_frontmatter(fm, extra):
    """在原 frontmatter 上更新/追加加工字段，不动其它原有字段。"""
    kept = []
    for line in (fm or "").split("\n"):
        key = line.split(":", 1)[0].strip()
        if line.strip() and key not in extra:
            kept.append(line)
    for k, v in extra.items():
        kept.append(f"{k}: {v}")
    return "\n".join(kept)


def build_summary_block(data):
    lines = ["## 📝 摘要", ""]
    if data.get("tldr"):
        lines += [f"> {data['tldr']}", ""]
    if data.get("points"):
        lines.append("**要点**")
        lines += [f"- {p}" for p in data["points"]]
        lines.append("")
    if data.get("worth"):
        lines += [f"**值得深读？** {data['worth']}", ""]
    if data.get("tags"):
        lines += ["**标签**：" + " ".join(f"#{t}" for t in data["tags"]), ""]
    return "\n".join(lines)


def insert_block(body, block):
    """摘要块插在第一个 # 标题之后；没有标题就插在最前。"""
    lines = body.split("\n")
    for i, l in enumerate(lines):
        if l.startswith("# "):
            return "\n".join(lines[:i + 1]) + "\n\n" + block + "\n" + "\n".join(lines[i + 1:])
    return block + "\n" + body


def enrich_text(text, data):
    fm, body = split_frontmatter(text)
    # 注入 YAML 前做转义：tldr/domain 可能含冒号、引号、换行，裸写会破坏 frontmatter
    def _yk(s):
        return '"' + str(s).replace("\\", "\\\\").replace("\n", " ").replace('"', '\\"').strip() + '"'
    safe_tags = [str(t).replace(",", " ").replace("\n", " ").strip() for t in data.get("tags", [])]
    extra = {
        "summary": _yk(data.get("tldr", "")),
        "domain": _yk(data.get("domain", "")),
        "auto_tags": "[" + ", ".join(safe_tags) + "]",
        "enriched": "true",
    }
    block = build_summary_block(data)
    new_body = insert_block(body, block)
    if fm is None:
        new_fm = inject_frontmatter("", extra)
        return f"---\n{new_fm}\n---\n\n{new_body}"
    return f"---\n{inject_frontmatter(fm, extra)}\n---\n\n{new_body}"


def call_deepseek(content, api_key):
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"提炼这篇内容：\n\n{content}"},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    raw = data["choices"][0]["message"]["content"].strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)


def enrich_file(path, api_key, out_dir, force):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if already_enriched(text) and not force:
        print(f"  ⏭️  跳过（已加工）：{os.path.basename(path)}", file=sys.stderr)
        return False
    _, body = split_frontmatter(text)
    if len(body.strip()) < 20:
        print(f"  ⏭️  跳过（内容过短）：{os.path.basename(path)}", file=sys.stderr)
        return False
    data = call_deepseek(body[:12000], api_key)
    new_text = enrich_text(text, data)
    target = os.path.join(out_dir, os.path.basename(path)) if out_dir else path
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"  ✅ {os.path.basename(path)} — {len(data.get('points', []))} 要点 / "
          f"{len(data.get('tags', []))} 标签", file=sys.stderr)
    return True


def main():
    parser = argparse.ArgumentParser(description="内容加工：补摘要/要点/标签")
    parser.add_argument("path", help="单个 .md 文件，或一个目录（批量）")
    parser.add_argument("--output", "-o", help="输出目录（默认就地增强）")
    parser.add_argument("--force", action="store_true", help="已加工过的也重新加工")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 缺少 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    if os.path.isdir(args.path):
        files = []
        for root, dirs, names in os.walk(args.path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files += [os.path.join(root, n) for n in names if n.endswith(".md")]
    elif os.path.isfile(args.path):
        files = [args.path]
    else:
        print(f"❌ 路径不存在：{args.path}", file=sys.stderr)
        sys.exit(1)

    print(f"🧠 待加工 {len(files)} 篇...", file=sys.stderr)
    done = 0
    for p in sorted(files):
        try:
            if enrich_file(p, api_key, args.output, args.force):
                done += 1
        except Exception as e:
            print(f"  ⚠️  失败 {os.path.basename(p)}：{e}", file=sys.stderr)
    print(f"✅ 完成：加工 {done} 篇", file=sys.stderr)


if __name__ == "__main__":
    main()
