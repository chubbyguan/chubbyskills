# 复刻验收清单：从零到「每天自动进库」

这份清单的用途不是教你用命令，而是回答一个问题：**我是不是真的把这套管线跑起来了？**

作者本机跑的是「多个信息源 → 每小时自动发现 → 转录/保存 → 进知识库 → 可搜索 → 每天出简报」。下面把这条链路拆成可逐条验证的步骤，每步都给出**预期观察**和**不对时该看哪里**。全部走通，才算复刻成功。

> 想只试一下效果，看 README 的 60 秒路径就够了；这份清单针对「我要长期用」。

## 0. 环境

```bash
python3 --version        # 需要 3.11 及以上
git clone https://github.com/chubbyguan/chubbyskills.git
cd chubbyskills
python3 tools/chubby.py init --vault "$PWD/creator-vault"
```

**预期**：`chubby.yaml`、`inbox/`、`runs/`、`.chubby/runs.jsonl` 出现在当前目录。

| 不对时 | 看 |
|---|---|
| macOS 自带 Python 是 3.9 | 第 0 步的 `--version`；`subscribe` 链路需要 3.11+ |
| 配置写到了别处 | 配置落在**你运行命令的目录**，不是仓库或 site-packages |

## 1. 第一个来源

先用一个必然可达的公开源：

```bash
python3 tools/chubby.py subscribe init
python3 tools/chubby.py subscribe add \
  --id yt-3blue1brown --name "3Blue1Brown" \
  --resolve "https://www.youtube.com/@3blue1brown" \
  --content-profile video --mode discover_only --poll-minutes 240
python3 tools/chubby.py subscribe test yt-3blue1brown
```

**预期**：`test` 返回 HTTP 200 和条目数（通常 15–40 条）。

| 不对时 | 看 |
|---|---|
| 401/403 | 源可能不是公开 Feed；本项目不接受带凭据的私有 Feed |
| 解析 0 条 | 换一个频道；YouTube 有时会限制特定出口 |

## 2. 建基线，再确认去重

```bash
python3 tools/chubby.py subscribe sync --all
python3 tools/chubby.py subscribe sync --all
```

**预期**：第一次 `new=25 duplicates=0`（数字取决于频道）；第二次 `new=0` 且 `duplicates` 等于第一次的 new 数。

**这一步是复刻的分水岭**：如果第二次仍然 `new>0`，说明游标没生效，长期跑会重复入库。

## 3. 让调度真的跑起来（最容易卡住的一步）

```bash
python3 tools/chubby.py subscribe schedule install
python3 tools/chubby.py subscribe schedule status
```

**预期**：`install` 打印写入的单元文件路径与解释器；`status` 显示定时器状态。

```bash
# 等一个周期后，或手动触发一次
python3 tools/chubby.py subscribe tick --due --no-process
python3 tools/chubby.py subscribe schedule status
```

**预期**：`status` 的「最近记录」里出现一行，字段是 `due=… healthy=… unchanged=… errors=…`。

| 不对时 | 看 |
|---|---|
| `最近记录：无` | 定时器没跑过；先手动 `tick` 一次确认命令本身能跑 |
| 定时器未安装 | `subscribe schedule install` 的输出；Linux 需要 `systemctl --user` 可用 |
| 每小时都在报错 | 看 `.chubby/logs/subscribe.err.log` |

> **为什么这步最容易卡**：调度失败通常是**静默**的——它只是没跑。所以 `tick` 自己写日志，`schedule status` 把它读回来。**没有记录的调度和停掉的调度是同一件事。**

## 4. 让它真的产出内容

`discover_only` 只发现不入库（这是有意的：避免无节制地下载转录）。挑一条推进管线：

```bash
python3 tools/chubby.py subscribe pending
python3 tools/chubby.py subscribe promote <id>
python3 tools/chubby.py subscribe process --limit 1 --timeout 600
```

**预期**：条目状态变成 `succeeded`，`creator-vault/00_Inbox/` 下出现一篇 Markdown。

| 不对时 | 看 |
|---|---|
| 卡在转录 | `chubby doctor --platform youtube`；本地转录要 funasr，云转录要 DashScope/Groq key |
| 采集失败 | `chubby doctor --credentials`；凭据怎么拿、上次结果都在那儿 |

**想让它全自动**：把来源的 `mode` 改成 `auto_ingest`，调度里的 `tick` 就会自动处理新条目（`--process-limit` 控制每次上限）。

## 5. 内容能被找回来

```bash
python3 tools/chubby.py search "<笔记里出现过的词>"
python3 tools/chubby.py brief --topic "<同一个词>" --output "$PWD/creator-vault/30_Output/brief.md"
```

**预期**：`search` 命中刚入库的笔记；`brief.md` 里有逐字摘录、原文行号、来源和 SHA-256。

## 6. 每天自动出简报（可选，建议）

```bash
python3 tools/chubby.py subscribe digest --days 1
python3 tools/chubby.py subscribe site build --output "$PWD/creator-vault/30_Output/site"
```

**预期**：`30_Output/` 下出现当日简报；站点目录里有 `index.html`、`feed.xml`、`llms.txt`。

想让它每天自动出，用 `subscribe schedule` 的方式再加一个定时任务，或直接用系统调度器调用 `subscribe digest --days 1`。

## 7. 复查：这套东西还活着吗

一周后跑这三条，比"感觉它在跑"可靠：

```bash
python3 tools/chubby.py subscribe status          # 每源 7 天检查数、错误数、上次 HTTP 状态
python3 tools/chubby.py subscribe schedule status # 定时器状态 + 最近几次 tick 结果
python3 tools/chubby.py doctor --credentials      # 凭据配置 + 各 skill 上次真实结果
```

**预期**：`errors` 为 0 或偶发；`最近记录` 的时间戳是最近的。

---

## 复刻失败时的通用排查顺序

1. **命令本身对不对** —— 手动跑一次 `tick`，看它输出什么
2. **调度有没有在跑** —— `schedule status` 的「最近记录」是否在更新
3. **来源还可达吗** —— `subscribe test <id>`
4. **凭据还有效吗** —— `doctor --credentials` 的「最近一次相关采集」
5. **依赖齐了吗** —— `chubby doctor --platform <平台>`

每一步都对应一个**可观察的证据**，而不是猜测。这套顺序本身也是项目对"验证"的一贯做法，见[验证模型](./verification-model.md)。
