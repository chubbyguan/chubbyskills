"""平台配置：把每个采集平台的差异收敛为数据，而非代码复制。

新增平台只需声明一份 PlatformConfig，yt-dlp 封装 / 转录 / 文件名等
公共行为全部由 chubby_common 提供。
"""

from dataclasses import dataclass, field

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class PlatformConfig:
    """单个平台的转录相关配置。"""

    id: str                      # 机器可读平台 ID，如 tiktok / weibo / zhihu
    name: str                    # 展示名，如 TikTok / 微博 / 知乎
    tag: str                     # Markdown tags 使用的标签名
    default_title: str           # 标题抓取失败时的兜底标题
    language: str = "auto"       # 转录语言：auto 或 zh
    ua: str = DEFAULT_UA         # User-Agent
    referer: str = ""            # Referer，为空则不传
    extra_ydl_args: tuple = field(default_factory=tuple)  # 附加 yt-dlp 参数
    tmp_prefix: str = ""         # 临时目录前缀，默认用 id
    info_timeout: int = 30       # 获取标题超时（秒）
    subtitle_timeout: int = 120  # 抓字幕超时（秒）
    download_timeout: int = 300  # 下载音频超时（秒）
    max_retry: int = 3           # 下载重试次数

    def __post_init__(self):
        if not self.tmp_prefix:
            object.__setattr__(self, "tmp_prefix", self.id)
