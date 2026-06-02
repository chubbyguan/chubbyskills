---
name: industry-intelligence-radar
description: "行业情报雷达：多源扫描(X/即刻/V2EX/HN) → 关键词过滤 → 趋势检测 → 每日情报简报。触发词：行业情报、竞品监控、热点扫描、情报雷达"
triggers:
  - "行业情报"
  - "竞品监控"
  - "热点扫描"
  - "情报雷达"
  - "今天有什么大事件"
version: 1.0
created: 2026-06-02
tags: [intelligence, monitoring, x-search, trends]
---

# 行业情报雷达

## 核心价值

**信息差优势**：早知道 = 早行动 = 早收益

## 数据源

| 数据源 | 工具 | 更新频率 | 信号强度 |
|--------|------|----------|----------|
| X/Twitter | `x_search` | 实时 | ⭐⭐⭐⭐⭐ |
| 即刻 | web_search | 实时 | ⭐⭐⭐⭐ |
| V2EX | web_search | 分钟级 | ⭐⭐⭐ |
| Hacker News | web_search | 分钟级 | ⭐⭐⭐⭐ |
| 36kr | web_search | 小时级 | ⭐⭐⭐ |
| 虎嗅 | web_search | 小时级 | ⭐⭐⭐ |

## 关键词矩阵

### 用户兴趣领域

```yaml
AI/Agent:
  - "AI agent" OR "AI 工具" OR "LLM" OR "大模型"
  - "Claude" OR "GPT" OR "Gemini" OR "DeepSeek"
  - "MCP" OR "tool use" OR "function calling"

半导体:
  - "半导体" OR "芯片" OR "chip" OR "semiconductor"
  - "台积电" OR "TSMC" OR "英伟达" OR "NVIDIA"

航天:
  - "航天" OR "火箭" OR "卫星" OR "SpaceX"
  - "星链" OR "Starlink"

新能源:
  - "新能源" OR "电动车" OR "电池"
  - "特斯拉" OR "Tesla" OR "比亚迪"

游戏:
  - "游戏" OR "Steam" OR "Switch" OR "PS5"
  - "米哈游" OR "原神" OR "黑神话"

跨境电商:
  - "跨境电商" OR "TikTok Shop" OR "SHEIN"
  - "独立站" OR "DTC"

创业/投资:
  - "创业" OR "融资" OR "投资"
  - "YC" OR "a]6z" OR "红杉"
```

## 工作流程

### Phase 1: 多源扫描（并行）

```bash
# X/Twitter（最高效的信号源）
x_search "AI agent OR LLM OR 大模型" --max_results 20
x_search "半导体 OR 芯片 OR NVIDIA" --max_results 10
x_search "创业 OR 融资 OR YC" --max_results 10

# 即刻（中文高质量讨论）
web_search "site:okjike.com AI OR Agent OR 创业" --max_results 10

# V2EX（技术社区）
web_search "site:v2ex.com AI OR 半导体 OR 创业" --max_results 10

# Hacker News（全球技术趋势）
web_search "site:news.ycombinator.com AI OR LLM OR agent" --max_results 10

# 36kr（商业资讯）
web_search "site:36kr.com AI OR 融资 OR 创业" --max_results 10
```

### Phase 2: 信号过滤

**过滤规则**：
1. **去重**：同一事件只保留最高质量来源
2. **时效**：只保留 24 小时内的内容
3. **信号强度**：
   - 🔴 高信号：融资、发布、政策变化、重大合作
   - 🟡 中信号：产品更新、行业讨论、观点碰撞
   - 🟢 低信号：日常动态、重复信息

### Phase 3: 趋势检测

**检测维度**：
1. **突发趋势**：某话题突然大量出现
2. **持续趋势**：某话题持续一周以上高频出现
3. **新兴趋势**：新概念/新工具首次出现

### Phase 4: 生成情报简报

**输出格式**：

```markdown
# 📡 行业情报简报 - YYYY-MM-DD

## 🔴 高信号（必须关注）

### 1. [事件标题]
- **来源**：X/Twitter @xxx
- **时间**：2 小时前
- **摘要**：一句话概括
- **影响**：对我/行业的影响
- **行动建议**：是否需要立即响应

## 🟡 中信号（值得了解）

### 2. [事件标题]
- **来源**：即刻 @xxx
- **摘要**：一句话概括
- **关联**：与我关注的 XX 领域相关

## 📈 趋势观察

### [趋势名称]
- **热度**：⬆️ 上升 / ⬇️ 下降 / ➡️ 平稳
- **持续时间**：X 天
- **相关讨论**：[链接1] [链接2]

## 💡 机会洞察

基于今日情报，发现以下潜在机会：
1. [机会1]
2. [机会2]

## 📊 数据统计

- 扫描源：5 个
- 原始条目：150+
- 筛选后：25 条
- 高信号：3 条
```

## Cron 配置

```yaml
# 每日早报（工作日 8:30）
schedule: "30 8 * * 1-5"
deliver: feishu

# 可选：午间快报（12:00）
schedule: "0 12 * * 1-5"
deliver: feishu
```

## 输出目标

1. **飞书群**：每日情报推送
2. **知识库**：高价值情报存入 `wiki/📡 外部输入/情报/`
3. **选题库**：发现好选题自动进入选题池

## 反模式

- ❌ 不要追求全量，信号 > 数量
- ❌ 不要只翻译，要有自己的判断
- ❌ 不要忽略中文社区（即刻、V2EX）
- ✅ 每条情报必须有「对我有什么用」的结论
- ✅ 优先独家/一手信息源
