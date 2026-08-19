"""VTT 字幕解析与语言优先级挑选（B 站 / YouTube 共用）。"""

import glob
import os
import re


def parse_vtt(path: str) -> str:
    """把 vtt 字幕解析成纯文本：去时间轴、去标签、去连续重复行。"""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line:
            continue
        if line.isdigit() or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        line = re.sub(r"<[^>]+>", "", line).replace("&nbsp;", " ").strip()
        if not line or (out and out[-1] == line):
            continue
        out.append(line)
    return "\n".join(out)


def pick_subtitle(files, priority: tuple) -> str:
    """按语言优先级从 vtt 文件列表中挑选最合适的。"""
    def rank(path):
        name = os.path.basename(path).lower()
        for index, tag in enumerate(priority):
            if tag in name:
                return index
        return 99

    return sorted(files, key=rank)[0]


def find_vtt_files(tmpdir: str) -> list:
    return glob.glob(os.path.join(tmpdir, "*.vtt"))
