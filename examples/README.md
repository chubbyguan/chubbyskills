# 示例输出

这个目录放最小可读的产物样例，方便用户在安装前理解 chubbyskills 的输出形态，也方便 CI 校验统一 frontmatter 协议。

- `outputs/bilibili-sample.md`：视频/字幕类产物
- `outputs/xiaohongshu-sample.md`：图文采集类产物
- `outputs/x-sample.md`：社交媒体采集类产物
- `outputs/wechat-sample.md`：文章采集类产物
- `outputs/workflow-sample.md`：一键 ingest + enrich 后的最终知识库条目

校验命令：

```bash
python3 tools/validate_outputs.py examples/outputs
```
