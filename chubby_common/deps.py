"""依赖体检：在脚本入口和关键步骤前检查系统命令 / Python 包。

缺失时给出可执行的安装提示（指向 setup.sh 档位），而不是裸 traceback。
"""

import importlib.util
import shutil
import sys


def check_command(name: str, hint: str) -> None:
    """检查系统命令是否存在，缺失时打印提示并以 exit 1 退出。"""
    if shutil.which(name) is None:
        print(f"❌ 未找到系统命令 `{name}`。", file=sys.stderr)
        print(f"   请安装：{hint}", file=sys.stderr)
        print("   装完后重新运行本脚本。", file=sys.stderr)
        raise SystemExit(1)


def check_python_module(name: str, hint: str) -> None:
    """检查 Python 包是否可导入，缺失时打印提示并以 exit 1 退出。"""
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        print(f"❌ 缺少 Python 依赖 `{name}`。", file=sys.stderr)
        print(f"   请安装：{hint}", file=sys.stderr)
        print("   装完后重新运行本脚本。", file=sys.stderr)
        raise SystemExit(1)


def ensure_ytdlp() -> None:
    """转录流程前的 yt-dlp 检查。"""
    check_command("yt-dlp", "bash setup.sh video 或 pip install -U yt-dlp")


def ensure_ffmpeg() -> None:
    """yt-dlp 转音频需要 ffmpeg。"""
    check_command(
        "ffmpeg",
        "macOS: brew install ffmpeg  |  Ubuntu: sudo apt install ffmpeg",
    )


def ensure_funasr() -> None:
    """音频转录前的 funasr 检查（模型加载时仍会延迟 import）。"""
    check_python_module(
        "funasr",
        "bash setup.sh video 或 pip install funasr modelscope torch torchaudio",
    )
