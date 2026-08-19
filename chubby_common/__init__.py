"""Chubby Skills 公共模块：被各平台采集脚本共享的零依赖工具层。

包含：平台配置、依赖体检、yt-dlp 封装、SenseVoice 转录封装、
统一 Markdown 生成、VTT 字幕解析。

用法（在各 skill 脚本中）：
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from chubby_common.config import PlatformConfig
    from chubby_common import ytdlp, funasr, markdown, vtt, deps
"""
