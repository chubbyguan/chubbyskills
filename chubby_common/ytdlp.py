"""yt-dlp 统一封装：带平台 UA / Referer / 附加参数、依赖体检、重试和友好错误。

各平台脚本不再自己拼 yt-dlp 命令，避免「同一处修复要改 N 份拷贝」。
"""

import os
import subprocess
import sys
import time

from chubby_common import deps


def run_ydl(cfg, args, timeout, capture=True):
    """统一的 yt-dlp 调用，自动带上平台的 UA / Referer / 额外参数。"""
    deps.ensure_ytdlp()
    cmd = ["yt-dlp", "--no-check-certificates", "--user-agent", cfg.ua]
    if cfg.referer:
        cmd += ["--referer", cfg.referer]
    cmd += list(cfg.extra_ydl_args) + list(args)
    return subprocess.run(
        cmd, capture_output=capture, text=True, timeout=timeout, check=not capture
    )


def get_title(cfg, url: str) -> str:
    """获取视频标题，失败回退到平台默认标题。"""
    try:
        result = run_ydl(cfg, ["--get-title", url], timeout=cfg.info_timeout, capture=True)
        return result.stdout.strip() or cfg.default_title
    except Exception:
        return cfg.default_title


def download_audio(cfg, url: str, output_dir: str, filename: str = "audio.mp3") -> str:
    """下载音频为 mp3，失败自动重试，全部失败时抛可读 RuntimeError。"""
    audio_path = os.path.join(output_dir, filename)
    last_err = None
    for attempt in range(1, cfg.max_retry + 1):
        try:
            print(
                f"  ⬇️  Downloading (attempt {attempt}/{cfg.max_retry})...",
                file=sys.stderr,
            )
            run_ydl(
                cfg,
                [
                    "--extract-audio",
                    "--audio-format",
                    "mp3",
                    "--audio-quality",
                    "128K",
                    "-o",
                    audio_path,
                    url,
                ],
                timeout=cfg.download_timeout,
            )
            if not os.path.exists(audio_path):
                raise RuntimeError(
                    f"yt-dlp 退出成功但未产出音频文件：{audio_path}，链接可能已失效"
                )
            size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            print(f"  ✅ Audio: {size_mb:.1f} MB", file=sys.stderr)
            return audio_path
        except subprocess.CalledProcessError as exc:
            last_err = exc
            print(f"  ⚠️  下载失败，{2 * attempt}s 后重试...", file=sys.stderr)
            time.sleep(2 * attempt)
        except subprocess.TimeoutExpired as exc:
            last_err = exc
            print("  ⚠️  下载超时，重试...", file=sys.stderr)
    raise RuntimeError(
        f"{cfg.name} 下载失败（已重试 {cfg.max_retry} 次）。"
        f"可能原因：链接失效、需要登录 cookie、或平台限制。原始错误：{last_err}"
    )
