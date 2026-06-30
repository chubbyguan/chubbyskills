---
title: Agent 检索工作流
type: note
platform: x
source: https://x.com/example/status/123
created: 2026-06-30
tags: [AI, Agent, 检索]
summary: "Agent 需要先检索 vault，再读取原文，最后带来源回答。"
---

# Agent 检索工作流

Agent 回答知识库问题时，不应该只凭记忆直接生成。可靠流程是：

- 先用语义检索找到候选笔记。
- 再读取最相关的原文。
- 最后用来源路径和关键要点回答用户任务。
