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
| X | `syndication_unavailable`, `protected_or_deleted_post`, `media_download_failed` | `--fallback-text` 手动正文 |
| Xiaohongshu | `missing_cookie`, `anti_bot`, `html_structure_changed` | 配置 `XHS_COOKIE` 或 `--fallback-text` |
| YouTube | `missing_yt_dlp`, `no_caption`, `age_or_region_limit` | 字幕优先；无字幕时走音频转录 |
| Zhihu | `embedded_video_unavailable`, `anti_bot`, `download_blocked` | 下载本地视频后转录 |

## Issue Triage

提交平台失败 issue 时至少贴：

- `python3 tools/platform_smoke.py --mode offline --check` 的结果。
- 平台、公开样例链接、复现命令。
- 失败分型判断：依赖 / cookie / 风控 / 链接 / 网络。
- 如果 live 链接不可公开，贴脱敏 URL 结构和 stderr 关键行。
