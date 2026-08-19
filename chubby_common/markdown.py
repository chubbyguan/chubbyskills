"""统一 Markdown 生成：frontmatter 协议与文件名清洗。

各采集 skill 输出契约保持一致（title/type/platform/source/created/author/tags…），
下游 vault_index / validate_outputs 才能正常工作。
"""

import re
from datetime import datetime


def sanitize_filename(name: str, fallback: str = "note") -> str:
    """清洗为安全文件名；空值或全非法字符时回退到 fallback。"""
    value = re.sub(r'[<>:"/\\|?*]', "", str(name or ""))
    value = re.sub(r"\s+", "-", value).strip(" -")
    return value[:50] or fallback


def note_markdown(title: str, body: str, fields: dict, created: str = None) -> str:
    """按统一协议生成带 frontmatter 的 Markdown。

    fields 为 frontmatter 字段（不含 title），如：
        {"type": "note", "platform": "tiktok", "tags": "[TikTok]",
         "source": url, "author": "", "transcriber": "SenseVoice-Small"}
    """
    created = created or datetime.now().strftime("%Y-%m-%d")
    lines = ["---", f"title: {title}", f"created: {created}"]
    for key, value in fields.items():
        lines.append(f"{key}: {value}")
    lines += ["---", "", f"# {title}", "", str(body or "")]
    return "\n".join(lines)
