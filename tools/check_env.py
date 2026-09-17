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
except ModuleNotFoundError:
    import platform_health


def has_cmd(c):
    return shutil.which(c) is not None


def has_mod(m):
    try:
        return importlib.util.find_spec(m) is not None
    except Exception:
        return False


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
        "funasr": "pip install funasr modelscope torch torchaudio   （视频/视频笔记转录）",
        "faster_whisper": "pip install faster-whisper   （播客转录）",
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
                             ("faster-whisper", mod_ok["faster_whisper"])) if not ok]
    line(not pmiss, "播客转录：小宇宙·喜马拉雅", " / ".join(pmiss))
    line(mod_ok["bs4"], "公众号文章采集", "beautifulsoup4")

    print("\n💡 小红书·X 图文、情报雷达和知识库管理可以只用标准库；公众号 HTML 需要 beautifulsoup4。")
    print("   YouTube/B站优先抓字幕，命中时也无需 funasr。只有「视频/播客转录」才需要 funasr / whisper。")
    print("\n   一键安装依赖：bash setup.sh [skill-name ...]")
    print("   只验所需路径：python3 tools/check_env.py --platform <platform-id>")
    return 0


def platform_report(selected):
    definitions = {item["id"]: item for item in platform_health.load_records(platform_health.DEFAULT_PLATFORM_DIR)}
    results = []
    for name in selected:
        if name not in definitions:
            raise ValueError(f"Unknown platform: {name}")
        definition = definitions[name]
        missing = {}
        for group in ("required", "optional"):
            missing[group] = []
            for dependency in definition.get(f"{group}_deps", []):
                present, label = platform_health.check_dependency(dependency)
                if not present:
                    missing[group].append(label)
        results.append({
            "platform": name,
            "ready": not missing["required"],
            "missing_required": missing["required"],
            "missing_optional": missing["optional"],
            "install_hint": f"bash setup.sh {definition['skill']}",
            "scope": definition.get("notes", "Default capture path only"),
        })
    return {"platforms": results, "checks_live_access": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check capture dependencies; explicit platform checks fail when required dependencies are missing")
    parser.add_argument("--platform", action="append", help="Platform ID; repeat to check more than one")
    parser.add_argument("--json", action="store_true", help="Return the platform dependency report as JSON")
    args = parser.parse_args(argv)
    if not args.platform and not args.json:
        return report_all()
    selected = args.platform or [item["id"] for item in platform_health.load_records(platform_health.DEFAULT_PLATFORM_DIR)]
    try:
        report = platform_report(list(dict.fromkeys(selected)))
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
        print("此检查不访问真实平台；字幕、登录态和网络仍影响采集。")
    return 1 if args.platform and any(not item["ready"] for item in report["platforms"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
