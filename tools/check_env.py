#!/usr/bin/env python3
"""
chubbyskills 依赖体检

一眼看清缺哪些依赖、各能力是否就绪，以及哪些功能「零依赖」即可用（轻量模式）。
纯标准库，直接运行：

    python3 tools/check_env.py
"""

import os
import sys
import shutil
import importlib.util


def has_cmd(c):
    return shutil.which(c) is not None


def has_mod(m):
    try:
        return importlib.util.find_spec(m) is not None
    except Exception:
        return False


def main():
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

    line(True, "图文/文字采集：小红书·X 图文、公众号、情报雷达、知识库健康检查 — 零依赖")
    line(sys_ok["yt-dlp"], "字幕优先：YouTube/B站（命中字幕免 GPU）", "yt-dlp")
    vmiss = [n for n, ok in (("yt-dlp", sys_ok["yt-dlp"]), ("ffmpeg", sys_ok["ffmpeg"]),
                             ("funasr", mod_ok["funasr"])) if not ok]
    line(not vmiss, "视频转录：抖音·B站·TikTok·微博·知乎·小红书视频·X视频", " / ".join(vmiss))
    pmiss = [n for n, ok in (("ffmpeg", sys_ok["ffmpeg"]),
                             ("faster-whisper", mod_ok["faster_whisper"])) if not ok]
    line(not pmiss, "播客转录：小宇宙·喜马拉雅", " / ".join(pmiss))
    line(mod_ok["bs4"], "公众号文章采集", "beautifulsoup4")

    print("\n💡 轻量模式：纯图文/文字采集（小红书·X·公众号·情报雷达·知识库管理）完全零依赖；")
    print("   YouTube/B站优先抓字幕，命中时也无需 funasr。只有「视频/播客转录」才需要 funasr / whisper。")
    print("\n   一键安装依赖：bash setup.sh [skill-name ...]")


if __name__ == "__main__":
    main()
