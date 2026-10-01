# 外部 Feed Provider：7 天兼容验收

> 这份流程验证的是 **Chubby 安全消费外部 Feed 的机制**。它不认证 RSSHub、RSS-Bridge 或任何平台路由的长期可用性。

## 适用边界

- 只使用公开、已获授权或由自己控制的 Feed。
- 禁止在 `subscriptions.json`、URL、截图、运行记录或验收 JSON 中保存 Cookie、token、密码和 API Key。
- 所有测试 source 保持 `discover_only`；验收阶段不自动下载媒体或调用 ASR。
- Provider 出错时只修 Provider 输出或最终 Feed URL。不要让 Chubby 回退抓平台网页。

## 验收矩阵

| Source | Provider 标签 | 需要证明的行为 |
|---|---|---|
| 一个作者原生 RSS/Atom | `native` | 首次 baseline、后续 304 或新条目、稳定去重 |
| 一个自管 RSSHub route | `rsshub_byo` | 只请求最终 Feed；不会访问管理端或读取凭据 |
| 一个自管 RSS-Bridge 输出 | `rssbridge_byo` | 只请求最终 Feed；429/5xx 被分类并退避 |
| 一个 YouTube 官方 Channel Atom | `native` | 官方 Atom 发现路径持续可用 |

## 执行步骤

```bash
# 1. 四个来源逐个进行无状态请求和解析检查。
python3 tools/chubby.py subscribe validate
python3 tools/chubby.py subscribe test <source-id>

# 2. 首次同步只写 seen 基线。
python3 tools/chubby.py subscribe sync --all

# 3. 每小时由 launchd 或 cron 调度；保留 discover_only，避免产生转录任务。
python3 tools/chubby.py subscribe tick --due --no-process

# 4. 在第 7 天导出审计证据。
python3 tools/chubby.py subscribe status --json > provider-acceptance-7d.json
python3 tools/chubby.py subscribe pending --json > provider-pending-7d.json
```

Mac 休眠会减少检查次数，不应被误判成 Provider 故障。设备累计在线不足时延长观察期。

## 放行阈值

| 条件 | 结果 |
|---|---|
| 每个来源至少 48 次检查，`success + unchanged` 占比至少 95%，无 `parse` | 可标为“在自管样本中完成兼容验证” |
| 有 429 / 5xx，状态页给出准确错误码、退避和修复建议，恢复后继续正常检查 | Chubby 机制通过；该 Provider 保持“可能不稳定”的表述 |
| 重复入队、凭据泄漏到 SQLite / JSONL / Markdown / stdout，或 Provider 故障后抓源站 | 阻断发布 |
| 401 / 403 / 404 / parse 被暂停；修复 URL 后 `resume` 能恢复 | Provider 边界通过 |
| 检查次数不足 48 | 延长观察期，不能写“已验证” |

## 证据解释

`subscribe status --json` 的关键字段：

| 字段 | 含义 |
|---|---|
| `provider` | 来源标签；用于溯源，绝不改变抓取行为 |
| `checks_7d` / `error_checks_7d` | 最近七天的检查和错误次数 |
| `last_check_outcome` / `last_http_status` | 最近一次检查的结果与 HTTP 状态 |
| `last_error_code` | 稳定错误码，例如 `http_429`、`http_5xx` 或 `parse` |
| `last_error` | 最后一个不含秘密的诊断信息 |
