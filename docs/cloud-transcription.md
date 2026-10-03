# 可选云端播客转录

播客默认使用本地 SenseVoice-Small（与视频类技能共用的 `chubby_common/funasr.py` 封装）。可选云端后端有两个，均需主动选择：

- `dashscope`：阿里云百炼 DashScope 的 `qwen3-asr-flash`，通过 OpenAI 兼容接口同步返回全文。
- `groq`：Groq 的 `whisper-large-v3-turbo`，通过 OpenAI 兼容的 `audio/transcriptions` 接口同步返回全文和分段时间戳。

此前的 Atlas / MuAPI 实验后端已被 DashScope 取代并移除。需求最初来自 [PR #3](https://github.com/chubbyguan/chubbyskills/pull/3)（[binyangzhu000-sudo](https://github.com/binyangzhu000-sudo)）和 [PR #5](https://github.com/chubbyguan/chubbyskills/pull/5)（[Anil-matcha](https://github.com/Anil-matcha)），归属保留。

> **验收状态**：`dashscope` 与 `groq` 两个后端（2026-10 接入）的请求构造、状态恢复和错误路径均有单测覆盖，但**尚未完成真实账号的在线验收**。首次使用前请用短音频自行验证，结果欢迎反馈到 issue。

## 选择后端

完整仓库中运行：

```bash
# 本地转录，明确覆盖可能存在的后端环境变量
python3 podcast-transcribe/scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider local

# 已通过安全环境配置 DASHSCOPE_API_KEY 后：会把音频内联上传给阿里云百炼
python3 podcast-transcribe/scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider dashscope --state-dir "$HOME/.local/state/chubbyskills/podcast"
```

云端命令会把音频内容发送至所选服务并可能计费。密钥配置在本机安全环境或密钥设施中，不放进命令参数、原稿或版本库。

| 设置 | 环境变量 |
|---|---|
| 默认后端 | `PODCAST_TRANSCRIBE_PROVIDER`：`local`、`dashscope`、`groq`；未设置时为 `local` |
| DashScope 凭据 | `DASHSCOPE_API_KEY` |
| DashScope API 地址 | `DASHSCOPE_BASE_URL`；默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`，替换时需使用可信 HTTPS 端点 |
| Groq 凭据 | `GROQ_API_KEY` |
| Groq API 地址 | `GROQ_BASE_URL`；默认 `https://api.groq.com/openai/v1`，替换时需使用可信 HTTPS 端点 |
| 持久任务目录 | `CHUBBY_PODCAST_STATE_DIR`；否则使用 `XDG_STATE_HOME/chubbyskills/podcast`，未设 XDG 时为 `~/.local/state/chubbyskills/podcast` |

命令行 `--provider` 优先于环境变量。批量入口始终把最终后端传给子进程，显式 `local` 不会被子进程的环境默认值改成云端。

## 参数与产物

| 参数 | 行为 |
|---|---|
| `--model` | 本地默认 `SenseVoiceSmall`（仅用于元数据记录）；DashScope 默认 `qwen3-asr-flash`；Groq 默认 `whisper-large-v3-turbo` |
| `--language` | 默认 `zh`，按所选模型接受的语言代码设置；DashScope 通过 `asr_options.language` 传给模型；Groq 按 ISO-639-1 代码透传；留空或 `auto` 则不指定语种 |
| `--cloud-timeout` | 本次云端等待的时间上限，默认 1800 秒 |
| `--poll-interval` | 轮询间隔，默认 3 秒；两个云端后端都是同步接口，正常路径不会轮询 |
| `--state-dir` | 保存任务与恢复信息的本地目录，优先于环境变量 |
| `--base-url` | 显式指定可信 HTTPS API 地址；统一运行记录会保留它供重试使用 |
| `--resubmit` | 明确创建新的云端任务，可能再次计费；普通恢复不要使用 |

两个云端后端都是同步接口，一次请求直接返回转录结果：

- **DashScope `qwen3-asr-flash`**：客户端把音频 base64 内联进 `chat/completions` 请求，响应的 `choices[0].message.content` 就是全文转录。输入限制为 **base64 编码后不超过 10MB、录音不超过 5 分钟**；本客户端在原始文件超过 7 MiB 时直接拒绝。
- **Groq `whisper-large-v3-turbo`**：客户端以 multipart/form-data 上传文件到 `audio/transcriptions`，`response_format=verbose_json` 返回全文和分段时间戳（产物附「时间戳参考」）。免费层单文件上限 25MB（dev tier 100MB）——**达到 25 MiB 的音频会自动分片**：ffmpeg 切成 20 分钟一段（16kHz mono 64kbps MP3，每段约 9.6MB，留足余量），逐段提交后按顺序拼接全文，分段时间戳自动累加前序偏移。分片进度逐段落盘，进程中断后重跑同一命令从断点续传，不重复提交已完成分片；遇到 HTTP 429 按 Retry-After 或指数退避等待（受 `--cloud-timeout` 总时限约束）。免费层还有请求速率限制，批量场景请控制频率。长音频分片需要本机 ffmpeg/ffprobe。

DashScope 超限会在提交前拒绝并提示改用本地 SenseVoice-Small（`--provider local`）；Groq 则自动分片处理长音频，不支持的音频容器先调用本机 `ffmpeg` 转为 MP3 再提交。仅使用云端转录不需要安装 funasr 本地依赖；需要容器转换或分片时仍需 `ffmpeg`。

成功后输出带来源和转录后端元数据的 Markdown，标准输出最后一行为文件路径，供统一入库流程接收。完整正文始终保留；Groq 返回的分段时间戳作为附录保留，DashScope 不返回时间戳，产物不编造时间轴。

播客 URL 和 RSS 自动下载只接受公网 HTTP(S) 直连地址，禁用重定向、代理和本地/私网地址。需要跳转或代理的资源，请先自行下载音频，再明确传入本地文件路径。此限制同样适用于本地转录后端的自动下载。

## 失败后恢复原任务

对相同音频、provider、模型、语言和服务地址，保留同一个状态目录，重新执行原命令：

| 已记录状态 | 再次执行的行为 |
|---|---|
| 已完成 | 使用保存结果重新导出 Markdown，不再发起请求 |
| 提交结果不明确（进程中断、响应丢失或响应格式异常） | 停止自动提交，保留记录并提示检查服务端是否已计费 |
| 服务端报告失败 | 保留失败状态，不自动创建新任务 |

只有确认需要新任务时才加 `--resubmit`。删除状态目录、改变音频或改用其他 provider、模型、语言、服务地址，都可能失去原任务的复用条件；不能把这些操作当作免费的重试。状态目录保存音频摘要、处理配置和转录内容，不保存 API key、原始音频路径或音频 URL；仍应按原始音频的隐私要求保存。

客户端停止等待不等于服务端未处理请求，也不表示没有产生费用。提交请求不做盲目重试；认证请求拒绝不安全重定向，API key 不应随着跨服务跳转传播。

## 批量与统一入库

RSS 批量沿用同一接口：

```bash
python3 podcast-transcribe/scripts/batch_transcribe.py \
  --rss-url "替换为实际 RSS 地址" --output ./output --count 3 \
  --provider dashscope --cloud-timeout 1800 \
  --state-dir "$HOME/.local/state/chubbyskills/podcast"
```

配置知识库后，也可以通过统一入口保存产物和更新索引：

```bash
python3 tools/chubby.py ingest "/你的音频目录/episode.mp3" \
  --skill podcast --provider dashscope --no-enrich
python3 tools/chubby.py search "转录中的关键词"
```

统一入口会在云端子进程启动前记录 `running` 状态；进程中断后可用 `retry` 恢复。统一入口的 `--refresh` 控制本地产物重新生成，云端 `--resubmit` 控制新建服务任务。`--resubmit` 是一次性动作，不会被 `retry` 继承；显式切换 provider 时，旧模型和 API 地址会清除，采用新后端默认值或本次显式参数。

当前只承诺本仓库已覆盖的本地行为（请求构造、状态恢复与错误处理均有离线测试）。服务可用性、账号授权、真实音频兼容性、转录质量和最终费用，需要独立的真实服务验证；请在实际使用前自行确认计费与配额。
