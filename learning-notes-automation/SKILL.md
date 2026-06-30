---
name: learning-notes-automation
description: "学习笔记自动化：视频/播客转录 → 知识点提取 → 闪卡生成 → 知识图谱更新。触发词：学习笔记、闪卡、Anki、知识提取、视频学习"
triggers:
  - "学习笔记"
  - "闪卡"
  - "Anki"
  - "知识提取"
  - "视频学习"
  - "提取知识点"
version: 1.0
created: 2026-06-02
tags: [learning, notes, anki, knowledge-extraction]
---

# 学习笔记自动化

## 核心价值

**被动学习 → 主动记忆**：看视频 ≠ 学会，生成闪卡 = 记住

## 输入源

| 输入类型 | 工具 | 输出格式 |
|----------|------|----------|
| YouTube 视频 | `youtube-transcribe` | 转录文本 |
| B站视频 | `bilibili-transcribe` | 转录文本 |
| 播客 | `podcast-transcribe` | 转录文本 |
| 抖音 | `douyin-transcribe` | 转录文本 |
| 公众号文章 | `wechat-article-ingest` | Markdown |

## 工作流程

### Phase 1: 内容转录

复用本仓库的转录 skill（相对路径，按需替换为你的安装位置）：

```bash
# YouTube（自动翻译）
python3 ../youtube-transcribe/scripts/transcribe.py "https://youtube.com/watch?v=xxx" -o ./

# B站
python3 ../bilibili-transcribe/scripts/transcribe.py "https://bilibili.com/video/xxx" ./

# 播客
python3 ../podcast-transcribe/scripts/transcribe.py "https://xiaoyuzhoufm.com/episode/xxx" ./
```

输出是一份转录 Markdown，作为 Phase 2 的输入。

### Phase 2 + 3: 知识点提取 + 闪卡生成（一步到位）

把转录稿交给 `make_notes.py`，自动提取知识点并生成 Anki 兼容闪卡：

```bash
export DEEPSEEK_API_KEY=***
python3 scripts/make_notes.py 转录稿.md --output ./notes --max-cards 20
# 产出：<标题>-学习笔记.md（核心要点+闪卡+关联知识） 和 <标题>-闪卡.csv（直接导入 Anki）
```

> 脚本用 DeepSeek 输出结构化 JSON，再渲染成下面约定的笔记与闪卡格式。
> 下面是各维度的设计说明，供理解和手动微调时参考。

**提取维度**：

1. **核心概念**（必须掌握）
   - 定义
   - 原理
   - 应用场景

2. **关键事实**（需要记忆）
   - 数据
   - 时间线
   - 人物/公司

3. **方法论**（可以复用）
   - 步骤
   - 框架
   - 最佳实践

4. **金句/洞察**（值得引用）
   - 精辟总结
   - 独特观点

### Phase 3: 闪卡生成

**闪卡格式**（Anki 兼容）：

```markdown
## 闪卡类型

### 1. 概念卡（Cloze Deletion）
Q: {{c1::Transformer}} 架构的核心机制是 {{c2::自注意力（Self-Attention）}}
A: Transformer, 自注意力（Self-Attention）

### 2. 问答卡（Basic）
Q: 什么是 RAG？
A: Retrieval-Augmented Generation，检索增强生成。通过检索外部知识库来增强 LLM 的回答能力，解决幻觉问题。

### 3. 对比卡（Comparison）
Q: Fine-tuning vs RAG 的区别？
A: 
| 维度 | Fine-tuning | RAG |
|------|-------------|-----|
| 成本 | 高（需要训练） | 低（只检索） |
| 更新 | 需要重新训练 | 实时更新 |
| 适用 | 特定任务 | 知识问答 |

### 4. 步骤卡（Process）
Q: 如何构建一个 RAG 系统？
A: 
1. 文档分块（Chunking）
2. 向量化（Embedding）
3. 存入向量数据库
4. 检索相关片段
5. 拼接 Prompt
6. LLM 生成回答
```

### Phase 4: 知识图谱更新

**实体提取**：
- 人物（Who）
- 概念（What）
- 工具/产品（Tool）
- 方法论（How）
- 时间（When）

**关系映射**：
- `发明了`：人物 → 概念/工具
- `属于`：概念 → 领域
- `替代了`：新工具 → 旧工具
- `依赖于`：概念 → 概念

**输出到知识库**：

```markdown
---
title: [概念名]
type: knowledge-card
platform: learning
tags: [学习, AI, ...]
source: [[视频/播客链接]]
created: YYYY-MM-DD
---

# [概念名]

## 定义
一句话定义

## 核心要点
1. ...
2. ...
3. ...

## 关联概念
- [[概念A]]：关系说明
- [[概念B]]：关系说明

## 应用场景
- 场景1：...
- 场景2：...

## 闪卡
（Anki 格式的闪卡内容）
```

## 输出格式

### 1. Anki 闪卡文件

```csv
# 符号分隔格式，可直接导入 Anki
"问题","答案","标签"
"什么是 Transformer?","一种基于自注意力机制的深度学习架构，广泛用于 NLP 任务","AI,深度学习"
```

### 2. 学习笔记 Markdown

```markdown
# [视频标题] - 学习笔记

**来源**：[链接]
**日期**：YYYY-MM-DD
**时长**：XX 分钟
**领域**：AI / 半导体 / ...

---

## 📝 核心要点

### 要点 1：[标题]
- 摘要：...
- 重要性：⭐⭐⭐⭐⭐

### 要点 2：[标题]
- 摘要：...
- 重要性：⭐⭐⭐⭐

---

## 🃏 闪卡（XX 张）

### 概念卡
1. Q: ... A: ...
2. Q: ... A: ...

### 问答卡
1. Q: ... A: ...

---

## 🔗 关联知识

- [[概念A]]：...
- [[概念B]]：...

---

## 💡 个人思考

（基于内容的个人见解和应用想法）
```

### 3. 知识库条目

存入：`wiki/📖 行业研究/[领域]/[概念名].md`

## Cron 配置（可选）

```yaml
# 每周日整理本周学习内容
schedule: "0 20 * * 0"
prompt: "整理本周的所有学习笔记，生成周学习报告"
```

## 使用示例

```
用户：帮我把这个视频做成学习笔记
https://youtube.com/watch?v=xxx

Agent：
1. 转录视频
2. 提取 15 个知识点
3. 生成 20 张闪卡
4. 更新知识图谱
5. 输出 Anki 文件 + Markdown 笔记
```

## 反模式

- ❌ 不要只提取不消化，必须有个人思考
- ❌ 不要生成太多闪卡，质量 > 数量（单视频 15-30 张）
- ❌ 不要忽略知识关联，孤立的知识容易遗忘
- ✅ 闪卡必须可独立理解（不依赖上下文）
- ✅ 每张闪卡只有一个知识点（原子性）
- ✅ 优先生成「为什么」和「怎么做」的卡，而非「是什么」
