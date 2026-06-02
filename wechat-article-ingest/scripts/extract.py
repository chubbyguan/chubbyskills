#!/usr/bin/env python3
"""
微信公众号文章 PDF → Markdown 提取工具

用法：
    python extract.py "path/to/article.pdf"
    python extract.py "path/to/article.pdf" --output ./output
    python extract.py "path/to/dir" --batch
"""

import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime


def extract_with_markitdown(pdf_path: str) -> str:
    """Extract text using MarkItDown (preferred)."""
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(pdf_path)
        return result.text_content
    except Exception as e:
        print(f"  ⚠️ MarkItDown failed: {e}", file=sys.stderr)
        return None


def extract_with_pymupdf(pdf_path: str) -> str:
    """Extract text using pymupdf (fallback)."""
    try:
        import pymupdf
        doc = pymupdf.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"  ⚠️ pymupdf failed: {e}", file=sys.stderr)
        return None


def extract_pdf(pdf_path: str) -> str:
    """Extract text from PDF, trying MarkItDown first, then pymupdf."""
    print(f"  📄 Extracting: {os.path.basename(pdf_path)}", file=sys.stderr)
    
    # Try MarkItDown first
    text = extract_with_markitdown(pdf_path)
    
    # Fallback to pymupdf
    if not text or len(text.strip()) < 300:
        print(f"  🔄 Trying pymupdf...", file=sys.stderr)
        text = extract_with_pymupdf(pdf_path)
    
    if not text or len(text.strip()) < 300:
        print(f"  ❌ Too short or failed, skipping", file=sys.stderr)
        return None
    
    return text


def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove page numbers
    text = re.sub(r'\n\d+\n', '\n', text)
    # Remove headers/footers patterns
    text = re.sub(r'\n.*?(关注|分享|点赞|在看).*?\n', '\n', text)
    return text.strip()


def extract_metadata(text: str, filename: str) -> dict:
    """Extract metadata from text."""
    meta = {
        'title': '',
        'author': '',
        'source': '公众号',
        'created': datetime.now().strftime('%Y-%m-%d'),
    }
    
    # Try to extract title from first few lines
    lines = text.split('\n')[:10]
    for line in lines:
        line = line.strip()
        if len(line) > 5 and len(line) < 100:
            if not meta['title']:
                meta['title'] = line
            break
    
    # Try to extract author
    author_match = re.search(r'(作者|作者：|文[：:])\s*(.+)', text[:500])
    if author_match:
        meta['author'] = author_match.group(2).strip()
    
    # Use filename as fallback title
    if not meta['title']:
        meta['title'] = Path(filename).stem
    
    return meta


def generate_markdown(text: str, meta: dict) -> str:
    """Generate Markdown with frontmatter."""
    return f"""---
title: {meta['title']}
type: note
tags: [公众号]
created: {meta['created']}
source: {meta['source']}
author: {meta['author']}
---

# {meta['title']}

{text}"""


def process_single(pdf_path: str, output_dir: str) -> str:
    """Process single PDF file."""
    text = extract_pdf(pdf_path)
    if not text:
        return None
    
    text = clean_text(text)
    meta = extract_metadata(text, pdf_path)
    markdown = generate_markdown(text, meta)
    
    # Generate output filename
    safe_title = "".join(c for c in meta['title'] if c.isalnum() or c in "-_ 《》").strip()
    safe_title = safe_title[:50]
    output_filename = f"{safe_title}.md"
    output_path = os.path.join(output_dir, output_filename)
    
    # Save
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print(f"  ✅ Saved: {output_path}", file=sys.stderr)
    return output_path


def process_batch(input_dir: str, output_dir: str):
    """Process all PDFs in a directory."""
    pdf_files = list(Path(input_dir).glob("*.pdf"))
    print(f"📁 Found {len(pdf_files)} PDF files", file=sys.stderr)
    
    results = []
    for pdf_file in pdf_files:
        print(f"\n{'='*50}", file=sys.stderr)
        result = process_single(str(pdf_file), output_dir)
        if result:
            results.append(result)
    
    print(f"\n🏁 Processed: {len(results)}/{len(pdf_files)}", file=sys.stderr)
    return results


def main():
    parser = argparse.ArgumentParser(description='微信公众号文章 PDF → Markdown')
    parser.add_argument('input', help='PDF 文件或目录')
    parser.add_argument('--output', '-o', default='.', help='输出目录')
    parser.add_argument('--batch', '-b', action='store_true', help='批量处理目录')
    args = parser.parse_args()
    
    if args.batch or os.path.isdir(args.input):
        results = process_batch(args.input, args.output)
    else:
        result = process_single(args.input, args.output)
        results = [result] if result else []
    
    # Print results
    for r in results:
        print(r)


if __name__ == '__main__':
    main()
