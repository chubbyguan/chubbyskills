# 安装到 Agent

先获取完整仓库，再用安装器生成可以独立移动的 Skill 目录。安装器只复制源码及仓库内的公共模块，不安装 Python 包，也不启动或配置 Agent。

```bash
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/install_skill.py --list
python3 tools/install_skill.py bilibili-transcribe --dest ~/.codex/skills
```

`--dest` 是你使用的 Agent 的 skills 根目录，请按客户端实际配置填写。上例会生成 `~/.codex/skills/bilibili-transcribe/`。多个技能可以一次安装：

```bash
python3 tools/install_skill.py x-ingest content-enrich --dest /path/to/agent/skills
python3 tools/install_skill.py --all --dest /path/to/agent/skills
```

同名目录已经存在时，安装器会在写入前退出，不覆盖或合并现有技能。更新时先安装到一个新的临时目录，检查差异并保留自己的修改，再按 Agent 的管理方式替换。

## 为什么需要安装器

9 个技能使用 `chubby_common`：6 个视频转录技能、`content-enrich`、`learning-notes-automation` 和小红书的爆款分析脚本。知识库技能的 MCP、索引和归档还依赖 `tools/vault_index.py` 与 `tools/vault_curator.py`。只下载 GitHub 上的单个原始技能目录会漏掉这些依赖。

安装器将公共源码放进每个技能自己的目录，并保留版本与文件清单 `installation.json`。安装完成后，可以单独复制整个技能目录到其他路径，无需原始仓库，也不需要在 Agent 的根目录维护一份跨技能共享模块。Python 包和系统命令仍需要在实际运行环境中安装。

X、公众号、播客、行业雷达的 Python 脚本不依赖仓库公共模块。学习笔记工作流中调用其他转录技能属于可选组合；需要从链接开始转录时，另装对应转录技能。

## 按能力安装运行依赖

```bash
bash setup.sh light                   # 图文和文本处理的轻量能力
bash setup.sh bilibili-transcribe     # 与 video 档相同，安装音频转录依赖
bash setup.sh video                   # 视频音频转录依赖
bash setup.sh podcast-transcribe      # 播客依赖
bash setup.sh wechat-article-ingest    # 公众号与 PDF 处理依赖
bash setup.sh doctor                  # 查看当前环境
```

`setup.sh` 接受全部 14 个完整技能目录名及原有简写。`x-ingest` 和 `xiaohongshu-ingest` 默认保持图文轻量能力；需要视频转录时明确运行 `bash setup.sh video`。B站与 YouTube 仅走字幕路径时，可以只安装 `yt-dlp`，不必安装音频转录模型。`content-enrich`、学习笔记与爆款拆解还需按需设置 `DEEPSEEK_API_KEY`。

公众号、抖音和在线播客使用 `curl`；安装器只在所选能力需要时检查它。`setup.sh` 不会把技能注册到 Agent，独立目录安装仍由 `tools/install_skill.py` 完成。

知识库的 MCP 服务另需官方 MCP SDK：

```bash
python3 -m pip install -r /path/to/agent/skills/knowledge-base-management/requirements-mcp.txt
VAULT_DIR=/path/to/vault python3 /path/to/agent/skills/knowledge-base-management/scripts/mcp_server.py
```

独立安装的知识库也包含 `tools/vault_index.py` 和 `tools/vault_curator.py`；在该技能目录运行文档中的 `python3 tools/...` 命令即可。

## 安装验收范围

测试会把全部 14 个安装产物分别移动到独立目录，用 Python 隔离模式导入每个脚本，并实际执行 X / 小红书的手动采集与知识库检索。这个检查验证分发与本地依赖完整性；平台在线采集与音频转录仍须分别验收。
