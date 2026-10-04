# 真实平台验证记录

日期：**2026-09-16**。版本：**0.11.1**。环境：macOS、Python 3.12.13、yt-dlp 2026.8.19；轻量采集环境未安装 funasr，不配置平台登录 Cookie。

本轮每个平台选 1 条公开来源，记录最终结果。调试过程重试不算独立样本，不能据此估计整个平台的成功率。成功意味着此次自动采集产生了符合 schema v1 的正文；没有人工粘贴 fallback。未完成逐字转录准确率或用户满意度评估。

| 平台 | 样本与最终结果 | 验证时间（UTC+8） | 观察与边界 |
|---|---|---|---|
| X | 1/1 完成：[OpenAI 公开推文](https://x.com/OpenAI/status/1663696190960173056) | 17:00:58 | 正文段落与来源保存；正文区 194 字符，含标题和展示信息。只验证这条纯文本推文。 |
| YouTube | 1/1 完成：[3Blue1Brown 神经网络视频](https://www.youtube.com/watch?v=aircAruvnKk) | 17:01:08 | 获取字幕，正文区 18,602 字符；标题、来源、YAML 和正文开头已由 Agent 检查。没有逐字校对、翻译或 ASR 验收。 |
| B站 | 0/1 完成：[李沐—还是要读论文](https://www.bilibili.com/video/BV1mw4m1r7Su/) | 16:58:16 | 读到标题并下载音频，没有可用字幕；本环境缺少 funasr，转录被阻塞。不能把这个结果归为平台失效。 |
| 其余 7 类平台 | 未验证 | — | 没有本轮真实样本，不以离线路由、定义状态或手动 fallback 代替在线结果。 |

本轮还发现并修复了 YouTube 元数据空标题、管线将无效产物记为成功，以及日志前缀误识别为输出路径的问题。以上 X/YouTube 结果来自修复后的再次采集。

## 可追溯信息

脱敏机器摘要：[live-verification.json](live-verification.json)。其中包含具体来源、依赖版本、检查时间、字节数和完整产物 SHA-256。`human_verified: false` 表示没有把 Agent 抽查冒充为人工验收。

- X Markdown SHA-256：`a05795d060200d27d2bc1158f0363b787b2dab90e2885db0e1f2500ea2fc12ae`
- YouTube Markdown SHA-256：`bd4baa22c51aff3037cd421a0792d7b5ca7232228ae88df86a6a7ce1d7802546`

完整产物和原始日志保存在执行环境的 `runs/live-2026-09-16-verified/`；失败记录保存在 `runs/live-2026-09-16-final/`。这些目录被 Git 忽略，未公开转载完整字幕，也未把本机绝对路径带入机器摘要。产物包含运行时间，重跑后的 hash 变化是正常现象。

## 复跑

在虚拟环境安装 `yt-dlp`、按需的 `beautifulsoup4` 和所选内容类型的转录依赖：

```bash
export CHUBBY_SMOKE_X_SOURCE='https://x.com/OpenAI/status/1663696190960173056'
export CHUBBY_SMOKE_YOUTUBE_SOURCE='https://www.youtube.com/watch?v=aircAruvnKk'
python3 tools/platform_smoke.py --mode live --platform x --platform youtube \
  --require-live --check --artifacts-dir runs/live-check --json
```

缺少指定来源、采集失败或输出不符合协议时返回非零。`evidence.json`、日志和 Markdown 会保留在每个平台单独的目录里；分享前检查内容和链接中是否包含私密信息。

GitHub 的 **Real text and subtitle verification (manual)** workflow 可手动选择一条公开链接，保留七天产物。它只提供图文/字幕依赖，不安装 ASR 或登录 Cookie；这些能力需要另外准备环境，不能依靠该 workflow 验证。

结构检查生成时间见 [platform-status](platform-status.md)，离线/fallback 结果见 [platform-smoke-matrix](platform-smoke-matrix.md)。生成日期不等于真实采集验证日期。

## 2026-10 补充实测记录

以下为 2026-10 期间完成、此前未落档的真实环境验证。均为单次或单点实测，不代表持续可用性。

### PR #27：yt-dlp 浏览器 Cookie 与 JS 挑战组件透传（2026-10-01/02）

环境变量 `YTDLP_COOKIES_FROM_BROWSER`（对应 `--cookies-from-browser`）和 `YTDLP_REMOTE_COMPONENTS`（对应 `--remote-components`，让 yt-dlp 下载 JS 挑战求解组件）透传到所有平台技能的 yt-dlp 调用（commit `7fd82e0`）。实测：在会被 YouTube 拦截为 `Sign in to confirm you are not a bot` 的出口 IP 上，两个变量同时设置后自动字幕下载成功。Cookie 来自用户自己浏览器的登录态，属个人使用路径。

### PR #31：抖音 spider-shell 回退（2026-10）

无 Cookie 访问抖音分享页时平台返回反爬 shell 页（spider shell），下载器检测到后自动回退到 yt-dlp 路径，配合 `YTDLP_COOKIES_FROM_BROWSER` 即可（浏览器访问过 douyin.com 即可，无需登录）。文档化于 commit `2af5d14`，见 [platform-status](platform-status.md) 和 `platforms/douyin.yaml`。

### YouTube 频道订阅单日深度验收（2026-10-03）

按 `docs/subscription-provider-acceptance.md` 对 YouTube 频道路径（3Blue1Brown，原生 Atom + yt-dlp 回退发现）做单日验收，10 项验收标准全部通过：首次基线 25 条入库、后续同步零重复（25 parsed / 0 new / 25 duplicates）、Atom 发现 HTTP 200、yt-dlp 回退路径直测返回与 Atom 完全一致的 25 条 video ID、凭据不泄漏（SQLite/JSON/stdout 检查无 token/cookie）、discover_only 不自动处理、promote 后字幕优先 23 秒完成且不触发音频转录、tick 调度锁竞争时正确跳过、到期语义与按源抖动正常、`status --json` 证据字段齐全。一个部分覆盖项：youtube_channel 源的 Atom 4xx 会被 yt-dlp 回退掩盖为 `network` 退避而非按 404 暂停，属设计取舍，已记为观察项。7 天连续观察（≥48 次检查、success+unchanged ≥95%）尚未完成，不写「已验证」；验收证据存于执行环境未入库目录，结论以本节为准。

### SenseVoice-Small vs Qwen3-ASR-0.6B 本地实测（2026-10-03）

MacBook Pro M3 Pro（18GB）纯 CPU，torch 2.14.1，5 分钟中文双人播客（茶文化专名/人名/数字密集）：SenseVoice-Small RTF **0.11**（32.8 秒），Qwen3-ASR-0.6B RTF **0.80**（240.4 秒），约 7 倍差距。质量互有胜负：Qwen 在专名（岩茶）和人名（朱伟）上更稳，但出现 LLM 式幻觉改写（「黄金」→「皇帝」），且无 ITN（数字输出为中文大写形式）；SenseVoice 有同音字错误但数字下游友好。**结论：CPU 场景保持 SenseVoice-Small 为默认；GPU 或专名敏感场景可选 Qwen3-ASR。**

### 仍待真实验收

- ~~Groq（`whisper-large-v3-turbo`）云转录后端~~：已于 2026-10-04 完成真实验收，见下。
- DashScope（`qwen3-asr-flash`）云转录后端：代码与限额检查就绪，未完成真实转录验收。
- ~~X 长文章（Articles）登录态全文路径（`X_COOKIES`）~~：已于 2026-10-04 完成真实验收，见下。

## 2026-10-04 验收：Groq 云转录后端

- **实测**：5 分钟中文双人播客（16kHz mono，`whisper-large-v3-turbo`），提交后 **3 秒**返回，154 个时间戳分段；二次运行命中本地缓存 0 秒零请求。文本流畅，专名表现稳定（「马连道」正确、「朱伟」第二次出现正确），无幻觉改写，偶有同音字（「茶」→「查」）。
- **修复**：Groq 的 Cloudflare 前置会拒绝 Python urllib 默认 UA（GET 403、POST 上传中断），`CloudProvider.request` 现统一携带桌面浏览器 UA 与 `Accept: application/json`（对 DashScope 同样无害），并有回归测试锁定。
- **注意**：本机经代理访问 api.groq.com；免费层有速率限制，长音频分片路径未在本轮实测覆盖。

## 2026-10-04 复测：X 长文章登录态全文抓取修复

- **背景**：线上发现 `x-ingest` 登录态全文抓取失效 —— `fetch_article_graphql()` 内置的两个硬编码 queryId（`DJS3BdhUhcaEpZ7B7irJDg`、`V3vfsYzNEyD9tsf4xoPhgw`）对 `TweetResultByRestId` 全部返回 404，登录 cookie 有效也无济于事，只能拿到 syndication 预览。
- **诊断**：用桌面 Chrome UA + 登录 cookie 拉 `https://x.com/home`，HTML 引用 `https://abs.twimg.com/responsive-web/client-web/main.<hash>.js`；在该 bundle 中匹配 `queryId:"...",operationName:"TweetResultByRestId"` 挖到当前有效 queryId `LbQZrAWyKPvExi8di3-EoA`。另发现该操作要求 `fieldToggles`（`withArticlePlainText` / `withArticleRichContentState` 置 true）才会返回 `plain_text` / `content_state`，否则 article 结果只有标题和预览；且 `TweetResultByRestId` 必须以**推文 id** 为参数（旧代码误传 syndication 返回的 article rest_id，同样拿不到全文）。
- **修复**：queryId 获取改为「新鲜缓存（`~/.cache/x-ingest/tweet-result-query-ids.json`，TTL 24h）→ 实时从 x.com 前端 JS bundle 提取并写缓存 → 过期缓存 → 内置兜底列表」；GraphQL 请求补齐新版 features 全集与 `fieldToggles`；正文抓取改用推文 id。
- **验证**（macOS，登录 cookie 有效）：`python3 x-ingest/scripts/fetch_tweet.py "https://x.com/369Serena/status/2103705402793730449" -o /tmp/x-fixed` 抓到全文 **2859 字**（正文，标题《小红书矩阵获客指南-全网独家，让你的活动 or 课程爆满！！！》），封面图本地化，无「预览」标注；同链接不带 cookie 复跑维持预览 + stderr 告警路径，无回归。
