# 订阅与调度（P0）

> **状态：P0 本地功能。** 支持公开 HTTPS RSS / Atom / JSON Feed 和 YouTube 的官方频道 Atom Feed。X、小红书、抖音、B站、公众号账号扫描不在 P0 支持范围。

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
# 查看待审条目
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
- 播客沿用现有 provider 设置，默认本地 `faster-whisper`；
- 成功条目通过 URL / GUID / enclosure identity 去重，重复同步不会重复转录。

恢复暂态失败：

```bash
python3 tools/chubby.py subscribe pending --state retry_wait
python3 tools/chubby.py subscribe process --retry-failed --limit 3
```

`tick` 会自动领取到期重试条目；手动 `process` 需要显式 `--retry-failed`，避免意外重跑。

## 定时调度

订阅 CLI 不启动常驻服务。每小时由系统定时器触发一次；每个来源仍按自身 `poll_minutes` 决定是否实际请求。

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

SQLite 内部 lease 负责阻止重叠 tick；launchd / cron 的重复触发不会并行转录同一条内容。

## 状态与故障处理

```bash
python3 tools/chubby.py subscribe status
python3 tools/chubby.py subscribe status --json
python3 tools/chubby.py subscribe pause yt-3blue1brown
python3 tools/chubby.py subscribe resume yt-3blue1brown
```

| 情况 | 行为 |
|---|---|
| HTTP 304 | 更新检查时间，不产生新任务 |
| 网络超时、429、5xx | 指数退避，最长 24 小时；不推进成功游标 |
| 401 / 403、格式错误、危险 URL | 自动停止该 source 的请求，修复配置后 `resume` |
| 转录失败 | 进入 `retry_wait`；最多三次，再变 `failed_terminal` |
| 素材写入成功、索引失败 | 只重试索引，不重新下载或转录媒体 |
| 进程中断 | 过期 lease 由后续 tick 回收；已成功素材不会重复转录 |

> 调度依赖设备在线。Mac 睡眠或关机期间不会执行；恢复后下一次 tick 会根据 Feed identity 补查新增内容。真正 24/7 需要持续运行的设备或后续部署到持久环境。
