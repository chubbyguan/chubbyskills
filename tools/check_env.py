#!/usr/bin/env python3
"""
chubbyskills 依赖体检

一眼看清缺哪些依赖、各能力是否就绪，以及哪些功能「零依赖」即可用（轻量模式）。
纯标准库，直接运行：

    python3 tools/check_env.py
"""

import argparse
import json
import os
import shutil
import importlib.util

try:
    from tools import platform_health
    from tools import podcast_options
except ModuleNotFoundError:
    import platform_health
    import podcast_options


def has_cmd(c):
    return shutil.which(c) is not None


def has_mod(m):
    try:
        return importlib.util.find_spec(m) is not None
    except Exception:
        return False


# Credentials the project reads, what each one unlocks, and how to obtain it.
# `secret` controls whether the value may be echoed: a browser name is not a
# secret, a session cookie is, and neither may ever be written to a report.
CREDENTIALS = (
    {
        "name": "YTDLP_COOKIES_FROM_BROWSER",
        "secret": False,
        "skills": ("youtube", "bilibili", "douyin", "tiktok", "weibo", "zhihu", "podcast"),
        "unlocks": "YouTube / B站 等被判定为机器人时，用本机浏览器的登录态证明",
        "how": ["export YTDLP_COOKIES_FROM_BROWSER=chrome   # 或 safari / edge / firefox"],
    },
    {
        "name": "YTDLP_REMOTE_COMPONENTS",
        "secret": False,
        "skills": ("youtube",),
        "unlocks": "YouTube 的 JS 挑战求解组件，缺它时部分视频拿不到格式",
        "how": ["export YTDLP_REMOTE_COMPONENTS=ejs:github"],
    },
    {
        "name": "X_COOKIES",
        "secret": True,
        "skills": ("x",),
        "unlocks": "抓 X 长文章（Article）全文；未配置时只取到预览文本",
        "how": [
            "浏览器登录 x.com → 开发者工具 → Application → Cookies → https://x.com",
            "复制 auth_token 与 ct0 两个值",
            "export X_COOKIES='auth_token=<值>; ct0=<值>'",
        ],
    },
    {
        "name": "XHS_COOKIE",
        "secret": True,
        "skills": ("xiaohongshu",),
        "unlocks": "提高小红书图文采集的成功率；未配置时更容易被风控拦住",
        "how": ["登录小红书网页版，从开发者工具复制 Cookie 头，整串写入 XHS_COOKIE"],
    },
    {
        "name": "DEEPSEEK_API_KEY",
        "secret": True,
        "skills": ("content-enrich", "industry-intelligence-radar"),
        "unlocks": "内容加工、爆款拆解、学习笔记，以及 subscribe digest --enrich",
        "how": ["在 DeepSeek 控制台创建 API Key", "export DEEPSEEK_API_KEY=sk-..."],
    },
    {
        "name": "DASHSCOPE_API_KEY",
        "secret": True,
        "skills": ("podcast",),
        "unlocks": "播客云转录（qwen3-asr-flash），免本地模型",
        "how": ["在阿里云百炼创建 API Key", "export DASHSCOPE_API_KEY=sk-..."],
    },
    {
        "name": "GROQ_API_KEY",
        "secret": True,
        "skills": ("podcast",),
        "unlocks": "播客云转录（whisper-large-v3-turbo），免费额度可用",
        "how": ["在 Groq 控制台创建 API Key", "export GROQ_API_KEY=gsk_..."],
    },
)


def _last_runs_by_skill(state_file, skills, limit=400):
    """Most recent recorded outcome per skill, read from the run journal."""
    latest = {}
    if not state_file or not os.path.isfile(state_file):
        return latest
    rows = []
    with open(state_file, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    for record in rows[-limit:]:
        skill = record.get("skill")
        if skill in skills:
            latest[skill] = record
    return latest


def credentials_report(state_file=None):
    """Report configuration state, how to obtain each credential, and the last
    real outcome of the paths that depend on them.

    Deliberately no liveness probe: that would mean a real authenticated request
    to each platform, which is exactly the traffic that triggers the risk
    controls this report is meant to help with. Whether a credential still works
    is answered by the last recorded run, not by guessing.
    """
    print("🔑 凭据体检\n")
    configured, missing = [], []
    for item in CREDENTIALS:
        (configured if os.environ.get(item["name"]) else missing).append(item)

    print("【已配置】")
    if not configured:
        print("  （无）")
    for item in configured:
        value = os.environ.get(item["name"], "")
        shown = value if not item["secret"] else "（已设置，值不显示）"
        print(f"  ✅ {item['name']} = {shown}")
        print(f"     {item['unlocks']}")

    print("\n【未配置】")
    if not missing:
        print("  （无）")
    for item in missing:
        print(f"  ⚪ {item['name']}")
        print(f"     作用：{item['unlocks']}")
        print("     获取：")
        for step in item["how"]:
            print(f"       {step}")

    skills = {skill for item in CREDENTIALS for skill in item["skills"]}
    latest = _last_runs_by_skill(state_file, skills)
    print("\n【最近一次相关采集】")
    if not latest:
        print("  （还没有记录。运行一次 ingest 后，这里会显示真实结果）")
    for skill in sorted(latest):
        record = latest[skill]
        stamp = (record.get("started_at") or "")[:16].replace("T", " ")
        status = record.get("status") or "?"
        detail = ""
        if status != "success":
            error = (record.get("error") or "").strip().splitlines()
            detail = f"：{error[0][:80]}" if error else ""
        print(f"  {skill:<10} {stamp}  {status}{detail}")

    print("\n说明：这里只报告「是否配置」和「上一次的真实结果」，不会主动发探活请求——"
          "探活本身要走真实平台，正是可能触发风控的那类流量。凭据是否还有效，以上次结果为准。")
    return 0


def report_all():
    print("🩺 chubbyskills 依赖体检\n")

    cmds = {
        "python3": "随系统自带",
        "ffmpeg": "macOS: brew install ffmpeg  |  Ubuntu: apt install ffmpeg",
        "yt-dlp": "macOS: brew install yt-dlp  |  pip install yt-dlp",
    }
    print("【系统命令】")
    sys_ok = {}
    for c, hint in cmds.items():
        ok = has_cmd(c)
        sys_ok[c] = ok
        print(f"  {'✅' if ok else '❌'} {c}" + ("" if ok else f"   → {hint}"))

    mods = {
        "funasr": "pip install funasr modelscope torch torchaudio   （视频/播客转录）",
        "bs4": "pip install beautifulsoup4   （公众号文章）",
        "markitdown": "pip install markitdown   （公众号 PDF，可选）",
        "pymupdf": "pip install pymupdf   （公众号 PDF 兜底，可选）",
    }
    print("\n【Python 包】")
    mod_ok = {}
    for m, hint in mods.items():
        ok = has_mod(m)
        mod_ok[m] = ok
        print(f"  {'✅' if ok else '❌'} {m}" + ("" if ok else f"   → {hint}"))

    print("\n【环境变量（按需）】")
    for e, use in [("DEEPSEEK_API_KEY", "翻译 / 爆款拆解 / 学习笔记"),
                   ("XHS_COOKIE", "提高小红书采集成功率")]:
        print(f"  {'✅' if os.environ.get(e) else '⚪'} {e}   — {use}")

    print("\n【按能力分组】")

    def line(ok, label, need=""):
        mark = "✅" if ok else "⚠️ "
        tail = f"   （缺：{need}）" if not ok and need else ""
        print(f"  {mark} {label}{tail}")

    line(True, "小红书·X 图文、情报雷达、知识库健康检查 — 零依赖")
    line(sys_ok["yt-dlp"], "字幕优先：YouTube/B站（命中字幕免 GPU）", "yt-dlp")
    vmiss = [n for n, ok in (("yt-dlp", sys_ok["yt-dlp"]), ("ffmpeg", sys_ok["ffmpeg"]),
                             ("funasr", mod_ok["funasr"])) if not ok]
    line(not vmiss, "视频转录：抖音·B站·TikTok·微博·知乎·小红书视频·X视频", " / ".join(vmiss))
    pmiss = [n for n, ok in (("ffmpeg", sys_ok["ffmpeg"]),
                             ("funasr", mod_ok["funasr"])) if not ok]
    line(not pmiss, "播客转录：小宇宙·喜马拉雅", " / ".join(pmiss))
    line(mod_ok["bs4"], "公众号文章采集", "beautifulsoup4")

    print("\n💡 小红书·X 图文、情报雷达和知识库管理可以只用标准库；公众号 HTML 需要 beautifulsoup4。")
    print("   YouTube/B站优先抓字幕，命中时也无需 funasr。只有「视频/播客转录」才需要 funasr。")
    print("   播客本地转录默认 SenseVoice-Small；可选 qwen3-asr-0.6b 后端需额外 `pip install qwen-asr transformers torch`（非必需，缺失不影响 doctor）。")
    print("\n   安装运行依赖：bash setup.sh [skill-name ...]")
    print("   只验所需路径：python3 tools/check_env.py --platform <platform-id>")
    print("\n【下一步】")
    print("  零依赖跑通本地链路（导入 → 搜索 → 资料包）：")
    print("    python3 tools/chubby.py init --vault ./creator-vault")
    print("    python3 tools/chubby.py import <你的笔记.md> --no-enrich")
    print("    python3 tools/chubby.py search \"关键词\"")
    return 0


def platform_report(selected, provider=None):
    definitions = {item["id"]: item for item in platform_health.load_records(platform_health.DEFAULT_PLATFORM_DIR)}
    definitions["document"] = {"skill": "document", "required_deps": [], "optional_deps": ["python:pymupdf"],
                               "notes": "Markdown/text need only Python; text-based PDF also requires pymupdf."}
    results = []
    for name in selected:
        if name not in definitions:
            raise ValueError(f"Unknown platform: {name}")
        definition = dict(definitions[name])
        settings = podcast_options.resolve_config(provider=provider) if name == "podcast" else None
        cloud = settings is not None and settings["provider"] != "local"
        if cloud:
            definition.update(required_deps=[], optional_deps=["cmd:curl", "cmd:ffmpeg"],
                              notes="Optional cloud local-audio path; URL downloads need curl, DashScope/Groq container conversion may need ffmpeg. Key presence only, no remote requests.")
        missing = {}
        for group in ("required", "optional"):
            missing[group] = []
            for dependency in definition.get(f"{group}_deps", []):
                present, label = platform_health.check_dependency(dependency)
                if not present:
                    missing[group].append(label)
        if cloud:
            keys = ("DASHSCOPE_API_KEY",) if settings["provider"] == "dashscope" else ("GROQ_API_KEY",)
            if not any(os.environ.get(key) for key in keys):
                missing["required"].append("environment:" + " or ".join(keys))
        results.append({
            "platform": name,
            "ready": not missing["required"],
            "missing_required": missing["required"],
            "missing_optional": missing["optional"],
            "install_hint": ("Configure the selected provider API key in your local environment" if cloud else
                             "python3 -m pip install pymupdf (PDF only)" if name == "document" else
                             f"bash setup.sh {definition['skill']}"),
            "scope": definition.get("notes", "Default capture path only"),
            **({"provider": settings["provider"]} if settings else {}),
        })
    return {"platforms": results, "checks_live_access": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check capture dependencies; explicit platform checks fail when required dependencies are missing")
    parser.add_argument("--platform", action="append", help="Platform ID; repeat to check more than one")
    parser.add_argument("--provider", choices=["local", "dashscope", "groq"], help="Provider for --platform podcast")
    parser.add_argument("--json", action="store_true", help="Return the platform dependency report as JSON")
    parser.add_argument("--credentials", action="store_true", help="Report credential state and how to obtain each one")
    parser.add_argument("--state-file", help="Run journal used to show the last real outcome per skill")
    args = parser.parse_args(argv)
    if args.credentials:
        return credentials_report(args.state_file)
    if args.provider and (not args.platform or "podcast" not in args.platform):
        parser.error("--provider requires --platform podcast")
    if not args.platform and not args.json:
        return report_all()
    selected = args.platform or [item["id"] for item in platform_health.load_records(platform_health.DEFAULT_PLATFORM_DIR)]
    try:
        report = platform_report(list(dict.fromkeys(selected)), provider=args.provider)
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        for item in report["platforms"]:
            print(f"{'✅' if item['ready'] else '❌'} {item['platform']}: 默认采集路径依赖{'就绪' if item['ready'] else '缺失'}")
            if item["missing_required"]:
                print("  缺少必需依赖：" + ", ".join(item["missing_required"]))
                print("  安装提示：" + item["install_hint"])
            if item["missing_optional"]:
                print("  可选路径尚缺：" + ", ".join(item["missing_optional"]))
            if item["ready"] and item["platform"] != "document":
                print("  下一步：python3 tools/chubby.py ingest \"<真实链接>\" --skill "
                      + item["platform"] + " --no-enrich")
        print("此检查不访问真实平台；字幕、登录态和网络仍影响采集。")
    return 1 if args.platform and any(not item["ready"] for item in report["platforms"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
