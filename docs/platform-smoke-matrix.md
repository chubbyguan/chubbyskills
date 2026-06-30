# Platform Smoke Matrix

Generated at: `2026-06-30T20:53:13+08:00`

This matrix separates deterministic CI checks from optional live platform checks.

- `offline`: verifies platform routing without network access.
- `fallback`: verifies manual fallback can still produce schema v1 Markdown.
- `live`: runs only when `CHUBBY_SMOKE_<PLATFORM>_SOURCE` is set.

| platform | mode | status | failure kind | fallback | detail |
|---|---|---|---|---|---|
| bilibili | offline | passed | - | subtitle-first then audio transcription | routes to bilibili-transcribe/scripts/transcribe.py |
| bilibili | fallback | skipped | - | subtitle-first then audio transcription | platform has no deterministic fallback smoke |
| bilibili | live | skipped | - | subtitle-first then audio transcription | set CHUBBY_SMOKE_BILIBILI_SOURCE to run a live smoke |
| douyin | offline | passed | - | audio transcription | routes to douyin-transcribe/scripts/transcribe.py |
| douyin | fallback | skipped | - | audio transcription | platform has no deterministic fallback smoke |
| douyin | live | skipped | - | audio transcription | set CHUBBY_SMOKE_DOUYIN_SOURCE to run a live smoke |
| podcast | offline | passed | - | local audio file | routes to podcast-transcribe/scripts/transcribe.py |
| podcast | fallback | skipped | - | local audio file | platform has no deterministic fallback smoke |
| podcast | live | skipped | - | local audio file | set CHUBBY_SMOKE_PODCAST_SOURCE to run a live smoke |
| tiktok | offline | passed | - | audio transcription after yt-dlp download | routes to tiktok-transcribe/scripts/transcribe.py |
| tiktok | fallback | skipped | - | audio transcription after yt-dlp download | platform has no deterministic fallback smoke |
| tiktok | live | skipped | - | audio transcription after yt-dlp download | set CHUBBY_SMOKE_TIKTOK_SOURCE to run a live smoke |
| wechat | offline | passed | - | pdf or saved HTML | routes to wechat-article-ingest/scripts/fetch_article.py |
| wechat | fallback | skipped | - | pdf or saved HTML | platform has no deterministic fallback smoke |
| wechat | live | skipped | - | pdf or saved HTML | set CHUBBY_SMOKE_WECHAT_SOURCE to run a live smoke |
| weibo | offline | passed | - | audio transcription after yt-dlp download | routes to weibo-transcribe/scripts/transcribe.py |
| weibo | fallback | skipped | - | audio transcription after yt-dlp download | platform has no deterministic fallback smoke |
| weibo | live | skipped | - | audio transcription after yt-dlp download | set CHUBBY_SMOKE_WEIBO_SOURCE to run a live smoke |
| x | offline | passed | - | manual text via --fallback-text | routes to x-ingest/scripts/fetch_tweet.py |
| x | fallback | passed | - | manual text via --fallback-text | generated schema v1 Markdown |
| x | live | skipped | - | manual text via --fallback-text | set CHUBBY_SMOKE_X_SOURCE to run a live smoke |
| xiaohongshu | offline | passed | - | manual text via --fallback-text | routes to xiaohongshu-ingest/scripts/fetch_note.py |
| xiaohongshu | fallback | passed | - | manual text via --fallback-text | generated schema v1 Markdown |
| xiaohongshu | live | skipped | - | manual text via --fallback-text | set CHUBBY_SMOKE_XIAOHONGSHU_SOURCE to run a live smoke |
| youtube | offline | passed | - | subtitle-first then audio transcription | routes to youtube-transcribe/scripts/transcribe.py |
| youtube | fallback | skipped | - | subtitle-first then audio transcription | platform has no deterministic fallback smoke |
| youtube | live | skipped | - | subtitle-first then audio transcription | set CHUBBY_SMOKE_YOUTUBE_SOURCE to run a live smoke |
| zhihu | offline | passed | - | audio transcription after yt-dlp download | routes to zhihu-transcribe/scripts/transcribe.py |
| zhihu | fallback | skipped | - | audio transcription after yt-dlp download | platform has no deterministic fallback smoke |
| zhihu | live | skipped | - | audio transcription after yt-dlp download | set CHUBBY_SMOKE_ZHIHU_SOURCE to run a live smoke |

## Live Smoke

```bash
export CHUBBY_SMOKE_X_SOURCE='https://x.com/<user>/status/<id>'
python3 tools/platform_smoke.py --mode live --check
```
