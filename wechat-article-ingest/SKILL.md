---
name: wechat-article-ingest
description: >
  微信公众号文章 PDF → Markdown 提取 + A层观点提取 + B层问题链生成。
  支持批量处理、长文档子主题拆分。
category: productivity
triggers:
  - "处理公众号文章"
  - "公众号入库"
  - "提取观点"
  - "A+B 处理"
  - "观点提取"
  - "问题链"
version: 1.0.0
tags: [productivity, wechat, article-ingest, knowledge-management]
---

# 微信公众号文章处理 Skill

将微信公众号文章 PDF 提取为 Markdown，生成 A 层观点提取 + B 层问题链，存入知识库。

## 为什么需要这个

微信公众号文章没有稳定的网页抓取方式（反爬、需要登录），但可以通过「笔记同步助手」等工具导出 PDF。这个 skill 解决：

- PDF → Markdown 结构化提取
- 观点提取（A层）：核心观点矩阵 + Takeaway
- 问题链生成（B层）：L1→L2→L3 递进式提问
- 长文档自动拆子主题

## 环境要求

```bash
# Python 3.10+
pip install markitdown pymupdf

# 或者用 uv
uv pip install markitdown pymupdf
```

## 核心流程

```
PDF 文件 → MarkItDown 提取 → 判断是否拆子主题 → A层观点提取 + B层问题链 → 存入知识库
```

## 使用方法

### 单篇处理

```bash
python scripts/extract.py "path/to/article.pdf" --output ./output
```

### A+B 处理（需要 Agent）

```
帮我处理这篇文章：path/to/article.pdf
提取观点 + 问题链
```

### 批量处理

```
处理素材库里最近的公众号文章
```

## Step 1: PDF → Markdown

### 首选：MarkItDown

```bash
python3 -m markitdown path/to/file.pdf > /tmp/output.md
```

MarkItDown 保留标题层级、列表、表格结构。

### 备选：pymupdf

```python
import pymupdf
doc = pymupdf.open('path/to/file.pdf')
text = ""
for page in doc:
    text += page.get_text()
```

纯文本，丢失格式但内容完整。

### 跳过规则

- 两种提取都返回 <300 字有效文本 → 纯图片扫描件，跳过
- 内容 <500 字 → 跳过
- 纯英文文章 → 跳过

## Step 2: A层观点提取

生成 `观点提取-{作者}-{主题}.md`：

```markdown
---
title: "{作者}：{主题} — 观点提取与知识卡片"
type: note
tags: [公众号, 主题标签...]
created: YYYY-MM-DD
source: "原文链接或路径"
summary: "一句话摘要"
---

# {作者}：{主题}

## 核心观点矩阵

### 🔴 支柱观点（P1-P6）
- P1: ...
- P2: ...

### 🟡 支撑观点（S1-S8）
- S1: ...

### 🟢 延伸观点（E1-E4）
- E1: ...

## Takeaway

1. **核心观点** → 行动指向
2. ...
```

## Step 3: B层问题链

生成 `问题链-{作者}-{主题}.md`：

```markdown
---
title: "{作者}：{主题} — 问题链与伴读引导"
type: note
tags: [问题链, 伴读...]
created: YYYY-MM-DD
source: "原文链接或路径"
paired_with: "[[观点提取-{作者}-{主题}]]"
---

# {作者}：{主题} — 问题链

## 问题链 1：{主题关键词}

### L1 安全区（你知道的）
- Q1: ...

### L2 边缘区（你模糊知道的）
- Q3: ...

### L3 核心区（你没想到的）
- Q5: ...

## 伴读指南
...

## 终局种子
一个带回家的问题。
```

## Step 4: 长文档子主题拆分

当一篇 PDF 报告有多个独立章节时：

1. **提取全文** → MarkItDown 转 Markdown
2. **识别子主题** → 提取 3-5 个最相关的独立子主题
3. **每个子主题独立 A+B** → 每篇设独立子目录
4. **并行分派** → 多 Agent 并行处理

## 知识库目录结构

```
知识库/
├── 素材库/
│   └── 公众号文章/
│       └── {公众号名}/
│           └── article.pdf
└── wiki/
    └── 外部输入/
        └── 公众号/
            └── {公众号名}/
                └── {主题}/
                    ├── 观点提取.md
                    └── 问题链.md
```

## 已知限制

- MarkItDown 需要 Python ≥ 3.10
- 纯图片扫描件无法提取（需要 OCR）
- 某些 PDF 有加密保护，无法解析
- 长文档拆分需要 Agent 判断，不是纯脚本能完成

## 参考项目

- [microsoft/markitdown](https://github.com/microsoft/markitdown) - PDF/文档转 Markdown
- [pymupdf/PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF 处理库
