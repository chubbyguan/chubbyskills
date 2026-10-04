# 订阅简报 enrich 提示词

`subscribe digest --enrich` 的三个阶段各对应一个文件，运行时按文件名加载：

| 文件 | 阶段 | 输出契约（必须保持） |
|---|---|---|
| `prescreen.txt` | 预筛 | JSON `{"keep": [序号]}` |
| `score.txt` | 评分 | JSON `{"scores": {"序号": 1-10}}` |
| `summary.txt` | 摘要 | JSON `{"headline": "...", "summary": "..."}` |

改筛选标准、评分口径或摘要风格只改这里的文字，不用改代码；
但输出的 JSON 结构必须保持不变，否则该阶段会被跳过或报错。
可复制整个目录后用代码内 `prompt_dir` 覆盖做实验。
