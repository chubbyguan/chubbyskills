#!/usr/bin/env python3
"""Export a shareable chubbyskills archive with the Xiaohongshu skill removed.

The source repository is never modified; this only shapes an exported copy.

Two properties matter here:

* **Privacy.** The file list comes from `git ls-files`, not from a directory
  walk, so `creator-vault/`, `.venv/`, `output/` and `chubby.yaml` cannot leak
  into an archive even though they sit in the working tree.
* **Failing loudly.** Every removal rule below must match. A rule that stops
  matching means the repository moved underneath the script, and the build
  aborts rather than shipping an archive that is only half de-Xiaohongshu'd.

Derived documents (`docs/platform-status.md`, `docs/platform-smoke-matrix.md`,
the golden fixture) are regenerated with the copy's own generators instead of
being hand-edited, so the archive still passes the repository's CI checks.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Root-level working directories that a test run can recreate inside the export.
ROOT_LEVEL_JUNK = (".chubby", ".pytest_cache", ".ruff_cache", "inbox", "output", "outputs", "runs")

# Never exported: the Xiaohongshu surface, plus material that carries no value
# for a recipient (or is this script itself).
DROP_PATHS = (
    "xiaohongshu-ingest",
    "platforms/xiaohongshu.yaml",
    "templates/sites/xiaohongshu.yaml",
    "examples/outputs/xiaohongshu-sample.md",
    "docs/release-0.11.0.md",
    "tools/pack_release.py",
)

# (repository path, exact text, replacement[, expected_matches]). Whole-line and
# whole-block removals are rules whose replacement is empty, so a block stays one
# indivisible rule. Every rule must match the expected number of times (1 unless
# said otherwise); a rule that stops matching aborts the build rather than
# shipping a half-trimmed archive. This is a list, not a dict, on purpose: a dict
# literal silently drops an earlier rule when a file is named twice.
ALL = "every match"

RULES = (
    # --- skill registry, routing and packaging ---------------------------------------
    ("tools/install_skill.py",
     '    "xiaohongshu-ingest", "youtube-transcribe", "zhihu-transcribe",\n',
     '    "youtube-transcribe", "zhihu-transcribe",\n'),
    ("tools/chubby_ingest.py",
     '    "xiaohongshu": ["xiaohongshu-ingest", "scripts", "fetch_note.py"],\n', ""),
    ("tools/chubby_ingest.py",
     '    if "xiaohongshu.com" in host or "xhslink.com" in host:\n        return "xiaohongshu"\n', ""),
    ("tools/chubby.py",
     '    if skill in {"x", "xiaohongshu"}:', '    if skill == "x":'),
    ("tools/validate_outputs.py", '    "xiaohongshu",\n', ""),
    ("tools/platform_smoke.py",
     '    "xiaohongshu": {\n'
     '        "source": "https://www.xiaohongshu.com/explore/example",\n'
     '        "title": "小红书 fallback smoke",\n'
     '    },\n', ""),
    # --- failure classification -------------------------------------------------------
    # `XHS_COOKIE` is only one keyword in an error-text match; the list already
    # carries the generic "cookie" / "登录" / "403" terms, so dropping it costs
    # no detection ability in a tree that has no Xiaohongshu skill.
    ("tools/platform_smoke.py",
     '("auth_or_cookie", ("cookie", "login", "登录", "XHS_COOKIE", "unauthorized", "forbidden", "403")),',
     '("auth_or_cookie", ("cookie", "login", "登录", "unauthorized", "forbidden", "403")),'),
    # --- credentials report -----------------------------------------------------------
    ("tools/check_env.py",
     '    {\n'
     '        "name": "XHS_COOKIE",\n'
     '        "secret": True,\n'
     '        "skills": ("xiaohongshu",),\n'
     '        "unlocks": "提高小红书图文采集的成功率；未配置时更容易被风控拦住",\n'
     '        "how": ["登录小红书网页版，从开发者工具复制 Cookie 头，整串写入 XHS_COOKIE"],\n'
     '    },\n', ""),
    ("tools/check_env.py",
     '    for e, use in [("DEEPSEEK_API_KEY", "翻译 / 爆款拆解 / 学习笔记"),\n'
     '                   ("XHS_COOKIE", "提高小红书采集成功率")]:\n',
     '    for e, use in [("DEEPSEEK_API_KEY", "翻译 / 爆款拆解 / 学习笔记")]:\n'),
    ("tools/check_env.py",
     '    line(True, "小红书·X 图文、情报雷达、知识库健康检查 — 零依赖")',
     '    line(True, "X 图文、情报雷达、知识库健康检查 — 零依赖")'),
    ("tools/check_env.py",
     '视频转录：抖音·B站·TikTok·微博·知乎·小红书视频·X视频',
     '视频转录：抖音·B站·TikTok·微博·知乎·X视频'),
    ("tools/check_env.py",
     '💡 小红书·X 图文、情报雷达和知识库管理可以只用标准库',
     '💡 X 图文、情报雷达和知识库管理可以只用标准库'),
    # --- distribution packaging -------------------------------------------------------
    ("pyproject.toml", "personal knowledge base: 14 agent skills",
     "personal knowledge base: 13 agent skills"),
    ("pyproject.toml", '"x_ingest", "xiaohongshu_ingest", "youtube_transcribe"',
     '"x_ingest", "youtube_transcribe"'),
    ("pyproject.toml", 'xiaohongshu_ingest = "xiaohongshu-ingest"\n', ""),
    ("pyproject.toml",
     'xiaohongshu_ingest = ["SKILL.md", "*.md", "*.txt", "*.yaml", "*.yml", "*.json", "scripts/*", "references/*", "assets/*"]\n',
     ""),
    # --- test expectations ------------------------------------------------------------
    ("tests/test_install_skill.py", "self.assertEqual(len(installed), 14)",
     "self.assertEqual(len(installed), 13)"),
    ("tests/test_install_skill.py",
     'install_skill.install_skills(["x-ingest", "xiaohongshu-ingest", "knowledge-base-management"], destination)',
     'install_skill.install_skills(["x-ingest", "knowledge-base-management"], destination)'),
    ("tests/test_install_skill.py",
     '                ("xiaohongshu-ingest", "fetch_note.py", "https://www.xiaohongshu.com/explore/example"),\n', ""),
    ("tests/test_install_skill.py",
     'self.run_setup(["x-ingest", "xiaohongshu-ingest", "content-enrich"]',
     'self.run_setup(["x-ingest", "content-enrich"]'),
    ("tests/test_tools.py",
     '            "https://www.xiaohongshu.com/explore/abc": "xiaohongshu",\n', ""),
    ("tests/test_tools.py",
     '            if item["platform"] in {"x", "xiaohongshu"}',
     '            if item["platform"] == "x"'),
    ("tests/test_tools.py", "self.assertEqual(len(manual_results), 2)",
     "self.assertEqual(len(manual_results), 1)"),
    ("tests/test_tools.py", "self.assertGreaterEqual(len(results), 10)",
     "self.assertGreaterEqual(len(results), 9)", ALL),
    # --- README, both locales (CI checks the two for parity) --------------------------
    ("README.md", "| X / 小红书 | 手动兜底 | 零依赖采集正文；", "| X | 手动兜底 | 零依赖采集正文；"),
    ("README.md", "X 推文和小红书图文都走 Python 标准库", "X 推文走 Python 标准库"),
    ("README.md", "把链接换成你要存的任意推文或小红书图文即可。", "把链接换成你要存的任意推文即可。"),
    ("README.md", "| X / 小红书图文 | Python 标准库；", "| X 图文 | Python 标准库；"),
    ("README.md", "X、小红书、抖音、B站、公众号账号扫描尚未支持", "X、抖音、B站、公众号账号扫描尚未支持"),
    ("README.md", "| 图文 | [xiaohongshu-ingest](./xiaohongshu-ingest/SKILL.md) | 小红书图文、视频及可选内容分析 |\n", ""),
    ("README.md", "小红书可按需配置自己的 `XHS_COOKIE`，", ""),
    ("README.md", " · [小红书](https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8)", ""),
    ("README.en.md", "| X / Xiaohongshu | Manual fallback |", "| X | Manual fallback |"),
    ("README.en.md", "X posts and Xiaohongshu image notes both go through the Python standard library only",
     "X posts go through the Python standard library only"),
    ("README.en.md", "Swap the link for any post or Xiaohongshu note you want to keep.",
     "Swap the link for any post you want to keep."),
    ("README.en.md", "| X/Xiaohongshu text and image posts |", "| X text and image posts |"),
    ("README.en.md", "X, Xiaohongshu, Douyin, Bilibili, or WeChat", "X, Douyin, Bilibili, or WeChat"),
    ("README.en.md", "| [xiaohongshu-ingest](./xiaohongshu-ingest/SKILL.md) | Xiaohongshu text, images, and video |\n", ""),
    ("README.en.md", "(`XHS_COOKIE`, `X_COOKIES`, or `YTDLP_COOKIES_FROM_BROWSER` for yt-dlp paths)",
     "(`X_COOKIES`, or `YTDLP_COOKIES_FROM_BROWSER` for yt-dlp paths)"),
    ("README.en.md", " · [Xiaohongshu](https://www.xiaohongshu.com/user/profile/57c061626a6a696f5a70f9a8)", ""),
    ("README.en.md", "Bilibili, YouTube, Douyin, TikTok, Weibo, Zhihu, WeChat, Xiaohongshu, X/Twitter, and podcasts",
     "Bilibili, YouTube, Douyin, TikTok, Weibo, Zhihu, WeChat, X/Twitter, and podcasts"),
    # --- version badge and skill count -------------------------------------------------
    # The badge is what a reader sees first, so it has to follow the trimmed set.
    # The version badge itself needs no rule: it tracks VERSION, which the export
    # carries unchanged. Only the count differs.
    ("README.md", "badge/Skills-14-10B981", "badge/Skills-13-10B981"),
    ("README.en.md", "badge/Skills-14-10B981", "badge/Skills-13-10B981"),
    ("README.md", "**14 个 Agent Skills 与命令行工具**", "**13 个 Agent Skills 与命令行工具**"),
    ("README.md", "14 个 skill 目录随包一起安装", "13 个 skill 目录随包一起安装"),
    ("README.md", "已对齐当前 14 个 Skills 版本", "已对齐当前 13 个 Skills 版本"),
    ("README.en.md", "**14 agent skills and a local command-line workflow**",
     "**13 agent skills and a local command-line workflow**"),
    ("README.en.md", "the 14 skill directories ship with the package",
     "the 13 skill directories ship with the package"),
    ("README.en.md", "install all 14, use the following commands",
     "install all 13, use the following commands"),
    ("docs/introduction.md", "14 个 Agent Skills 加一个", "13 个 Agent Skills 加一个"),
    # --- product documentation --------------------------------------------------------
    ("docs/installation.md",
     "9 个技能使用 `chubby_common`：6 个视频转录技能、`content-enrich`、`learning-notes-automation` 和小红书的爆款分析脚本。",
     "8 个技能使用 `chubby_common`：6 个视频转录技能、`content-enrich`、`learning-notes-automation` 和情报雷达。"),
    ("docs/installation.md",
     "`setup.sh` 接受全部 14 个完整技能目录名及原有简写。`x-ingest` 和 `xiaohongshu-ingest` 默认保持图文轻量能力；",
     "`setup.sh` 接受全部 13 个完整技能目录名及原有简写。`x-ingest` 默认保持图文轻量能力；"),
    ("docs/installation.md",
     "测试会把全部 14 个安装产物分别移动到独立目录，用 Python 隔离模式导入每个脚本，并实际执行 X / 小红书的手动采集与知识库检索。",
     "测试会把全部 13 个安装产物分别移动到独立目录，用 Python 隔离模式导入每个脚本，并实际执行 X 的手动采集与知识库检索。"),
    ("docs/creator-workflow.md", "| X / 小红书 |", "| X |"),
    ("docs/subscription-architecture.md", "（X、小红书、抖音、B站）", "（X、抖音、B站）"),
    ("docs/subscriptions.md", "X、小红书、抖音、B站、公众号账号扫描不在支持范围",
     "X、抖音、B站、公众号账号扫描不在支持范围"),
    ("docs/platform-fallbacks.md",
     "| Xiaohongshu | `missing_cookie`, `anti_bot`, `html_structure_changed` | 配置 `XHS_COOKIE` 或 `--fallback-text` |\n", ""),
    ("docs/platform-fallbacks.md", "（`YTDLP_COOKIES_FROM_BROWSER`、`XHS_COOKIE`、`X_COOKIES`）",
     "（`YTDLP_COOKIES_FROM_BROWSER`、`X_COOKIES`）"),
    ("docs/community-promotion-submission-guide.zh-CN.md",
     "14 skills for ingesting Chinese content (Douyin, Bilibili, Xiaohongshu, WeChat, X/Twitter, podcasts)",
     "13 skills for ingesting Chinese content (Douyin, Bilibili, WeChat, X/Twitter, podcasts)"),
    ("docs/community-promotion-submission-guide.zh-CN.md",
     "WeChat articles, Xiaohongshu, X/Twitter", "WeChat articles, X/Twitter"),
    ("docs/community-promotion-submission-guide.zh-CN.md",
     "14 Agent Skills that pull Chinese content (Douyin, Bilibili, Xiaohongshu, WeChat, X)",
     "13 Agent Skills that pull Chinese content (Douyin, Bilibili, WeChat, X)"),
    ("docs/community-promotion-submission-guide.zh-CN.md",
     "chubbyskills——14 个把中文全渠道内容（抖音/B站/小红书/公众号/X 等）",
     "chubbyskills——13 个把中文多渠道内容（抖音/B站/公众号/X 等）"),
    ("docs/community-promotion-submission-guide.zh-CN.md",
     "> `xiaohongshu-ingest`、`x-ingest`、`knowledge-base-management`（带 MCP 那个）。",
     "> `x-ingest`、`knowledge-base-management`（带 MCP 那个）。"),
    # --- contributing, adjacent skills and CI ------------------------------------------
    ("CONTRIBUTING.md", "如 `xiaohongshu-ingest`、`douyin-transcribe`", "如 `douyin-transcribe`、`wechat-article-ingest`"),
    ("content-enrich/SKILL.md", "抖音 / B站 / 小红书 / X / 公众号", "抖音 / B站 / X / 公众号"),
    ("x-ingest/SKILL.md", "（与抖音/B站/小红书同一套依赖）", "（与抖音/B站同一套依赖）"),
    ("x-ingest/requirements.txt", "（与抖音/B站/小红书同一套）", "（与抖音/B站同一套）"),
    ("x-ingest/scripts/fetch_tweet.py", "（与抖音/B站/小红书同一套，延迟导入）", "（与抖音/B站同一套，延迟导入）"),
    (".github/workflows/live-smoke.yml", "options: [bilibili, youtube, x, wechat, xiaohongshu]",
     "options: [bilibili, youtube, x, wechat]"),
    (".github/ISSUE_TEMPLATE/platform_failure.yml", "        - xiaohongshu\n", ""),
    (".github/ISSUE_TEMPLATE/platform_template.yml", "例如 bilibili、wechat、xiaohongshu。", "例如 bilibili、wechat、zhihu。"),
    (".github/ISSUE_TEMPLATE/bug_report.md", "<!-- 如 xiaohongshu-ingest / x-ingest / bilibili-transcribe -->",
     "<!-- 如 x-ingest / bilibili-transcribe / wechat-article-ingest -->"),
    # --- the dependency installer -------------------------------------------------------
    ("setup.sh", "#   bash setup.sh bilibili xhs    # aliases are accepted",
     "#   bash setup.sh bilibili wechat # aliases are accepted"),
    ("setup.sh", "    info \"可直接使用：X 图文、小红书图文、情报雷达、知识库健康检查、content-enrich\"",
     "    info \"可直接使用：X 图文、情报雷达、知识库健康检查、content-enrich\""),
    ("setup.sh", "    warn \"小红书采集建议按需设置 XHS_COOKIE\"\n", ""),
    ("setup.sh", "        light|x|twitter|x-ingest|xhs|xiaohongshu|xiaohongshu-ingest|content|",
     "        light|x|twitter|x-ingest|content|"),
    # --- sample assets ------------------------------------------------------------------
    ("examples/README.md", "- `outputs/xiaohongshu-sample.md`：图文采集类产物\n", ""),
    ("vault-template/10_Sources/README.md", "- `xiaohongshu/`\n", ""),
)

REPORT_NAME = "PACKAGE-INFO.md"


class RuleMiss(Exception):
    """A removal rule stopped matching the repository."""


def tracked_files(destination):
    """Export the git-tracked set, so ignored private paths cannot leak."""
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode()
    copied = 0
    for name in filter(None, listing.split("\0")):
        if any(name == drop or name.startswith(drop + "/") for drop in DROP_PATHS):
            continue
        source = ROOT / name
        if not source.is_file():
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def apply_edits(destination):
    """Apply every rule, one file at a time; a miss aborts the whole build."""
    for rule in RULES:
        relative, old, new = rule[:3]
        expected = rule[3] if len(rule) > 3 else 1
        path = destination / relative
        if not path.is_file():
            raise RuleMiss(f"rule target missing: {relative}")
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != expected and not (expected is ALL and count >= 1):
            raise RuleMiss(f"rule matched {count} times, expected {expected}: {relative}: {old[:70]!r}")
        path.write_text(text.replace(old, new), encoding="utf-8")
    return len(RULES)


def child_env(destination):
    """Environment for running the export's own scripts.

    `.venv` holds an editable install whose finder maps `tools` to the source
    checkout, and `platform_smoke.py` opens with `from tools import
    platform_health`. Without this, checks run inside the export would silently
    import the source repository and report on a tree that is not being shipped
    — which is exactly how a stale `platforms/xiaohongshu.yaml` first showed up
    in an export that no longer contained one. Placing the export ahead on
    `PYTHONPATH` works because `PathFinder` precedes the editable finder in
    `sys.meta_path`.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(destination)
    return env


def prune_runtime_artifacts(destination):
    """Remove what a test run leaves behind. Never shipped to a recipient.

    Root-level names only, mirroring the repository's `/outputs/` rule: matching
    `outputs` at any depth would delete the tracked `examples/outputs/` samples.
    """
    removed = 0
    for name in ROOT_LEVEL_JUNK:
        path = destination / name
        if path.is_dir():
            removed += sum(1 for item in path.rglob("*") if item.is_file())
            shutil.rmtree(path)
    for path in list(destination.rglob("__pycache__")):
        removed += sum(1 for item in path.rglob("*") if item.is_file())
        shutil.rmtree(path)
    for path in destination.rglob("*"):
        if path.is_file() and path.suffix in {".pyc", ".pyo"}:
            path.unlink()
            removed += 1
    return removed


def regenerate(destination, python):
    """Rebuild derived docs with the copy's own generators, so CI stays green."""
    steps = (
        [python, "tools/platform_health.py", "--repo-root", str(destination),
         "--platform-dir", str(destination / "platforms"),
         "--template-dir", str(destination / "templates" / "sites"),
         "--output", str(destination / "docs" / "platform-status.md")],
        [python, "tools/platform_smoke.py", "--mode", "all", "--write",
         "--platform-dir", str(destination / "platforms"),
         "--output", str(destination / "docs" / "platform-smoke-matrix.md")],
        [python, "tools/golden_outputs.py", "examples/outputs", "--write",
         "--golden", str(destination / "fixtures" / "golden" / "examples_outputs.json")],
    )
    for step in steps:
        result = subprocess.run(step, cwd=destination, env=child_env(destination), capture_output=True, text=True)
        if result.returncode != 0:
            raise RuleMiss(f"generator failed: {' '.join(step[:3])}\n{result.stdout}\n{result.stderr}")


def write_report(destination, version, upstream_note):
    text = f"""# chubbyskills {version} — shared build

This is a trimmed copy of [chubbyguan/chubbyskills](https://github.com/chubbyguan/chubbyskills).
It differs from upstream in exactly one functional way: **the Xiaohongshu skill is not included.**

## What was removed

| Removed | Why |
|---|---|
| `xiaohongshu-ingest/` | the skill itself |
| `platforms/xiaohongshu.yaml`, `templates/sites/xiaohongshu.yaml` | its platform definition and digest template |
| `examples/outputs/xiaohongshu-sample.md` | its sample output |

References to Xiaohongshu were also removed from the README (both locales), the
platform tables, the test suite, `pyproject.toml` and the issue templates, so the
13 remaining skills are self-consistent. The derived documents
(`docs/platform-status.md`, `docs/platform-smoke-matrix.md`,
`fixtures/golden/examples_outputs.json`) were regenerated with this copy's own
generators rather than hand-edited.

Everything else — the CLI, capture, indexing, search, briefs, subscriptions,
the MCP server and the other 13 skills — is unchanged from upstream.

## Install

    bash setup.sh            # check the environment (no packages installed)
    python3 tools/install_skill.py --list
    python3 tools/install_skill.py --all --dest ~/.claude/skills

`install_skill.py` copies self-contained skill directories; it never installs
Python packages and never overwrites an existing skill. Optional runtime
dependencies (yt-dlp, ffmpeg, funasr) are separate — see `docs/installation.md`.

## Try it in 60 seconds

    python3 tools/chubby.py init --vault ./vault
    python3 tools/chubby.py ingest "https://x.com/example/status/123456" --fallback-text note.txt
    python3 tools/chubby.py search "关键词"

## Verify

    python3 -m pytest tests/ -q      # or: python3 -m unittest discover -s tests

{upstream_note}
"""
    (destination / REPORT_NAME).write_text(text, encoding="utf-8")


CI_CHECKS = (
    ("unit tests", ["-m", "unittest", "discover", "-s", "tests"]),
    ("sample outputs", ["tools/validate_outputs.py", "examples/outputs"]),
    ("sample outputs, schema v1", ["tools/validate_outputs.py", "examples/outputs", "--schema-v1"]),
    ("golden snapshot", ["tools/golden_outputs.py", "examples/outputs"]),
    ("platform definitions", ["tools/platform_health.py", "--check"]),
    ("platform status page", ["tools/platform_health.py", "--repo-root", ".",
                              "--output", "docs/platform-status.md", "--check-output"]),
    ("platform smoke matrix", ["tools/platform_smoke.py", "--mode", "all", "--check"]),
)


def run_ci_checks(destination, python):
    """Run the export through the same gates the repository's CI runs.

    A trimmed copy is only trustworthy if the checks still pass on it, and this
    is the cheapest place to find out.
    """
    for label, arguments in CI_CHECKS:
        result = subprocess.run([python, *arguments], cwd=destination, env=child_env(destination),
                                capture_output=True, text=True)
        if result.returncode != 0:
            tail = (result.stdout + result.stderr)[-3000:]
            raise RuleMiss(f"CI check failed in the exported copy — {label}:\n{tail}")
    return len(CI_CHECKS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="Archive path (default: outputs/chubbyskills-<version>-shared.tar.gz)")
    parser.add_argument("--version", help="Override the version recorded in the archive")
    parser.add_argument("--keep-dir", help="Leave the exported tree here for inspection")
    args = parser.parse_args(argv)

    version = args.version or (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    archive = Path(args.out) if args.out else ROOT / "outputs" / f"chubbyskills-{version}-shared.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)

    if args.keep_dir:
        # Building in place keeps a failed export inspectable.
        workspace = Path(args.keep_dir).expanduser().resolve()
        if workspace.exists():
            shutil.rmtree(workspace)
    else:
        workspace = Path(tempfile.mkdtemp(prefix="chubby-pack-"))
    exported = workspace / f"chubbyskills-{version}"
    exported.mkdir(parents=True)
    try:
        count = tracked_files(exported)
        apply_edits(exported)
        regenerate(exported, sys.executable)
        (exported / "VERSION").write_text(version + "\n", encoding="utf-8")
        write_report(exported, version,
                     "This build is trimmed, so run the checks before trusting them "
                     "on code you have changed.")
        checks = run_ci_checks(exported, sys.executable)
        print(f"self-check: {checks} CI gates passed")
        pruned = prune_runtime_artifacts(exported)
        shipped = sum(1 for _ in exported.rglob("*") if _.is_file())
        print(f"exported {count} tracked files -> {shipped} shipped ({pruned} runtime files pruned)")

        with tarfile.open(archive, "w:gz") as tar:
            tar.add(exported, arcname=exported.name)
        print(f"archive: {archive} ({archive.stat().st_size / 1024:.0f} KB)")
    finally:
        if not args.keep_dir:
            shutil.rmtree(workspace, ignore_errors=True)
        else:
            print(f"tree kept at {exported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
