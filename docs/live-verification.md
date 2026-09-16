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
