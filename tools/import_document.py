#!/usr/bin/env python3
"""Import local documents and their explicitly referenced assets without a network request."""

import argparse
import hashlib
import importlib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chubby_common.markdown import note_markdown, sanitize_filename

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}


def _web_source(value):
    if not isinstance(value, str) or any(ord(char) < 33 or ord(char) == 127 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            return None
        _ = parsed.port  # Reject invalid ports as well as malformed hosts.
    except ValueError:
        return None
    return value


def _scalar(value):
    """Read only simple title/source scalars; never evaluate arbitrary YAML tags."""
    value = value.strip()
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, str) else None
        except ValueError:
            return None
    if value.startswith("'"):
        return value[1:-1].replace("''", "'") if value.endswith("'") else None
    if not value or value[0] in "[{'&*!>|":
        return None
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def _frontmatter(text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index, line in enumerate(lines[1:], 1):
        if line.strip() in {"---", "..."}:
            fields = {}
            for entry in lines[1:index]:
                match = re.match(r"^(title|source):\s*(.*)$", entry)
                if match:
                    fields[match[1]] = _scalar(match[2])
            return fields, "".join(lines[index + 1:])
    raise ValueError("Markdown frontmatter 缺少结束分隔符 ---。")


def _title(value, fallback):
    value = re.sub(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip() or fallback


def _mask_code(body):
    """Keep offsets stable while excluding fenced/indented/inline code examples."""
    def blank(match):
        return re.sub(r"[^\r\n]", " ", match.group())

    fence, lines = None, []
    for line in body.splitlines(keepends=True):
        marker = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        was_fenced = fence is not None
        if fence is None and marker:
            fence = marker[1]
        elif marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
            fence = None
        lines.append(re.sub(r"[^\r\n]", " ", line) if was_fenced or fence is not None else line)
    # A four-space image inside a list is visible content, not an indented code block.
    masked_lines, list_context = [], False
    for line in lines:
        if re.match(r"^[ \t]{0,3}(?:[-+*]|[0-9]+[.)])[ \t]+", line):
            list_context = True
        elif line.strip() and not re.match(r"^(?: {4}|\t)", line):
            list_context = False
        if not list_context and re.match(r"^(?: {4}|\t)", line):
            line = re.sub(r"[^\r\n]", " ", line)
        masked_lines.append(line)
    masked = "".join(masked_lines)
    masked = re.sub(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", blank, masked, flags=re.DOTALL)
    masked = re.sub(r"<!--.*?-->", blank, masked, flags=re.DOTALL)
    return masked


def _escaped(text, position):
    count = 0
    while position > 0 and text[position - 1] == "\\":
        count += 1
        position -= 1
    return count % 2 == 1


def _references(body):
    """Return destination spans for inline links, definitions, embeds and HTML."""
    masked = _mask_code(body)
    spans = []
    for match in re.finditer(r"!?\[[^\]\n]*\]\(", masked):
        opening = match.start() + (1 if match.group().startswith("!") else 0)
        if _escaped(masked, opening):
            continue
        start = match.end()
        while start < len(masked) and masked[start].isspace():
            start += 1
        if masked[start:start + 1] == "<":
            closing = masked.find(">", start + 1)
            if closing != -1 and "\n" not in masked[start:closing]:
                spans.append((start + 1, closing))
            continue
        cursor, depth = start, 1
        while cursor < len(masked) and depth:
            char = masked[cursor]
            if char == "\\":
                cursor += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            cursor += 1
        if depth:
            continue
        end = cursor - 1
        while start < end and masked[start].isspace():
            start += 1
        while end > start and masked[end - 1].isspace():
            end -= 1
        title = re.search(r"\s+(?:\"[^\"]*\"|'[^']*')$", masked[start:end])
        spans.append((start, start + title.start() if title else end))
    for match in re.finditer(r"(?m)^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*(?:<([^>\n]+)>|([^\s]+))", masked):
        spans.append(match.span(1 if match[1] is not None else 2))
    for tag in re.finditer(r"<(?:img|a|audio|video|source)\b[^>]*>", masked, flags=re.IGNORECASE):
        if _escaped(masked, tag.start()):
            continue
        for attr in re.finditer(r"\b(?:src|href|poster)\s*=\s*(?:([\"'])(.*?)\1|([^\s>]+))", tag.group(), flags=re.IGNORECASE):
            begin, end = attr.span(2 if attr[2] is not None else 3)
            spans.append((tag.start() + begin, tag.start() + end))
    for match in re.finditer(r"!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", masked):
        if _escaped(masked, match.start()) or _escaped(masked, match.start() + 1):
            continue
        spans.append(match.span(1))
    return sorted(set(spans))


def _asset_target(reference, source_dir):
    reference = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", reference)
    if not reference or reference.startswith("#"):
        return None
    try:
        parsed = urlsplit(reference)
    except ValueError as exc:
        raise ValueError(f"附件链接无效：{reference}") from exc
    if parsed.scheme or parsed.netloc:
        if parsed.scheme == "file":
            raise ValueError(f"附件必须使用来源目录内的相对路径：{reference}")
        return None
    relative = unquote(parsed.path, errors="strict")
    if not relative:
        return None
    if (relative.startswith(("/", "\\")) or "\\" in relative
            or any(ord(char) < 32 or ord(char) == 127 for char in relative)):
        raise ValueError(f"附件必须使用来源目录内的相对路径：{reference}")
    path = Path(relative)
    if ".." in path.parts:
        raise ValueError(f"附件路径不能逃逸来源目录：{reference}")
    current = source_dir
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"附件不能通过符号链接引用：{reference}")
    resolved = current.resolve()
    if not resolved.is_relative_to(source_dir) or not resolved.is_file():
        raise ValueError(f"本地附件不存在或不在来源目录内：{reference}")
    suffix = ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
    return path.as_posix(), resolved, suffix


def _snapshot(source):
    source = Path(source).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("仅支持本地 .md、.markdown、.txt、.pdf 文件。")
    raw = source.read_bytes()
    if not raw:
        raise ValueError("无法导入空文件。")
    fields, assets, references = {}, {}, []
    if source.suffix.lower() == ".pdf":
        body = None
    else:
        try:
            body = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("文本必须为有效 UTF-8；请先明确转换原文件编码。") from exc
        if source.suffix.lower() in {".md", ".markdown"}:
            fields, body = _frontmatter(body)
            for start, end in _references(body):
                target = _asset_target(body[start:end], source.parent)
                if target is not None:
                    relative, path, suffix = target
                    if relative not in assets:
                        assets[relative] = path.read_bytes()
                    references.append((start, end, relative, suffix))
        if not body.strip():
            raise ValueError("文件正文为空，未生成笔记。")
    manifest = [{"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
                for relative, data in sorted(assets.items())]
    digest = hashlib.sha256(raw).hexdigest()
    fingerprint = hashlib.sha256(json.dumps({"source_sha256": digest, "assets": manifest},
                                            ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return source, raw, body, fields, assets, references, manifest, digest, fingerprint


def document_fingerprint(source):
    """Hash source bytes plus only referenced local asset paths/bytes; invalid references fail."""
    return _snapshot(source)[-1]


def _pdf_text(raw):
    try:
        module = importlib.import_module("pymupdf")
    except ImportError as exc:
        raise ValueError("PDF 文字提取需要可选依赖：python -m pip install 'pymupdf>=1.24'。") from exc
    try:
        with module.open(stream=raw, filetype="pdf") as document:
            if document.needs_pass:
                raise ValueError("PDF 已加密，请先提供可读取的解密副本。")
            pages = [page.get_text("text").strip() for page in document]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"PDF 无法读取：{exc}") from exc
    if not any(pages):
        raise ValueError("PDF 没有可提取的文字层，可能是扫描件；本导入器不执行 OCR。")
    return "\n\n".join(f"## 第 {number} 页\n\n{text}" for number, text in enumerate(pages, 1) if text) + "\n"


def import_document(source, output_dir, source_url=None):
    """Create a new normalized note with copied local assets; never modify the source."""
    if source_url is not None and _web_source(source_url) is None:
        raise ValueError("--source-url 必须是无用户名、密码或空白字符的有效 HTTP(S) 网页地址。")
    source, raw, body, fields, assets, references, manifest, digest, fingerprint = _snapshot(source)
    if body is None:
        body = _pdf_text(raw)
        method = "pdf_text"
    else:
        method = "markdown" if source.suffix.lower() in {".md", ".markdown"} else "text"
    heading = re.search(r"(?m)^ {0,3}# +(.+?)[ \t]*#*[ \t]*$", body) if method == "markdown" else None
    title = _title(fields.get("title") or (heading[1] if heading else None), source.stem)
    metadata = {
        "type": "note", "platform": "content",
        "source": source_url or _web_source(fields.get("source")) or source.as_uri(),
        "import_method": method, "original_path": str(source),
        "source_sha256": digest, "source_fingerprint": fingerprint, "source_assets": manifest,
    }
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base = sanitize_filename(title)
    for version in range(1, 10001):
        stem = base if version == 1 else f"{base}--v{version}"
        destination = output_dir / f"{stem}.md"
        asset_dir = output_dir / f"{stem}.assets"
        if destination.exists() or destination.is_symlink() or asset_dir.exists() or asset_dir.is_symlink():
            continue
        try:
            handle = destination.open("xb")
        except FileExistsError:
            continue
        owned_assets = False
        try:
            if assets:
                asset_dir.mkdir()
                owned_assets = True
                for relative, data in assets.items():
                    target = asset_dir / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            rewritten = body
            for start, end, relative, suffix in reversed(references):
                link = quote(f"{stem}.assets/{relative}", safe="/-._~") + suffix
                rewritten = rewritten[:start] + link + rewritten[end:]
            markdown = note_markdown(title, rewritten, metadata)
            # Preserve an existing Markdown heading/body instead of adding another H1.
            if method == "markdown":
                prefix = markdown.split("\n---\n", 1)[0] + "\n---\n"
                markdown = prefix + rewritten
            with handle:
                handle.write(markdown.encode("utf-8"))
            return destination
        except BaseException:
            handle.close()
            destination.unlink(missing_ok=True)
            if owned_assets:
                shutil.rmtree(asset_dir)
            raise
    raise ValueError("同名导入版本过多，请选择另一个输出目录。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="本地 Markdown、UTF-8 文本或含文字层的 PDF")
    parser.add_argument("--output", required=True, help="导入产物目录；同名文件自动另存新版本")
    parser.add_argument("--source-url", help="原始 HTTP(S) 网页地址，仅记来源，不联网")
    args = parser.parse_args(argv)
    try:
        output = import_document(args.source, args.output, args.source_url)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"导入失败：{exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
