# Platform Failure Types and Fallbacks

平台采集失败通常不是单一 bug，而是依赖、权限、风控、链接失效、内容结构变化共同造成。v0.10 把失败分型写进 `platforms/*.yaml`，并用 `tools/platform_smoke.py` 做可复现验证。

## Smoke Layers

```bash
python3 tools/platform_smoke.py --mode offline --check
python3 tools/platform_smoke.py --mode fallback --check
python3 tools/platform_smoke.py --mode live --check
```

- `offline`：不访问网络，验证平台定义能路由到正确 skill。
- `fallback`：验证手动 fallback 平台能离线生成 schema v1 Markdown。
- `live`：只有设置 `CHUBBY_SMOKE_<PLATFORM>_SOURCE` 时才跑真实平台链接。

## Failure Classes

| class | meaning | first action |
|---|---|---|
| `missing_dependency` | 本地缺 `yt-dlp`、`ffmpeg`、`funasr`、`bs4` 等 | 跑 `bash setup.sh doctor` 或对应安装档位 |
| `auth_or_cookie` | 平台需要登录态、cookie 或用户授权 | 配置自己的 cookie，不在 issue 里粘贴敏感信息 |
| `anti_bot_or_rate_limit` | 触发风控、验证码、429、环境异常 | 换公开样例、稍后重试，或走手动 fallback |
| `expired_or_invalid_source` | 短链过期、内容删除、链接格式不支持 | 换原始链接或本地文件 |
| `network` | DNS、连接、超时 | 先确认浏览器能打开，再重试 CLI |

## Platform Fallback Matrix

| platform | likely failures | fallback |
|---|---|---|
| Bilibili | `missing_yt_dlp`, `no_subtitle`, `ffmpeg_or_funasr_missing`, `region_or_login_limit` | 字幕优先；无字幕时走音频转录 |
| Douyin | `expired_short_link`, `anti_bot`, `download_blocked` | 保存本地视频后转录 |
| Podcast | `rss_unreachable`, `audio_download_failed`, `long_audio_timeout` | 下载音频到本地后转录 |
| TikTok | `region_limit`, `anti_bot`, `download_blocked` | 本地视频转录 |
| WeChat | `wechat_client_only`, `html_structure_changed`, `content_too_short` | 导出 PDF 或保存 HTML 后入库 |
| Weibo | `mobile_link_required`, `anti_bot`, `download_blocked` | 优先用 `m.weibo.cn` 链接或本地视频 |
| X | `syndication_unavailable`, `protected_or_deleted_post`, `media_download_failed` | `--fallback-text` 手动正文或 `--fallback-json` 结构化推文 |
| Xiaohongshu | `missing_cookie`, `anti_bot`, `html_structure_changed` | 配置 `XHS_COOKIE` 或 `--fallback-text` |
| YouTube | `missing_yt_dlp`, `no_caption`, `age_or_region_limit` | 字幕优先；无字幕时走音频转录 |
| Zhihu | `embedded_video_unavailable`, `anti_bot`, `download_blocked` | 下载本地视频后转录 |

## 为什么不对抗风控

本项目刻意选择「轻量接口 + 手动兜底」，不使用浏览器自动化（无头浏览器、模拟点击、验证码识别）去对抗平台反爬。原因有三：

- **维护成本不对等**。反爬对抗是持续的猫鼠游戏：平台每次调整页面结构或风控策略，自动化脚本就要跟着修。一个人维护的工具箱追不起这种军备竞赛，追不上的结果就是用户拿到一堆时灵时不灵的脚本。
- **合规边界清晰**。用平台公开的字幕、RSS、嵌入端点和用户自己浏览器里的登录态（`YTDLP_COOKIES_FROM_BROWSER`、`XHS_COOKIE`、`X_COOKIES`），处理的是自己有权访问的内容，定位是个人学习与研究。绕过验证码、伪造设备指纹这类手段会把工具推向另一个合规地带，我们不去。
- **手动兜底是特性不是缺陷**。采集失败时，保存正文、导出 PDF、下载本地视频再导入，对个人用户来说通常比调试一条反爬链路更快。本项目把「失败分型 + 明确的兜底路径」当作核心能力来维护（见上面的 Failure Classes 和 Fallback Matrix），而不是把「什么都能抓下来」当作目标。

如果需求是大规模、持续、多账号地抓取平台数据（舆情监控、商业数据管道等），[MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 这类以浏览器自动化为核心的项目更合适——它们投入对应的维护资源，也要求使用者自行承担账号与合规风险。两条路线服务的是不同场景，不存在谁替代谁。

## 凭据体检

登录态失效是采集类工具最常见的失败原因，而它的表现往往只是一个笼统的"采集失败"。先跑这条命令，它会告诉你**哪些凭据配了、缺的那些怎么拿、以及上一次真实采集的结果**：

```bash
python3 tools/chubby.py doctor --credentials
```

```text
【未配置】
  ⚪ X_COOKIES
     作用：抓 X 长文章（Article）全文；未配置时只取到预览文本
     获取：
       浏览器登录 x.com → 开发者工具 → Application → Cookies → https://x.com
       复制 auth_token 与 ct0 两个值
       export X_COOKIES='auth_token=<值>; ct0=<值>'

【最近一次相关采集】
  x          2026-10-05 11:14  success
  youtube    2026-10-03 15:37  success
```

两点刻意的设计：**凭据的值永远不会被打印**（这份输出常被贴进 issue，值会跟着外传）；**不做主动探活**——探活本身要走真实平台请求，正是可能触发风控的那类流量。凭据是否还有效，以上一次真实采集的结果为准。

## Issue Triage

提交平台失败 issue 时至少贴：

- `python3 tools/platform_smoke.py --mode offline --check` 的结果。
- 平台、公开样例链接、复现命令。
- 失败分型判断：依赖 / cookie / 风控 / 链接 / 网络。
- 如果 live 链接不可公开，贴脱敏 URL 结构和 stderr 关键行。
