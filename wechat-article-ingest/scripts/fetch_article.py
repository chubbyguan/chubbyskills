#!/usr/bin/env python3
"""
微信公众号文章 → Markdown 提取工具

用法：
    python fetch_article.py "https://mp.weixin.qq.com/s/xxxxx"
    python fetch_article.py "https://mp.weixin.qq.com/s/xxxxx" --output ./output
    python fetch_article.py "path/to/article.pdf"  # PDF fallback
"""

import sys
import os
import re
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


def fetch_from_url(url: str) -> tuple:
    """Fetch article from WeChat URL. Returns (title, author, content)."""
    print(f"  🌐 Fetching: {url[:60]}...", file=sys.stderr)
    
    result = subprocess.run(
        ["curl", "-sL", "--max-time", "30",
         "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
         url],
        capture_output=True, text=True, timeout=35
    )
    
    if result.returncode != 0:
        print(f"  ❌ Fetch failed", file=sys.stderr)
        return None, None, None
    
    html = result.stdout
    
    # Check if blocked
    if '环境异常' in html or '请在微信客户端' in html:
        print(f"  ❌ Blocked by WeChat", file=sys.stderr)
        return None, None, None
    
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
    except ImportError:
        print(f"  ❌ Need beautifulsoup4: pip install beautifulsoup4", file=sys.stderr)
        return None, None, None
    
    # Extract title
    title_tag = soup.find('h1', class_='rich_media_title')
    title = title_tag.get_text().strip() if title_tag else ""
    
    # Extract author/account
    author_tag = soup.find('span', class_='rich_media_meta_nickname')
    author = author_tag.get_text().strip() if author_tag else ""
    
    # Extract content
    content_tag = soup.find('div', class_='rich_media_content')
    if not content_tag:
        print(f"  ❌ No content found", file=sys.stderr)
        return None, None, None
    
    content = content_tag.get_text()
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()
    
    if len(content) < 100:
        print(f"  ❌ Content too short ({len(content)} chars)", file=sys.stderr)
        return None, None, None
    
    print(f"  ✅ Fetched: {title[:50]}... ({len(content)} chars)", file=sys.stderr)
    return title, author, content


def extract_from_pdf(pdf_path: str) -> tuple:
    """Extract from PDF. Returns (title, author, content)."""
    print(f"  📄 Extracting PDF: {os.path.basename(pdf_path)}", file=sys.stderr)
    
    # Try MarkItDown first
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(pdf_path)
        content = result.text_content
    except Exception as e:
        print(f"  ⚠️ MarkItDown failed: {e}", file=sys.stderr)
        content = None
    
    # Fallback to pymupdf
    if not content or len(content.strip()) < 300:
        try:
            import pymupdf
            doc = pymupdf.open(pdf_path)
            content = ""
            for page in doc:
                content += page.get_text()
        except Exception as e:
            print(f"  ⚠️ pymupdf failed: {e}", file=sys.stderr)
            return None, None, None
    
    if not content or len(content.strip()) < 300:
        print(f"  ❌ Content too short", file=sys.stderr)
        return None, None, None
    
    # Extract title from first lines
    lines = content.split('\n')[:10]
    title = ""
    for line in lines:
        line = line.strip()
        if len(line) > 5 and len(line) < 100:
            title = line
            break
    
    # Try to extract author
    author_match = re.search(r'(作者|作者：|文[：:])\s*(.+)', content[:500])
    author = author_match.group(2).strip() if author_match else ""
    
    if not title:
        title = Path(pdf_path).stem
    
    content = re.sub(r'\n{3,}', '\n\n', content).strip()
    
    print(f"  ✅ Extracted: {title[:50]}... ({len(content)} chars)", file=sys.stderr)
    return title, author, content


def generate_markdown(title: str, author: str, content: str, source: str) -> str:
    """Generate Markdown with frontmatter."""
    now = datetime.now().strftime("%Y-%m-%d")
    
    return f"""---
title: {title}
type: note
tags: [公众号]
created: {now}
author: {author}
source: {source}
---

# {title}

{content}"""


def sanitize_filename(name: str) -> str:
    """Clean filename."""
    s = re.sub(r'[<>:"/\\|?*]', '', name)
    s = re.sub(r'\s+', '-', s)
    return s[:50]


def main():
    parser = argparse.ArgumentParser(description='微信公众号文章 → Markdown')
    parser.add_argument('input', help='公众号链接或 PDF 文件路径')
    parser.add_argument('--output', '-o', default='.', help='输出目录')
    args = parser.parse_args()
    
    source = args.input
    
    # Determine input type
    if source.startswith('http'):
        title, author, content = fetch_from_url(source)
    elif os.path.exists(source):
        title, author, content = extract_from_pdf(source)
    else:
        print(f"❌ Invalid input: {source}", file=sys.stderr)
        sys.exit(1)
    
    if not content:
        print(f"❌ Failed to extract content", file=sys.stderr)
        sys.exit(1)
    
    # Generate markdown
    markdown = generate_markdown(title, author, content, source)
    
    # Save
    safe_title = sanitize_filename(title)
    output_filename = f"{safe_title}.md"
    output_path = os.path.join(args.output, output_filename)
    
    os.makedirs(args.output, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print(f"\n✅ Saved: {output_path}", file=sys.stderr)
    print(output_path)


if __name__ == '__main__':
    main()
