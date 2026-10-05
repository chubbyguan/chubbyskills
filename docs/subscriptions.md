# 订阅与调度（P0 + Provider 兼容层）

> **状态：P0 本地功能 + P1 外部 Feed Provider 兼容层。** 支持公开 HTTPS RSS / Atom / JSON Feed、YouTube 的官方频道 Atom Feed，以及用户自带的 RSSHub、RSS-Bridge 或其它 Provider 的最终公开 Feed。X、小红书、抖音、B站、公众号账号扫描不在支持范围。

订阅模块把“发现更新”和“下载/转录”拆开：同步时只请求 Feed、去重和入队；只有显式启用 `auto_ingest` 或手动 `promote` 后，条目才进入现有的转录与入库管线。

```text
外部定时器 → chubby subscribe tick → Feed 更新发现 → SQLite 队列
→ YouTube / podcast 转录，或 RSS 正文保存 → Markdown → 索引
```

## 前提

先初始化完整项目和知识库：

```bash
python3 tools/chubby.py init --vault "$PWD/creator-vault"
python3 tools/chubby.py subscribe init
```

这会创建：

| 文件 | 作用 | 是否应提交 Git |
|---|---|---|
| `.chubby/subscriptions.json` | 订阅来源和策略 | 默认不提交；团队共享时用 `subscribe --subscriptions /path/to/file` 指定显式配置文件 |
| `<vault>/.chubby/subscriptions.sqlite` | 游标、ETag、队列、失败退避、租约 | 不提交 |
| `.chubby/runs.jsonl` | 既有采集执行审计 | 不提交 |

订阅模块只接受公开 HTTPS URL，不接受 URL 内嵌账号密码或 `token`、`cookie`、`secret` 等查询参数。P0 不支持私有 Feed。

## 添加来源

### YouTube 频道

使用稳定的 `channel_id`，不要使用容易变动的 `@handle`：

```bash
python3 tools/chubby.py subscribe add \
  --id yt-3blue1brown \
  --name "3Blue1Brown" \
  --kind youtube_channel \
  --channel-id UCYO_jab_esuFRV4b17AJtAw \
  --content-profile video \
  --mode discover_only \
  --poll-minutes 240 \
  --exclude-title '(?i)shorts'
```

不知道 `channel_id` 时，可用 `--resolve` 传频道 URL 或 `@handle`，从公开页面解析：

```bash
python3 tools/chubby.py subscribe add \
  --id yt-3blue1brown --name "3Blue1Brown" --kind youtube_channel \
  --resolve "https://www.youtube.com/@3blue1brown" --content-profile video
```

### 播客 RSS

播客是 `feed`，`content_profile` 才决定新条目由 podcast pipeline 处理：

```bash
python3 tools/chubby.py subscribe add \
  --id podcast-acquired \
  --name "目标播客" \
  --kind feed \
  --feed "https://publisher.example/feed.xml" \
  --content-profile podcast \
  --mode discover_only \
  --poll-minutes 360
```

### 普通文章 Feed

```bash
python3 tools/chubby.py subscribe add \
  --id blog-example \
  --name "Example Blog" \
  --kind feed \
  --feed "https://publisher.example/feed.xml" \
  --content-profile article \
  --mode discover_only
```

Feed 提供 `content` / `content:encoded` 时，P0 将其存为 Markdown；只有 `summary` 时，产物会写 `content_completeness: summary` 并保留原文链接。P0 不抓网页详情页，不能把 Feed 摘要误报为全文。

请求默认使用 urllib 标准身份（`Python-urllib/x.y`，如实声明，不伪装浏览器）。个别 host 拉黑该身份时，可按来源覆盖：

```bash
python3 tools/chubby.py subscribe add ... --user-agent "my-feed-reader/1.0"
```

`--provider`（native / rsshub_byo / rssbridge_byo / generic_byo）只记录来源渠道用于健康统计，不改变抓取行为；BYO 表示你自己准备 RSSHub / RSS-Bridge 实例并把它的 feed URL 当普通 feed 订阅。

### 外部 Feed Provider（BYO）

RSSHub、RSS-Bridge 或其它工具可以将公开内容输出为标准 Feed。Chubby 只消费**最终只读 Feed URL**；`byo` 表示 *bring your own*，由你负责部署、帐号授权、平台条款、升级、代理和上游风控。

```bash
python3 tools/chubby.py subscribe add \
  --id creator-rsshub \
  --name "某创作者（自建 RSSHub）" \
  --kind feed \
  --provider rsshub_byo \
  --feed "https://feeds.example.net/creator.atom" \
  --format atom \
  --content-profile auto \
  --mode discover_only
```

| Provider 标签 | 适用范围 | Chubby 的行为 |
|---|---|---|
| `native` | 原生 Feed 与 YouTube 官方 Atom | 只请求最终公开 Feed |
| `rsshub_byo` | 用户自管的 RSSHub 最终 Feed | 只作为来源归因；不调用 RSSHub API 或管理端 |
| `rssbridge_byo` | 用户自管的 RSS-Bridge 输出 | 只作为来源归因；不发现 Bridge 或其路由 |
| `generic_byo` | 其它自管 Feed Provider | 只作为来源归因；不执行专用抓取逻辑 |

| 必须遵守 | 原因 |
|---|---|
| 填最终 RSS / Atom / JSON Feed URL，不能填平台主页、Provider 控制台或管理 API | Chubby 没有网页列表抓取器，也不会猜路由 |
| URL 必须是公开 HTTPS，且不能含 `token`、`cookie`、`secret`、密码或用户名 | P1 没有秘密托管、权限审计或认证 Feed 支持 |
| 私密关注不要使用公共 Provider 实例 | Provider 可能看到订阅 URL 与访问频率 |
| Provider 故障后先修 Provider 或 Feed URL | Chubby 会记录、退避或暂停；不会回退抓取平台源站 |

`provider` 是诊断标签，不控制请求头、代理、认证、解析器或调度频率。变更标签不会清 ETag、重置退避或重新建立历史基线；最终 Markdown 与 `runs.jsonl` 会记录 `subscription_provider`。

## 首次启用：先建立基线

默认首次同步把当前条目写为 `seen`，不会触发历史下载或转录：

```bash
python3 tools/chubby.py subscribe list
python3 tools/chubby.py subscribe test yt-3blue1brown
python3 tools/chubby.py subscribe sync --all
python3 tools/chubby.py subscribe pending
```

明确要少量回填时，才使用上限为 10 的 `--backfill`：

```bash
python3 tools/chubby.py subscribe sync --all --backfill 3
```

回填必须在第一次同步前使用。它只入队最新的 N 条，不会绕过每条内容后续的采集失败处理。

## 审核与自动执行

默认 `discover_only`：新条目进入 `discovered`，人工决定哪些应进入知识库。

```bash
# 查看待审条目（含基线 seen 条目，可随时挑历史内容补采）
python3 tools/chubby.py subscribe pending --state discovered

# 只把选择的条目送入采集与转录
python3 tools/chubby.py subscribe promote 42 43
python3 tools/chubby.py subscribe process --limit 2
```

确认一个来源长期可靠、内容密度足够高后，才设置 `--mode auto_ingest`。自动模式下：

- 每源每次最多入队 3 条，配置可改为 1–10；
- 全局每次处理最多 3 条；
- 标题正则可在添加来源时设定 `--include-title` / `--exclude-title`；
- YouTube 沿用字幕优先、缺字幕才走本地转录；
- 播客沿用现有 provider 设置，默认本地 SenseVoice-Small（funasr）；
- 成功条目通过 URL / GUID / enclosure identity 去重，重复同步不会重复转录。

恢复暂态失败：

```bash
python3 tools/chubby.py subscribe pending --state retry_wait
python3 tools/chubby.py subscribe process --retry-failed --limit 3
```

`tick` 会自动领取到期重试条目；手动 `process` 需要显式 `--retry-failed`，避免意外重跑。

## 每日情报简报（digest）

把订阅队列里近 N 天的条目汇总成一份 Markdown 简报，默认**零 LLM**——不需要任何 key：

```bash
python3 tools/chubby.py subscribe digest                 # 近 1 天，写到 <vault>/30_Output/
python3 tools/chubby.py subscribe digest --days 7 --output digest.md
```

数据源是订阅 SQLite 的 entries 表（`discovered` / `queued` / `ingesting` / `succeeded` 等在途与已处理状态；`seen` 基线与 `skipped` 不计入）。窗口内没有条目时只提示、不写文件。

- **事件聚簇**：标题归一化（小写、去标点、提取关键词 token + 中文二元组）后按 Jaccard 相似度贪心聚簇，同一事件被多个来源报道时聚成一簇。阈值用 `--cluster-threshold` 调（默认 0.5，越高越严格）。
- **热度带时间衰减**：每个独立来源只计一次（同一来源重复报道不叠加），权重按该来源最新一条报道的年龄算——24 小时内满权、24–48 小时减半、超过 48 小时不再计入。这个模型借自 AIHOT 的事件热度：否则一周前被 5 个来源报道过的旧事件会一直压住今早 3 个来源的新事件，在 7 天窗口的站点上尤其明显。全部报道都过期时热度为 0，只显示「N 条 / M 源」而不显示一个误导性的「热度 0」。排序与展示用的是同一个衰减值，不会出现「热度 3 排在热度 5 上面」的错乱。
- **知识库关联**：每个事件用条目标题在 vault 索引里做检索，显示"知识库已有 N 篇相关笔记"（top 3 标题 + 路径）。`--no-vault-links` 可跳过。
- **证据可回查**：已处理（`succeeded`）的条目链接到本地笔记路径；未处理的保留原始 URL。

输出 frontmatter 记录生成时间、窗口、来源数、条目数、聚簇阈值和是否 enrich。同名文件永不覆盖：当天已有简报时自动追加时分秒后辍。

### 可选 LLM 层（--enrich）

```bash
export DEEPSEEK_API_KEY=***
python3 tools/chubby.py subscribe digest --enrich
```

`--enrich` 用 DeepSeek 做三段加工：**预筛**（淘汰灌水条目）→ **评分**（1-10 重要性）→ **中文摘要**（每事件一句话标题 + 两三句摘要，仅处理热度排序前 10 个事件）。边界：

- 模型生成的标题 / 摘要 / 评分一律带 🤖 标注，frontmatter 记 `enriched: true`；每条仍保留原始链接，模型内容永远可回查原文。
- `DEEPSEEK_API_KEY` 缺失时 enrich 直接报错并提示去掉 `--enrich` 用零 LLM 模式；不会静默降级后照出文件。
- 提示词外置在 `templates/digest-prompts/`（`prescreen.txt` / `score.txt` / `summary.txt`）：**改筛选标准、评分口径、摘要风格只改文字，不用改代码**；但各文件的输出 JSON 结构必须保持不变。

### 日报站点（site）

`subscribe site build` 把订阅队列渲染成一个纯静态站点（纯 Python `string.Template`，零 JS 框架、零模板引擎），可直接发到 GitHub Pages：

```bash
python3 tools/chubby.py subscribe site build                          # 默认 <vault>/30_Output/site/
python3 tools/chubby.py subscribe site build --days 30 \
  --site-name "Chubby 情报站" --base-url /chubby-daily --output ./site
```

页面：`index.html`（近 7 天事件流，按热度+时间排序的聚簇卡片）、`archive/<date>.html`（近 30 天每日归档）、`sources.html`（订阅源表：名称、类型、最近检查时间、7 天检查数与成功率，读 source_checks）、`about.html`（项目说明与免责）+ `style.css`。聚簇复用 digest 的标题相似度逻辑，不依赖 digest 的 Markdown 产物。

**Agent 出口**：站点根同时生成 `feed.xml`（RSS 2.0，每个事件一条 item，条目链接指向原始来源而非本站）和 `llms.txt`（llmstxt.org 形状：事件索引 + 订阅源健康表 + 内容边界声明），让站点不只给人看、也能被 Agent 直接消费。`index.html` 的 `<head>` 用 `<link rel="alternate" type="application/rss+xml">` 指向 feed。只有当 `--base-url` 是绝对 URL 时才输出 `atom:link rel="self"`——宁可不写，也不发一个读者解析不了的相对自我地址。Markdown/XML 文本节点只转义 `&`、`<`、`>`（引号保持原样，`Euler's Formula` 不会变成 `Euler&#x27;s Formula`），而 HTML 属性仍用完整转义。
**公开站内容边界（硬规则）**：只放条目标题、来源名、发布时间、原始链接、聚簇热度和来源健康统计；**绝不**输出正文/转录全文、本地 vault 路径、关联笔记标题或任何凭据。`feed.xml` 与 `llms.txt` 受完全相同的约束。所有用户内容转义；泄漏断言由测试保障，且扫描范围覆盖这三个出口。注意输出目录是生成物，重复 build 会**覆盖**（与 digest 的不覆盖惯例不同）。

部署到 GitHub Pages（示例）：

```bash
python3 tools/chubby.py subscribe site build --base-url /<repo> --output /tmp/site
gh repo create <repo> --public --source /tmp/site --push
gh api repos/{owner}/<repo>/pages -X POST -f "build_type=workflow"  # 或用 Settings → Pages 选分支目录
```

也可在仓库里加一个 Actions workflow 定时 build 并推 gh-pages 分支；--site-name 与 --base-url 会注入所有内部链接。

## 定时调度

订阅 CLI 不启动常驻服务。每小时由系统定时器触发一次；每个来源仍按自身 `poll_minutes` 决定是否实际请求。每个来源的下一次到期时间带按来源哈希的确定性抖动（约 ±10%），批量添加的源不会在同一秒集中请求同一个 host。

```bash
python3 tools/chubby.py subscribe tick --due --process-limit 3
```

macOS 推荐 launchd。将下列文件保存为 `~/Library/LaunchAgents/im.chubby.chubbyskills.subscribe.plist`，并替换解释器、仓库和日志的绝对路径：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>im.chubby.chubbyskills.subscribe</string>
  <key>ProgramArguments</key><array>
    <string>/absolute/path/to/.venv/bin/python</string>
    <string>/absolute/path/to/chubbyskills/tools/chubby.py</string>
    <string>subscribe</string><string>tick</string><string>--due</string>
    <string>--process-limit</string><string>3</string>
  </array>
  <key>StartInterval</key><integer>3600</integer>
  <key>StandardOutPath</key><string>/absolute/path/to/logs/subscription.out.log</string>
  <key>StandardErrorPath</key><string>/absolute/path/to/logs/subscription.err.log</string>
</dict></plist>
```

加载和查看状态：

```bash
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/im.chubby.chubbyskills.subscribe.plist
launchctl print "gui/$(id -u)/im.chubby.chubbyskills.subscribe"
```

SQLite 内部 lease 负责阻止重叠 tick；launchd / cron 的重复触发不会并行转录同一条内容。手动 `process` 与定时 `tick` 共用同一把调度锁（4 小时，按最长单条转录时长设定）。条目被领取后，执行线程每 60 秒写一次心跳；只有心跳停止超过 6 小时（即进程崩溃）条目才会被回收重试——长时间转录不会被误判为卡死。

## 状态与故障处理

```bash
python3 tools/chubby.py subscribe status
python3 tools/chubby.py subscribe status --json
python3 tools/chubby.py subscribe pause yt-3blue1brown
python3 tools/chubby.py subscribe resume yt-3blue1brown
python3 tools/chubby.py subscribe requeue 42        # 环境修复后重排终态失败条目
python3 tools/chubby.py subscribe remove old-feed   # 移除来源（历史条目保留）
```

| 情况 | 行为 |
|---|---|
| HTTP 304 | 更新检查时间，不产生新任务 |
| HTTP 401 / 403 | 暂停 source；检查 Provider 是否真的公开最终 Feed，不能向 Chubby 粘贴凭据 |
| HTTP 404 / 其他 4xx | 暂停 source；更新失效 Provider route 后 `resume` |
| HTTP 429、5xx、网络超时 | 指数退避，最长 24 小时；不推进成功游标 |
| XML / JSON 解析失败、响应过大、危险 URL | 暂停 source；修复 Provider 输出或配置后 `resume` |
| 转录失败 | 进入 `retry_wait`；最多三次，再变 `failed_terminal` |
| 素材写入成功、索引失败 | 只重试索引，不重新下载或转录媒体 |
| 进程中断 | 过期 lease 由后续 tick 回收；已成功素材不会重复转录 |

`subscribe status --json` 会输出最近 7 天的检查次数、错误次数、最后一次 HTTP 状态和错误代码。Provider 兼容性的真实放行标准见 [Provider 7 天验收](./subscription-provider-acceptance.md)。

> 调度依赖设备在线。Mac 睡眠或关机期间不会执行；恢复后下一次 tick 会根据 Feed identity 补查新增内容。真正 24/7 需要持续运行的设备或后续部署到持久环境。
