---
name: wechat-article-ingest
description: >
  微信公众号文章 → Markdown 提取 + A层观点提取 + B层问题链生成。
  支持直接链接抓取和 PDF 提取两种方式。
category: productivity
triggers:
  - "处理公众号文章"
  - "公众号入库"
  - "提取观点"
  - "A+B 处理"
  - "把这篇文章转成 markdown"
  - "抓取公众号文章"
version: 1.0.0
tags: [productivity, wechat, article-ingest, knowledge-management]
---

# 微信公众号文章处理 Skill

将微信公众号文章转换为 Markdown，生成 A 层观点提取 + B 层问题链，存入知识库。

## 两种模式

### 模式 1：直接链接抓取（推荐）

```bash
python scripts/fetch_article.py "https://mp.weixin.qq.com/s/xxxxx"
```

公众号文章 URL 是公开的，不需要登录，直接抓取即可。

### 模式 2：PDF 提取

```bash
python scripts/extract.py "path/to/article.pdf"
```

适用于通过「笔记同步助手」等工具导出的 PDF。

## 环境要求

```bash
# Python 3.10+
pip install beautifulsoup4 markitdown pymupdf

# 或者用 uv
uv pip install beautifulsoup4 markitdown pymupdf
```

## 使用方法

### 单篇处理（链接）

```bash
python scripts/fetch_article.py "https://mp.weixin.qq.com/s/xxxxx" --output ./output
```

### 单篇处理（PDF）

```bash
python scripts/extract.py "path/to/article.pdf" --output ./output
```

### A+B 处理（需要 Agent）

```
帮我处理这篇文章：https://mp.weixin.qq.com/s/xxxxx
提取观点 + 问题链
```

## 核心流程

```
公众号链接/PDF → 提取内容 → A层观点提取 + B层问题链 → 存入知识库
```

## A层：观点提取

生成 `观点提取-{作者}-{主题}.md`：

- 🔴 支柱观点（P1-P6）：文章最核心的论点
- 🟡 支撑观点（S1-S8）：支撑支柱的论据
- 🟢 延伸观点（E1-E4）：可以延伸思考的方向
- Takeaway：每条含核心观点 + 行动指向

## B层：问题链

生成 `问题链-{作者}-{主题}.md`：

- 3-5 条问题链，每条对应一个核心主题
- 每条链分 L1（安全区）→ L2（边缘区）→ L3（核心区）
- 每条链 6 道问题
- 终局种子：一个带回家的问题

## 知识库目录结构

```
知识库/
├── 素材库/
│   └── 公众号文章/
│       └── {公众号名}/
│           └── article.md
└── wiki/
    └── 外部输入/
        └── 公众号/
            └── {公众号名}/
                └── {主题}/
                    ├── 观点提取.md
                    └── 问题链.md
```

## 已知限制

- 部分公众号文章有防盗链，可能抓取失败
- 纯图片文章无法提取文字
- MarkItDown 需要 Python ≥ 3.10
- 长文档拆分需要 Agent 判断

## 参考项目

- [microsoft/markitdown](https://github.com/microsoft/markitdown) - PDF/文档转 Markdown
- [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF 处理库
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML 解析
