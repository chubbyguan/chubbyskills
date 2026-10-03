# chubbyskills 推广 / 聚合榜提交指南

> **维护提示（2026-10-03）：** 文案已对齐当前 v0.13.1 + Unreleased 状态（14 个 Skills、SenseVoice-Small 本地转录、DashScope/Groq 云后端、订阅调度 P0+P1）。仓库当前约 1162 stars / 144 forks。对外提交前仍需再核对一次仓库最新版本与各平台最新投稿规则；云转录后端（dashscope / groq）真实调用**尚未完成验收**，外发文案不要宣称已验收。

> 照着这份操作即可。仓库：https://github.com/chubbyguan/chubbyskills （star 所在）
> 镜像：https://gitee.com/chubbyguan/chubbyskills

---

## 一、提交到 awesome-agent-skills（最重要，纯 GitHub PR）

### 操作步骤
1. 打开 https://github.com/heilcheng/awesome-agent-skills ，点右上角 **Fork**
2. 在你 fork 的仓库里打开 `README.md`，点编辑（铅笔图标）
3. 找到 **Community Skills** 区下的 `Productivity and Collaboration` 分类，在列表里加上下面这一行
4. 页面底部填 commit 信息 → **Propose changes**
5. 点 **Create pull request**，标题和正文用下面准备好的

### 要加的那一行（直接复制）
```markdown
- [chubbyguan/chubbyskills](https://github.com/chubbyguan/chubbyskills) - 14 skills for ingesting Chinese content (Douyin, Bilibili, Xiaohongshu, WeChat, X/Twitter, podcasts) into a personal knowledge base — auto image/video routing, subtitle-first transcription, RSS/YouTube subscription scheduling, and a knowledge-base MCP server
```

### PR 标题（复制）
```
Add chubbyskills: Chinese content-ingestion skills + knowledge-base MCP server
```

### PR 正文（复制）
```markdown
Adds **chubbyskills** — a collection of 14 skills focused on ingesting Chinese-platform content into a personal knowledge base, an area currently underrepresented in this list.

- Sources: Douyin, Bilibili, TikTok, Weibo, Zhihu, YouTube, podcasts, WeChat articles, Xiaohongshu, X/Twitter (long-form articles via logged-in cookies)
- Auto-routes image vs. video notes (images saved locally, videos transcribed)
- Subtitle-first transcription (no GPU needed when captions exist); local SenseVoice-Small transcription with an opt-in Qwen3-ASR-0.6B model; optional DashScope / Groq cloud backends (newly added, live transcription not yet acceptance-verified)
- Subscription scheduling for public RSS / Atom / JSON feeds and YouTube channels, with bring-your-own provider support (RSSHub / RSS-Bridge)
- Unified frontmatter + a knowledge-base MCP server so any MCP agent can query the vault
- Each skill is self-contained and independently installable; MIT licensed

Repo: https://github.com/chubbyguan/chubbyskills
```

> 提交前快速对照它的 CONTRIBUTING：每个 skill 有 `SKILL.md`、单文件 <500 行、有示例、标注限制——你这些都满足。

---

## 二、通用「一句话简介」（到处都能用）

**英文**（国际榜单 / 英文场合）：
```
chubbyskills — 14 Agent Skills that pull Chinese content (Douyin, Bilibili, Xiaohongshu, WeChat, X) into your personal knowledge base: image/video auto-routing, subtitle-first transcription, RSS/YouTube subscription scheduling, and a knowledge-base MCP server.
```

**中文**（国内平台 / 即刻 / X 中文）：
```
chubbyskills——14 个把中文全渠道内容（抖音/B站/小红书/公众号/X 等）采集进个人知识库的 Agent Skill：图文存图、视频转文字稿、字幕优先免 GPU、本地 SenseVoice-Small 转录，还支持 RSS/YouTube 频道订阅调度，外加一个知识库 MCP server。
```

---

## 三、ClawHub / SkillsMP 等聚合平台

这两个不是固定的 GitHub PR 流程，步骤通用：
1. 打开平台官网，找 **Submit / Add Skill / Contribute** 入口（通常在导航或页脚）
2. 多数是「填仓库 URL + 名称 + 描述」的表单，或要求按模板提 PR
3. **URL** 填 `https://github.com/chubbyguan/chubbyskills`，**描述**用上面第二节的中/英一句话
4. 分类选 **Productivity / Knowledge / Content** 这类最接近的

> 如果它们要求「单个 skill」粒度而非整个仓库，优先登记最有特色的 3 个：
> `xiaohongshu-ingest`、`x-ingest`、`knowledge-base-management`（带 MCP 那个）。

---

## 四、顺手能提升转化的两件事（可选）

1. **GitHub 仓库 About / Topics**：在仓库主页右侧 About 里，描述填上面英文一句话，Topics 加：
   ```
   agent-skills  claude  knowledge-base  obsidian  mcp  transcription  chinese
   ```
   榜单和搜索都靠 topics 发现你。

2. **置顶一条介绍推文 / 即刻**：用第二节中文那句 + 一张「14 个 skill 四层管线（采集 / 加工 / 管理 / 应用）」的图，挂到你 X / 即刻主页。可以提当前约 1100+ stars，但数字会变，发之前看一眼仓库首页。

---

## 提交清单（做完打勾）

- [ ] awesome-agent-skills 提了 PR
- [ ] GitHub 仓库 About + Topics 填好
- [ ] ClawHub 登记
- [ ] SkillsMP 登记
- [ ] X / 即刻 发了介绍贴
