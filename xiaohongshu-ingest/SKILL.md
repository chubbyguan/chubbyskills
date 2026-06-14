---
name: xiaohongshu-ingest
description: >
  小红书笔记采集 → 统一 frontmatter Markdown → 爆款拆解 + 衍生选题。
  支持笔记链接和 xhslink 短链；爆款拆解按「人群×场景×痛点×情绪×钩子」生成可复用选题。
category: content
triggers:
  - 用户发送小红书笔记链接
  - "采集这篇小红书笔记"
  - "拆解这个爆款笔记"
  - "帮我做小红书选题"
version: 1.0.0
tags: [content, xiaohongshu, ingest, hook-analysis, topic]
---

# 小红书采集 + 爆款拆解 Skill

把小红书笔记抓成结构化 Markdown 入库，再用 DeepSeek 拆解爆款逻辑、衍生可直接写的选题。
补齐了仓库在「中文内容采集」上最大的平台缺口，也是「采集 → 选题」创作工作流的起点。

## 环境要求

```bash
# 采集脚本零依赖（仅 Python 标准库）

# 强烈建议：配置 cookie 以规避风控（从浏览器登录后复制）
export XHS_COOKIE="你的小红书 cookie 字符串"

# 爆款拆解需要 DeepSeek API Key
export DEEPSEEK_API_KEY="your-api-key"
```

## 使用方法

```bash
# 1) 采集笔记 → 统一 frontmatter Markdown
python scripts/fetch_note.py "https://www.xiaohongshu.com/explore/xxxx" -o ./out
python scripts/fetch_note.py "http://xhslink.com/xxxx" -o ./out

# 2) 爆款拆解 → 拆解报告 + 5 条衍生选题
python scripts/analyze_hook.py ./out/某笔记.md -o ./out
```

## 产出

- `fetch_note.py`：标题、正文、标签、作者、互动数据（赞/藏/评）、图片链接 → 统一 frontmatter Markdown（`platform: xiaohongshu`）
- `analyze_hook.py`：目标人群 / 场景 / 痛点 / 情绪价值 / 标题钩子 / 正文结构 / 可复用模板 / 5 条衍生选题（带 `- [ ]` 勾选，可直接进选题库）

## ⚠️ 关于反爬（务必先读）

小红书风控严格，**未登录的纯脚本访问经常被拦**。本 skill 的策略：

1. 优先解析页面内嵌的 `__INITIAL_STATE__` 结构化数据
2. 失败则回退到 `og:` 元标签
3. 仍失败时给出明确提示——此时可**手动复制笔记正文**存成 `.txt`，直接走 `analyze_hook.py` 拆解（拆解环节不依赖抓取）

提供 `XHS_COOKIE` 能显著提高采集成功率。页面结构若调整，需更新 `fetch_note.py` 里的选择器。

## 合规声明

仅供**个人学习与研究**使用。请遵守小红书用户协议与 robots 规则，控制请求频率，不要用于批量抓取、商用爬取或侵犯他人权益的场景。

## 衔接工作流

- 采集产物 → `knowledge-base-management` 入库（统一 frontmatter，按 `platform` 聚合）
- 衍生选题 → 创作者选题流（采集 → 拆解 → 选题库 → 初稿）
- 多篇拆解 → 沉淀「爆款选题库」，对接 `industry-intelligence-radar` 的趋势信号

## 参考

- 小红书爆款方法论：人群 × 场景 × 痛点 + 情绪价值
- [DeepSeek](https://platform.deepseek.com/) — 拆解用 LLM
