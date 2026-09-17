# 可选云端播客转录

播客默认使用本地 `faster-whisper`。`atlas` 和 `muapi` 是需要主动选择的 **experimental** 后端：本版本验证离线请求生命周期、错误处理和产物格式，尚未完成真实付费服务的端到端验收。

两种后端共享 provider 入口和持久化任务恢复。需求分别来自 [PR #3](https://github.com/chubbyguan/chubbyskills/pull/3)（[binyangzhu000-sudo](https://github.com/binyangzhu000-sudo)）和 [PR #5](https://github.com/chubbyguan/chubbyskills/pull/5)（[Anil-matcha](https://github.com/Anil-matcha)）；本项目在共同接口上重新实现，未原样合并旧 PR。

## 选择后端

完整仓库中运行：

```bash
# 本地转录，明确覆盖可能存在的后端环境变量
python3 podcast-transcribe/scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider local

# 已通过安全环境配置 ATLAS_API_KEY 后：会把音频提交给 Atlas Cloud
python3 podcast-transcribe/scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider atlas --state-dir "$HOME/.local/state/chubbyskills/podcast"

# 已通过安全环境配置 MUAPI_API_KEY 后：会上传音频并提交 MuAPI 转录任务
python3 podcast-transcribe/scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider muapi --state-dir "$HOME/.local/state/chubbyskills/podcast"
```

云端命令会把音频内容发送至所选服务并可能计费。密钥配置在本机安全环境或密钥设施中，不放进命令参数、原稿或版本库。

| 设置 | 环境变量 |
|---|---|
| 默认后端 | `PODCAST_TRANSCRIBE_PROVIDER`：`local`、`atlas`、`muapi`；未设置时为 `local` |
| Atlas 凭据 | `ATLAS_API_KEY`，兼容 `ATLAS_CLOUD_API_KEY` |
| Atlas API 地址 | `ATLAS_BASE_URL`；替换时需使用可信 HTTPS 端点 |
| MuAPI 凭据 | `MUAPI_API_KEY`，兼容 `MU_API_KEY` |
| MuAPI API 地址 | `MUAPI_BASE_URL`；替换时需使用可信 HTTPS 端点 |
| 持久任务目录 | `CHUBBY_PODCAST_STATE_DIR`；否则使用 `XDG_STATE_HOME/chubbyskills/podcast`，未设 XDG 时为 `~/.local/state/chubbyskills/podcast` |

命令行 `--provider` 优先于环境变量。批量入口始终把最终后端传给子进程，显式 `local` 不会被子进程的环境默认值改成云端。

## 参数与产物

| 参数 | 行为 |
|---|---|
| `--model` | 本地默认 `small`；Atlas 默认 `bytedance/seed-asr-2.0`；MuAPI 默认 `openai-whisper` |
| `--language` | 默认 `zh`，按所选模型接受的语言代码设置 |
| `--cloud-timeout` | 本次云端等待的时间上限，默认 1800 秒 |
| `--poll-interval` | 初始轮询间隔，默认 3 秒 |
| `--state-dir` | 保存任务与恢复信息的本地目录，优先于环境变量 |
| `--base-url` | 显式指定可信 HTTPS API 地址；统一运行记录会保留它供重试使用 |
| `--resubmit` | 明确创建新的云端任务，可能再次计费；普通恢复不要使用 |

MuAPI 音频必须小于 25 MiB；超限在上传前拒绝。Atlas 客户端为内联上传设置 100 MiB 上限，对不支持的音频容器先调用本机 `ffmpeg` 转为 MP3；这个客户端上限不是服务商容量保证。仅使用云端转录不需要安装 `faster-whisper`；需要容器转换时仍需 `ffmpeg`。

成功后输出带来源和转录后端元数据的 Markdown，标准输出最后一行为文件路径，供统一入库流程接收。完整正文始终保留；后端返回的有效时间戳作为附录，不补造时间轴，也不因分段不完整而丢弃正文。

播客 URL 和 RSS 自动下载只接受公网 HTTP(S) 直连地址，禁用重定向、代理和本地/私网地址。需要跳转或代理的资源，请先自行下载音频，再明确传入本地文件路径。此限制同样适用于本地转录后端的自动下载。

## 失败后恢复原任务

对相同音频、provider、模型、语言和服务地址，保留同一个状态目录，重新执行原命令：

| 已记录状态 | 再次执行的行为 |
|---|---|
| 已有任务 ID，仍在处理中或查询超时 | 继续查询同一任务，不重新提交 |
| 已完成 | 使用保存结果重新导出 Markdown |
| 提交结果不明确，无法确认是否接受 | 停止自动提交，保留记录并提示检查服务端任务 |
| 服务端报告失败 | 保留失败状态，不自动创建新任务 |

只有确认需要新任务时才加 `--resubmit`。删除状态目录、改变音频或改用其他 provider、模型、语言、服务地址，都可能失去原任务的复用条件；不能把这些操作当作免费的重试。状态目录保存音频摘要、处理配置、任务 ID 和转录内容，不保存 API key、原始音频路径或音频 URL；仍应按原始音频的隐私要求保存。

客户端停止等待不等于服务端取消任务，也不表示没有产生费用。提交请求不做盲目重试；认证请求拒绝不安全重定向，API key 不应随着跨服务跳转传播。

## 批量与统一入库

RSS 批量沿用同一接口：

```bash
python3 podcast-transcribe/scripts/batch_transcribe.py \
  --rss-url "替换为实际 RSS 地址" --output ./output --count 3 \
  --provider atlas --cloud-timeout 1800 \
  --state-dir "$HOME/.local/state/chubbyskills/podcast"
```

配置知识库后，也可以通过统一入口保存产物和更新索引：

```bash
python3 tools/chubby.py ingest "/你的音频目录/episode.mp3" \
  --skill podcast --provider atlas --no-enrich
python3 tools/chubby.py search "转录中的关键词"
```

统一入口的 `--refresh` 控制本地产物重新生成，云端 `--resubmit` 控制新建服务任务。恢复超时任务用原参数重新运行或 `retry`，不要为了继续查询而增加 `--resubmit`。

统一入口会在云端子进程启动前记录 `running` 状态；进程中断后可用 `retry` 恢复。新任务的失败或运行状态会阻止复用旧的成功产物。重试保留原服务配置，但不会继承一次性的 `--resubmit`；显式切换 provider 时，旧模型和 API 地址会清除，采用新后端默认值或本次显式参数。

当前实验状态只承诺本仓库已覆盖的本地行为。服务可用性、账号授权、真实音频兼容性、转录质量和最终费用，需要独立的真实服务记录；本版没有为验证发起付费转录。
