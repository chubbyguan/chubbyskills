# v0.11.0 发布与宣发文案（2026-08-19）

> 使用说明：GitHub Release 粘贴「一、Release Notes」到 https://github.com/chubbyguan/chubbyskills/releases/new
> （Tag 填 `v0.11.0`，标题填 `v0.11.0 — 公共模块重构 + 依赖体检 + 叙事升级`），其余渠道按需复制。

---

## 一、GitHub Release Notes（正式版）

**标题**：v0.11.0 — 公共模块重构 + 依赖体检 + README 叙事升级

**正文**：

> 从"一个人的好工具"走向"中文 Agent 内容采集的事实标准"——这一版先把地基打牢。

### 🧱 工程重构（用户不可见，但决定了项目能走多远）

- **新增 `chubby_common/` 公共模块**：tiktok / weibo / zhihu 三个转录脚本从 180 行瘦身到 70 行，全仓库消除 ~400 行复制粘贴；yt-dlp 封装（重试 + 超时 + 依赖体检）、SenseVoice 转录、VTT 字幕解析、Markdown 生成全部统一
- **消除双事实来源**：平台路由表现在从 `platforms/*.yaml` 自动生成——加一个新平台只需写一份定义文件

### 👍 用户体验改进

- **友好依赖提示**：缺 yt-dlp / ffmpeg / funasr 时提示 `bash setup.sh video` 安装命令，不再裸 traceback
- **LLM 输出容错**：enrich / 爆款拆解 / 学习笔记的 JSON 解析与数值转换全面加防御，模型抽风不再崩脚本
- **抖音下载器加固**：页面结构变化给出可读报错（提示风控/链接失效），独立运行不再泄漏临时文件
- **播客 RSS 解析修复**：缺 title / pubDate / duration 标签不再崩溃

### 📖 叙事升级

- README 首屏重写：定位声明「中文 Agent 内容采集的事实标准」+ 生态对比表（vs feedgrab / RSSHub / 商业工具）+ 完整版见 [docs/comparison.md](https://github.com/chubbyguan/chubbyskills/blob/main/docs/comparison.md)

### ✅ 质量

- 56 个单元测试全绿（新增 16 个公共模块测试），CI 增加 7 个脚本入口检查

**感谢**：@kriptoburak 的 Xquik fallback 贡献（v0.10.1 期间合并）。

---

## 二、X / Twitter 文案（英文，1-2 条）

**主帖**：

> Your feed forgets. Your knowledge base remembers. Your agents use it.
>
> Chubby Skills v0.11 is out — the de facto standard for Chinese content ingestion into AI agents:
> 📥 10 Chinese platforms (WeChat, Douyin, XHS, Bilibili, Zhihu, Weibo…)
> 🎬 subtitle-first transcription, zero GPU
> 🧠 unified Markdown → searchable vault → MCP for any agent
> 🔒 fully local, zero API cost
>
> We also killed ~400 lines of copy-paste with a shared module, and added friendly dependency checks.
> github.com/chubbyguan/chubbyskills

**跟进帖（可选，技术向）**：

> One design decision worth stealing: every ingest skill writes to one output contract (schema v1 frontmatter), so vault indexing, semantic search, and MCP retrieval all work without per-platform code. Platform adapter = 4 files + 1 yaml.

---

## 三、即刻文案（中文，社区向）

> 我的 skill 仓库 v0.11 发了，这版没加新平台，但把地基打了一遍：
>
> - 三个转录脚本原来有 ~400 行是一模一样的复制粘贴（tiktok/weibo/zhihu 就差个 UA），抽成了公共模块，现在修一个 bug 改一处
> - 缺 yt-dlp/ffmpeg 不再裸报错，会告诉你跑哪条安装命令
> - LLM 输出加了容错，DeepSeek 抽风不再崩脚本
>
> 顺便把 README 首屏重写了：定位从"14 个 skill"改成"中文 Agent 内容采集的事实标准"——跟 feedgrab、RSSHub、商业工具做了个可证伪的对比表。
>
> 我的判断：这个生态已经 140 万+ 技能包，垂直领域（中文内容→知识库）还没有事实标准，这个位置值得占。
>
> 🔗 github.com/chubbyguan/chubbyskills
> #AgentSkills #知识库 #内容创作

---

## 四、小红书文案（中文，个人/教程向）

**标题候选**：
1. 我把 3 个脚本从 180 行瘦到 70 行，只做对了一件事
2. 内容创作者的素材库，终于接上了 AI
3. 我的第二大脑管道 v0.11：AI 开始"用"我的知识库了

**正文**（以标题 1 为例）：

> 做内容的人都会囤素材，但囤了不用 = 没有。
> 我的解决方案是一套开源 skill 管道（已 500+ star）：抖音/B站/小红书/公众号的链接丢进去，自动变成统一格式的 Markdown 进 Obsidian，AI Agent 能直接检索调用。
>
> 这版没加新功能，做的是"把地基打牢"：
> 🔧 3 个平台脚本原来有 400 行重复代码，抽成公共模块——以后修 bug 只改一处
> ⚡ 缺依赖时给安装提示，不再看不懂的报错
> 🛡️ AI 输出加容错，模型抽风不再崩
>
> 对我个人最大的意义：AI 终于开始"用"我的知识库，而不只是"存"进去。
>
> 开源免费，完全本地，零 API 费用。仓库：chubbyguan/chubbyskills（GitHub）
>
> #内容创作 #第二大脑 #AI工具 #知识管理 #Obsidian

---

## 五、发布检查清单

- [ ] GitHub Release 发布（Tag: `v0.11.0`，标题见上）
- [ ] X 主帖发布（发布后 2-4 小时发跟进帖）
- [ ] 即刻同步
- [ ] 小红书同步（可选配图：README 首屏截图）
- [ ] README 已指向 v0.11.0（✅ 已完成）
- [ ] 记录发布数据（stars 前后对比、互动数），供下月复盘
