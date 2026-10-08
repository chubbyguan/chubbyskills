# 订阅系统架构总览

> 本文档对齐心智模型：CLI 层、状态层、skill 层各管什么，以及它们之间如何协作。
> 不会重复 `docs/subscriptions.md` 的命令手册，那篇讲「怎么用」，这篇讲「为什么这样设计」。

---

## 1. 分层结构

```
┌─────────────────────────────────────────────────────────────────┐
│  用户入口                                                        │
│  chubby subscribe <子命令>                                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  CLI 层                                                          │
│  tools/chubby.py 中 subscribe 子命令组                            │
│  → tools/subscriptions.py 分发到具体 handler                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
┌─────────▼──────────┐  ┌──────▼──────────┐  ┌─────▼─────────────┐
│  状态与调度层       │  │  执行引擎层     │  │  知识库输出层      │
│  subscription_     │  │  subscription_  │  │  subscription_    │
│  store.py          │  │  executor.py    │  │  digest.py        │
│  subscription_     │  │                 │  │  subscription_    │
│  schedule.py       │  │                 │  │  site.py          │
└─────────┬──────────┘  └──────┬──────────┘  └───────────────────┘
          │                    │
          │         ┌──────────┼──────────┐
          │         │          │          │
          │    ┌────▼────┐ ┌──▼───┐ ┌───▼────┐
          │    │ 适配器  │ │ 去重 │ │ 降级   │
          │    │ layer   │ │ /队列│ │ /重试  │
          │    │adapters │ │store │ │executor│
          │    │.py     │ │.py   │ │.py     │
          │    └─────────┘ └──────┘ └────────┘
          │
┌─────────▼──────────────────────────────────────────────────────┐
│  平台 skill 层                                                   │
│  podcast-transcribe / youtube-transcribe / bilibili-transcribe  │
│  x-ingest / wechat-article-ingest / ...                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 各层职责

### 2.1 CLI 层（chubby.py subscribe + tools/subscriptions.py）

**管什么**：参数解析、子命令分发、用户可见的输出格式。

**不管什么**：不直接抓网页、不转录、不写 Markdown。这些全部委托给下层。

关键子命令分组：

| 分组 | 子命令 | 作用 |
|---|---|---|
| 生命周期 | `init`, `validate`, `remove` | 初始化/校验/删除订阅源 |
| 日常操作 | `list`, `status`, `pause`, `resume` | 查看和暂停恢复 |
| 同步 | `sync`, `tick`, `test` | 发现 Feed 更新 |
| 队列 | `pending`, `promote`, `requeue`, `skip`, `process` | 条目从发现到执行的流转 |
| 产物 | `digest`, `schedule` | 生成情报简报 / 安装定时器 |

### 2.2 状态与调度层

**subscription_store.py**：SQLite 游标管理。每个 source 记录：
- `last_etag` / `last_modified`：HTTP 缓存验证
- `next_due_at`：下次轮询时间
- `entry_key`：条目去重（URL 或内容 hash）
- 条目状态机：`seen → discovered → queued → ingesting → succeeded / failed_terminal`

**subscription_schedule.py**：OS 定时器安装。支持：
- macOS launchd（label: `im.chubby.chubbyskills.subscribe`）
- systemd timer（`chubbyskills-subscribe.service` / `.timer`）

核心原则：**定时器只调 `chubby subscribe tick`，不直接跑转录**。tick 内部做 sync + bounded processing。

### 2.3 执行引擎层

**subscription_executor.py**：条目执行器。拿到 `queued` 条目后：
1. 根据 `content-profile`（video / podcast / article / auto）路由到对应 skill
2. 调用 skill 脚本，监控超时
3. 把结果写回 SQLite（`succeeded` / `failed_terminal` / `retry_wait`）

**subscription_adapters.py**：Feed 解析适配层。统一处理：
- RSS / Atom / JSON Feed
- YouTube 官方 Atom（通过 channel_id）
- RSSHub / RSS-Bridge 输出（diagnostic provenance only）

### 2.4 知识库输出层

**subscription_digest.py**：每日情报简报。输入是 SQLite 中 recent entries，输出是 `<vault>/30_Output/subscription-digest-YYYY-MM-DD.md`。

默认零 LLM：只做标题相似度聚类（Jaccard），可选 `--enrich` 加 DeepSeek 摘要层。

**subscription_site.py**：静态站点生成。输出 HTML + `feed.xml` + `llms.txt`，全部硬边界（不暴露 vault 路径、不暴露正文）。

### 2.5 平台 skill 层

**独立于订阅系统**：podcast-transcribe、industry-intelligence-radar 等 skill 有自己独立的 RSS/批处理逻辑，不经过 `subscribe` 命令。

**通过订阅系统接入**：youtube-transcribe、bilibili-transcribe、x-ingest 等可以通过 `subscribe add` 注册为 source，由订阅系统调度执行。

边界：skill 层只负责「单个条目的抓取/转录」，不管理定时、去重、队列。

---

## 3. 数据流

```
用户: chubby subscribe add --kind feed --feed https://example.com/rss
  ↓
CLI 层: 写入 subscriptions.json
  ↓
定时器: 每小时触发 chubby subscribe tick
  ↓
sync: 请求 Feed → 去重 → 写入 SQLite (discovered)
  ↓
用户/自动: promote / auto_ingest → queued
  ↓
process: 调用 skill 脚本 → 转录/保存 → Markdown
  ↓
vault_index: 索引入库
  ↓
digest/site: 生成简报或静态站
```

---

## 4. 配置文件说明

| 文件 | 位置 | 作用 | 是否应提交 Git |
|---|---|---|---|
| `subscriptions.json` | `.chubby/` 或 `--subscriptions` 指定 | 订阅源列表和策略 | 默认不提交；团队共享时用显式路径 |
| `subscriptions.sqlite` | `<vault>/.chubby/` | 游标、队列、失败退避 | 不提交 |
| `runs.jsonl` | `.chubby/` | 采集执行审计 | 不提交 |

> 如果团队需要共享订阅源配置，用 `chubby subscribe --subscriptions /path/to/shared.json` 显式指定，不要提交默认位置的 `.chubby/`。

---

## 5. 独立 skill 与订阅系统的关系

| skill | 独立 RSS 支持 | 是否走 subscribe | 说明 |
|---|---|---|---|
| podcast-transcribe | ✅ 有 `--rss-url` | ❌ 不经过 | 独立批处理，状态目录自管理 |
| industry-intelligence-radar | ✅ 有 `config.rss` | ❌ 不经过 | 独立扫描，输出情报简报 |
| youtube-transcribe | ✅ 通过 channel_id | ✅ 经过 | 通过 `subscribe add --kind youtube_channel` 接入 |
| bilibili-transcribe | ❌ 无 | N/A | 手动发链接，不订阅 |
| x-ingest | ❌ 无 | N/A | 手动发链接，不订阅 |

**设计原则**：订阅系统只管理「有稳定 Feed URL 或频道 ID 的内容源」。没有 Feed 的平台（X、小红书、抖音、B站）需要手动触发。

---

## 6. 常见问题

**Q: 订阅系统和 skill 自己的 RSS 功能有什么区别？**

A: 订阅系统管「定时发现 + 去重 + 队列 + 调度」，是长期运行的管线。skill 自己的 RSS 功能是一次性批处理，适合单次跑完就结束的场景。

**Q: 定时器装在哪？**

A: `chubby subscribe schedule install` 会探测当前系统（macOS → launchd，Linux → systemd）并生成 unit 文件。路径和解释器自动从运行环境推导，不需要手动修改绝对路径。

**Q: 一个条目失败了怎么办？**

A: 失败条目进入 `failed_terminal` 状态，环境修复后 `chubby subscribe requeue <entry_id>` 重新入队。`--retry-failed` 参数可在 process 时一并处理。

**Q: 订阅系统的输出和 skill 直接运行输出有区别吗？**

A: 没有内容区别，都是同一个 skill 脚本产出 Markdown。区别在于订阅系统会自动加 frontmatter、索引到 vault、记录运行状态，并支持后续 digest/site 聚合。
