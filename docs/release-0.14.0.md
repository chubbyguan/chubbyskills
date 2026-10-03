# v0.14.0 — 转录栈统一与云端可选后端

这次迭代把播客转录栈收敛到与视频技能一致的本地底座，同时把此前实验性的云后端换成可维护的两条线路，并解决了长音频的免费档限制。

- **本地统一 SenseVoice-Small**：播客本地转录改走共享的 `chubby_common/funasr.py` 封装，与视频技能同栈；faster-whisper（及其 `av` 版本锁定）已移除。SenseVoice 返回整段纯文本，播客转录稿不再带逐段时间戳。
- **可选本地 Qwen3-ASR-0.6B**：`--provider local --model qwen3-asr-0.6b` 启用新 `local_qwen_asr.py` 后端（官方 `qwen-asr` 包，transformers CPU float32），本地模型名做了白名单校验，`qwen-asr` 为可选依赖、不在默认安装内。实测（M3 Pro CPU，2026-10）：SenseVoice RTF 0.11 vs Qwen RTF 0.80——Qwen 慢约 7 倍，专有名词更稳，但可能幻觉且没有 ITN，适合对准确率敏感、不在乎速度的场景。
- **云后端换代**：实验性的 Atlas Cloud / MuAPI 已移除，换成阿里云百炼 DashScope `qwen3-asr-flash`（`--provider dashscope`）和 Groq `whisper-large-v3-turbo`（`--provider groq`，保留 verbose_json 时间戳附录）。DashScope 同步响应被归一化进既有的可续传状态机；超过服务限制的音频在提交前拒绝并指向本地 SenseVoice。**如实说明：两条云线路都尚未完成真实账号在线验收**，欢迎有条件的用户反馈。
- **Groq 长音频自动分片**：达到 25 MB 免费档上限的文件不再直接拒绝，而是用 ffmpeg 自动切成 20 分钟 / 16 kHz / 64 kbps MP3 分段（约 9.6 MB），按序提交；每段进度落盘（digest + 时长写进既有状态文件，兼容旧的单文件状态），中断后已完成的段落不会重传；文本按序拼接、时间戳按累计时长平移；HTTP 429 按 Retry-After / 指数退避等待。
- **测试依赖修复**：`pyyaml` 纳入测试依赖，跑测试不再需要手动 `--with pyyaml`。

## 安装与使用

```bash
git clone --branch v0.14.0 https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 -m pip install -e .
chubby init --vault "$HOME/Documents/creator-vault"
chubby import "/你的文档目录/report.md" --no-enrich
chubby search "报告中的关键词"
```

安装包 `chubbyskills-0.14.0-skills.tar.gz` 包含 14 个可独立移动的技能目录，Python 和系统依赖需另外安装。

## 社区贡献

- 本版的云转录需求来自 [PR #3](https://github.com/chubbyguan/chubbyskills/pull/3) 与 [PR #5](https://github.com/chubbyguan/chubbyskills/pull/5) 的原始请求，归属保留；它们引入的 Atlas / MuAPI 后端在本版已被 DashScope / Groq 取代。

## 验证范围

本地 277 项测试通过、1 项跳过（含 Groq 分片续传、DashScope 状态归一化、Qwen3-ASR 本地后端与模型白名单的新增用例），测试命令不再需要额外声明 pyyaml。Quickstart 体检、示例输出 schema v1 校验、Ruff（E/F/W）与 `git diff --check` 均通过。

发布包重新解压后验证 14 个技能目录脚本的隔离导入。DashScope 与 Groq 云后端只有 mock 层与协议层测试覆盖，**未完成真实账号在线验收**；调用失败时会在提交前或状态机中给出可读错误，不会静默出错。

## 资产校验

`chubbyskills-0.14.0-skills.tar.gz` SHA-256: `b54f1318fd5aaeffa55dfecc8f64b5ea2547521173af55ea0b5adefe32c41b45`（14 个技能目录，解压后 25 个脚本隔离导入验证通过）
