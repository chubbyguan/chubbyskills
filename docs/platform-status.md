# Platform Status

Generated at: `2026-06-30T16:59:22+08:00`

This page is generated from `platforms/*.yaml` and `templates/sites/*.yaml`.
Default checks validate repository structure and template coverage. Run with `--local` to include local dependency readiness.

Local dependency check: `off`

| platform | skill | status | content | fallback | template | notes |
|---|---|---|---|---|---|---|
| Bilibili | bilibili-transcribe | stable | video, subtitle | subtitle-first then audio transcription | yes | Subtitle-first path keeps the default install light. |
| Douyin | douyin-transcribe | heavy deps | video | audio transcription | yes | Platform risk is mainly link expiry and anti-bot behavior. |
| Podcast | podcast-transcribe | heavy deps | audio, rss, local_file | local audio file | yes | Long-form audio is slow but stable when local dependencies are ready. |
| TikTok | tiktok-transcribe | beta | video | audio transcription after yt-dlp download | yes | Region limits and anti-bot behavior may affect downloads. |
| WeChat Official Account | wechat-article-ingest | beta | article, pdf | pdf or saved HTML | yes | HTML structure changes frequently; PDF fallback keeps useful coverage. |
| Weibo | weibo-transcribe | beta | video | audio transcription after yt-dlp download | yes | Mobile links are usually more reliable than desktop links. |
| X Twitter | x-ingest | manual fallback | text, image, video | manual text via --fallback-text | yes | Embed endpoint works for many public posts; fallback text protects capture flow. |
| Xiaohongshu | xiaohongshu-ingest | manual fallback | text, image, video | manual text via --fallback-text | yes | Cookie improves success rate; fallback text keeps the knowledge pipeline moving. |
| YouTube | youtube-transcribe | stable | video, subtitle | subtitle-first then audio transcription | yes | Captions provide the fastest path; audio transcription remains available. |
| Zhihu | zhihu-transcribe | beta | video | audio transcription after yt-dlp download | yes | Supports standalone video links and embedded answer/article videos. |

## Status Meaning

- `stable`: text/subtitle-first path is expected to be reliable.
- `beta`: works, but platform markup or anti-bot behavior may change.
- `heavy deps`: requires local audio/video transcription dependencies.
- `manual fallback`: supports manual text fallback when live fetch fails.
- `blocked` / `degraded`: local dependency check found missing required or optional dependencies.
- `broken`: repository definition, script, or template validation failed.

## Commands

```bash
python3 tools/platform_health.py --check
python3 tools/platform_health.py --local --check
python3 tools/platform_health.py --json
```
