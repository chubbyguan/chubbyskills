#!/usr/bin/env python3
"""
小红书爆款拆解 → 选题模板

输入一篇笔记（fetch_note.py 的产物，或任意手动粘贴的文本），用 DeepSeek 按
「人群 × 场景 × 痛点 × 情绪 × 钩子 × 结构」拆解爆款逻辑，并衍生可复用的选题。

用法：
    export DEEPSEEK_API_KEY=***
    python analyze_hook.py 笔记.md
    python analyze_hook.py 笔记.md --output ./out

产出：<标题>-爆款拆解.md（拆解报告 + 5 条衍生选题），可直接进选题库。
"""

import sys
import os
import re
import json
import argparse
import urllib.request
from datetime import datetime


SYSTEM_PROMPT = """你是资深小红书运营，擅长拆解爆款笔记的底层逻辑。
只输出一个 JSON 对象，不要 markdown 代码块、不要多余解释。结构：
{
  "audience": "目标人群（谁会看）",
  "scene": "使用场景（什么时候/在哪用得上）",
  "pain_point": "核心痛点或需求",
  "emotion": "提供的情绪价值",
  "title_hook": {"type": "标题钩子类型", "why": "为什么能吸引点击"},
  "structure": ["开头怎么写", "中间怎么展开", "结尾怎么收/引导互动"],
  "reusable_template": "一句话概括可复用的标题+结构模板",
  "derived_topics": ["衍生选题1", "选题2", "选题3", "选题4", "选题5"]
}
要求：分析具体、可操作；衍生选题要和原笔记同人群但换角度，能直接拿去写。用中文。"""


def call_deepseek(content, api_key):
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"拆解这篇小红书笔记：\n\n{content}"},
        ],
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    raw = data["choices"][0]["message"]["content"].strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip()
    return text


def build_report(d, source_name):
    now = datetime.now().strftime("%Y-%m-%d")
    hook = d.get("title_hook", {})
    structure = d.get("structure", [])
    topics = d.get("derived_topics", [])
    lines = [
        "---",
        f"title: 爆款拆解 - {source_name}",
        "type: note",
        "platform: xiaohongshu",
        "tags: [小红书, 爆款拆解, 选题]",
        f"created: {now}",
        f"source: {source_name}",
        "---",
        "",
        f"# 爆款拆解 - {source_name}",
        "",
        "## 🎯 爆款要素",
        "",
        f"- **目标人群**：{d.get('audience', '')}",
        f"- **使用场景**：{d.get('scene', '')}",
        f"- **核心痛点**：{d.get('pain_point', '')}",
        f"- **情绪价值**：{d.get('emotion', '')}",
        "",
        "## 🪝 标题钩子",
        "",
        f"- **类型**：{hook.get('type', '')}",
        f"- **为什么吸引**：{hook.get('why', '')}",
        "",
        "## 🧱 正文结构",
        "",
    ]
    for i, s in enumerate(structure, 1):
        lines.append(f"{i}. {s}")
    lines += [
        "",
        "## ♻️ 可复用模板",
        "",
        d.get("reusable_template", ""),
        "",
        "## 💡 衍生选题（可直接进选题库）",
        "",
    ]
    for t in topics:
        lines.append(f"- [ ] {t}")
    lines.append("")
    return "\n".join(lines)


def sanitize(name):
    s = re.sub(r'[<>:"/\\|?*\n]', "", name)
    s = re.sub(r"\s+", "-", s)
    return s[:50] or "xhs-note"


def main():
    parser = argparse.ArgumentParser(description="小红书爆款拆解")
    parser.add_argument("input", help="笔记 md/txt 文件")
    parser.add_argument("--output", "-o", default=".", help="输出目录")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 缺少 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        content = strip_frontmatter(f.read())
    if len(content.strip()) < 20:
        print("❌ 内容过短，无法拆解", file=sys.stderr)
        sys.exit(1)
    if len(content) > 8000:
        content = content[:8000]

    print("🧠 DeepSeek 拆解中...", file=sys.stderr)
    try:
        data = call_deepseek(content, api_key)
    except Exception as e:
        print(f"❌ 拆解失败：{e}", file=sys.stderr)
        sys.exit(1)

    base = sanitize(os.path.splitext(os.path.basename(args.input))[0])
    os.makedirs(args.output, exist_ok=True)
    output_path = os.path.join(args.output, f"{base}-爆款拆解.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(build_report(data, os.path.basename(args.input)))

    print(f"✅ Saved: {output_path}", file=sys.stderr)
    print(f"  衍生选题：{len(data.get('derived_topics', []))} 条", file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
