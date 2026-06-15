---
name: content-enrich
description: >
  内容加工：给任意采集产物（转录稿 / 文章 / 笔记）自动补「摘要 + 要点 + 标签 + 价值判断」，
  写进 frontmatter 并在正文顶部插入摘要块。是「加工层」通用能力，惠及仓库所有采集 skill。
category: content
triggers:
  - "给这篇笔记加摘要"
  - "提炼要点和标签"
  - "加工一下采集的内容"
  - "批量给知识库补摘要"
version: 1.0.0
tags: [content, enrich, summary, tagging, knowledge-base]
---

# 内容加工（Content Enrich）

采集进来的转录稿、文章往往是大段原始文本，没人愿意回头看。这个 skill 给**任意采集产物**
自动补上可快速消化的元信息——它是「加工层」的通用能力，配合仓库里所有采集 skill 使用。

## 环境要求

```bash
# 零 pip 依赖（仅 Python 标准库）
export DEEPSEEK_API_KEY="your-api-key"   # 必需，用于提炼
```

## 使用方法

```bash
python scripts/enrich.py 某篇笔记.md              # 就地增强单篇
python scripts/enrich.py ./vault/外部输入/         # 批量增强整个目录下的 .md
python scripts/enrich.py 某篇.md --output ./out    # 不改原文件，输出到 out/
python scripts/enrich.py 某篇.md --force           # 已加工过的重新加工
```

## 产出

在原 Markdown 上（原内容完整保留）：

- **frontmatter 注入**：`summary`（一句话总结）、`domain`（领域）、`auto_tags`（标签列表）、`enriched: true`
- **正文顶部插入 `## 📝 摘要` 区块**：一句话 TL;DR、3-5 条要点、「值得深读？」判断、标签

幂等：默认跳过已加工（`enriched: true`）的文件，可 `--force` 重做。

## 为什么有用

- **盘活采集产物**：转录稿 / 文章一眼能看懂讲了啥、值不值得深读
- **便于知识库聚合**：`auto_tags` / `domain` 进 frontmatter，Obsidian Dataview 可直接按标签 / 领域聚合
- **一处投入，惠及全部**：抖音 / B站 / 小红书 / X / 公众号 …… 任何采集产物都能加工

## 衔接工作流

```
采集（任意 *-ingest / *-transcribe skill）
  → content-enrich（补摘要 + 要点 + 标签）
  → knowledge-base-management 入库（按 auto_tags / domain 聚合检索）
```

## 参考

- [DeepSeek](https://platform.deepseek.com/) — 提炼用 LLM
