---
name: podcast-transcribe
description: >
  播客/小宇宙 → 下载 → 转录 → 存为 Markdown 的完整工作流。
  支持 RSS 批量下载、单集链接转录。
metadata:
  category: "media"
  triggers: "[\"用户发送小宇宙/播客链接\", \"帮我转录这个播客\", \"下载播客\", \"批量转录播客\"]"
  version: "1.1.0"
  tags: "[\"media\", \"audio\", \"podcast\", \"transcription\", \"xiaoyuzhou\"]"
---

# 播客转录 Skill

将播客音频下载并转录为 Markdown。支持小宇宙、喜马拉雅、直接音频地址、本地音频和 RSS 批量流程。

默认在本地使用 SenseVoice-Small（与视频类技能共用的 `chubby_common/funasr.py` 封装）。可选云端后端为阿里云百炼 DashScope 的 `qwen3-asr-flash` 和 Groq 的 `whisper-large-v3-turbo`，用户明确选择后才启用；音频会发送至云端并可能计费。

## 环境要求

以下命令在本 skill 目录运行，建议使用 Python 3.11 或更新版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
```

本地模型首次使用时需要下载。仅使用云端后端不需要 funasr 本地依赖；不支持的音频容器转换仍可能需要 `ffmpeg`。云端密钥通过安全环境配置，不能写入命令参数、转录稿或版本库。

## 单集与批量

```bash
python3 scripts/transcribe.py "https://www.xiaoyuzhoufm.com/episode/xxxxx" ./output \
  --provider local
python3 scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider local --language zh
python3 scripts/batch_transcribe.py --rss-url "替换为实际 RSS 地址" \
  --output ./output --count 10 --provider local
```

将示例地址替换为实际来源。单集页面会尝试提取音频链接，提取失败时改用直接音频地址或本地文件。标准输出最后一行是成功生成的 Markdown 路径。

自动下载仅接受公网 HTTP(S) 直连地址，禁用代理和重定向，拒绝本地/私网地址。需要跳转或代理的来源，请先自行下载音频，再传入本地文件路径。

## 本地模型选择：SenseVoice-Small vs Qwen3-ASR-0.6B

`--provider local` 支持两个本地模型：`SenseVoiceSmall`（默认）和 `qwen3-asr-0.6b`：

```bash
python3 scripts/transcribe.py "/你的音频目录/episode.mp3" ./output --provider local
python3 scripts/transcribe.py "/你的音频目录/episode.mp3" ./output --provider local --model qwen3-asr-0.6b
```

`qwen3-asr-0.6b` 是可选重依赖，不在默认安装内，需自行 `pip install qwen-asr transformers torch`。

以下对比数据来自 2026-10 在 MacBook Pro（Apple M3 Pro，纯 CPU）上对 5 分钟中文播客的实测：

| | SenseVoice-Small（默认） | Qwen3-ASR-0.6B（可选） |
|---|---|---|
| 速度 | RTF 0.11（5 分钟音频约 33 秒） | RTF 0.80（约 4 分钟，慢约 7 倍） |
| 专有名词 | 一般（"岩茶"误作"盐茶"，人名前后不一致） | 更稳（"岩茶"、人名识别一致） |
| 主要风险 | 输出混入情感标签，正式文稿需清洗 | 有幻觉式改写风险（"黄金加工厂"→"皇帝家族"）；无 ITN，数字输出为全文字 |
| 长音频 | VAD 自动分段，稳定 | 整段进模型；本后端已把 `max_new_tokens` 调到 4096 避免截断 |
| 适用场景 | CPU 默认选择，长播客友好 | GPU 机器，或对专名/人名准确性敏感的内容 |

两者质量互有胜负、没有代差。CPU 场景请保持默认 SenseVoice-Small；有 GPU 或专名敏感时再选 Qwen3-ASR-0.6B。

## 可选云端转录

| 后端 | 凭据环境变量 | 默认模型 |
|---|---|---|
| `local` | 无 | `SenseVoiceSmall`（仅用于元数据记录） |
| `dashscope` | `DASHSCOPE_API_KEY` | `qwen3-asr-flash` |
| `groq` | `GROQ_API_KEY` | `whisper-large-v3-turbo` |

配置 `DASHSCOPE_API_KEY` 或 `GROQ_API_KEY` 后：

```bash
python3 scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider dashscope --cloud-timeout 1800 \
  --state-dir "$HOME/.local/state/chubbyskills/podcast"
python3 scripts/transcribe.py "/你的音频目录/episode.mp3" ./output \
  --provider groq --cloud-timeout 1800 \
  --state-dir "$HOME/.local/state/chubbyskills/podcast"
```

`--provider` 优先于 `PODCAST_TRANSCRIBE_PROVIDER`，都未指定时使用 `local`。批量入口支持同样的 provider、模型、语言、等待和状态目录参数，并把最终选项显式传给单集进程。

两个云端后端都是同步接口。DashScope 限制为**编码后不超过 10MB、时长不超过 5 分钟**（客户端在原始文件超过 7 MiB 时拒绝并提示改用本地 SenseVoice）。Groq 免费层单文件上限 25MB，**达到上限的长音频会自动分片**：ffmpeg 切成 20 分钟一段（约 9.6MB/段），逐段转录后按顺序拼接，时间戳自动累加偏移；分片进度逐段落盘，中断后重跑同一命令断点续传，不重复提交已完成分片；遇 429 按 Retry-After/指数退避等待。Groq 返回的分段时间戳会作为附录保留。分片和容器转换需要本机 `ffmpeg`。

## 云端任务恢复

默认状态目录为 `~/.local/state/chubbyskills/podcast`；设置了 `XDG_STATE_HOME` 时使用其中的 `chubbyskills/podcast`。还可用 `CHUBBY_PODCAST_STATE_DIR` 或 `--state-dir` 指定。目录包含任务与转录内容，应按音频内容的隐私要求保存。

相同音频、provider、模型、语言和服务地址再次运行时，已有任务继续查询；已完成结果可以重新导出。提交结果不明确或服务端报告失败时，不自动重新提交。普通网络重试保留状态目录并重跑原命令即可。

`--resubmit` 明确创建新任务，可能重复计费。不要用它解决单纯的轮询超时。删除状态目录或改变输入配置也可能失去复用条件。客户端超时不等于服务端取消，也不代表没有计费。

完整仓库使用说明、统一入库和验证范围见[云端转录说明](https://github.com/chubbyguan/chubbyskills/blob/main/docs/cloud-transcription.md)。

## 产物与限制

产物为带 frontmatter、来源和转录后端标记的 Markdown。后端返回可用分段时保留时间戳；没有时间信息时不编造时间轴。

- 本地 SenseVoice-Small 只输出纯文本全文，不生成逐段时间戳（段数记为 1）。
- 本地 CPU 推理耗时受音频长度和机器配置影响。
- 转录可能有专有名词、数字或断句错误，引用前核对原始音频。
- 云端真实可用性、账号权限、音频兼容性和费用尚需独立验收。
- 本 skill 不提供通用说话人分离保证。

## 贡献与参考

可选云端转录需求最初来自 [binyangzhu000-sudo 的 PR #3](https://github.com/chubbyguan/chubbyskills/pull/3) 和 [Anil-matcha 的 PR #5](https://github.com/chubbyguan/chubbyskills/pull/5)（Atlas / MuAPI 实验后端，现已被 DashScope 后端取代，归属保留）。

- [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice)
- [阿里云百炼 Qwen-ASR API 参考](https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference)
- [Groq Speech to Text 文档](https://console.groq.com/docs/speech-to-text)

## 合规声明

请遵守来源平台条款并尊重内容版权，控制请求频率。云端处理前确认自己有权向所选服务提交音频；下载和转录不会改变原内容的版权归属。
