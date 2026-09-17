"""Conservative source identities for repeated capture of the same material.

Known platform identities refer to the whole video or post, so playback times
and tracking parameters do not distinguish them. Bilibili parts do. Unknown
URLs remain unchanged; no redirects or other network requests are performed.
"""

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}
X_HOSTS = {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
BV_ID = re.compile(r"BV[A-Za-z0-9]{10}")
X_STATUS_PATH = re.compile(r"/(?:[A-Za-z0-9_]{1,15}|i/web)/status/([0-9]+)(?:/(?:photo|video)/[0-9]+)?/?")


def _platform_identity(source):
    if BV_ID.fullmatch(source):
        return f"bilibili:{source}:p1"
    # urlsplit discards some control characters, which could change the host.
    if any(ord(char) < 32 or ord(char) == 127 for char in source):
        return None
    try:
        url = urlsplit(source)
        if url.scheme not in {"http", "https"} or url.username is not None or url.password is not None:
            return None
        if url.port not in {None, 443 if url.scheme == "https" else 80}:
            return None
        host = url.hostname
        query = parse_qs(url.query, keep_blank_values=True)
    except ValueError:
        return None

    video = None
    if host in YOUTUBE_HOSTS:
        if url.path == "/watch":
            values = query.get("v", [])
            video = values[0] if len(values) == 1 else None
        else:
            match = re.fullmatch(r"/(?:shorts|embed)/([A-Za-z0-9_-]{11})/?", url.path)
            video = match.group(1) if match else None
    elif host in {"youtu.be", "www.youtu.be"}:
        match = re.fullmatch(r"/([A-Za-z0-9_-]{11})/?", url.path)
        video = match.group(1) if match else None
    if video and VIDEO_ID.fullmatch(video):
        return f"youtube:{video}"

    if host in BILIBILI_HOSTS:
        match = re.fullmatch(r"/video/(BV[A-Za-z0-9]{10})/?", url.path)
        parts = query.get("p", ["1"])
        if match and len(parts) == 1 and re.fullmatch(r"[0-9]+", parts[0]):
            part = parts[0].lstrip("0")
            if part:
                return f"bilibili:{match.group(1)}:p{part}"

    if host in X_HOSTS:
        match = X_STATUS_PATH.fullmatch(url.path)
        if match:
            return f"x:{match.group(1)}"
    return None


def normalize_source(source, base_dir=None):
    """Return a stable content identity, preserving unfamiliar input unchanged.

    Existing local files use their resolved absolute path and SHA-256 content
    digest. A missing or unreadable file is left unchanged instead of guessing
    an identity. Relative file paths are resolved against ``base_dir`` or cwd.
    """
    source = os.fspath(source)
    platform = _platform_identity(source)
    if platform:
        return platform
    try:
        # Unknown URLs must not accidentally be treated as local path names.
        if urlsplit(source).scheme or source.startswith("//"):
            return source
        path = Path(source).expanduser()
        if not path.is_absolute() and base_dir is not None:
            path = Path(base_dir).expanduser() / path
        path = path.resolve()
        if not path.is_file():
            return source
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"file:{path}:sha256:{digest.hexdigest()}"
    except (OSError, ValueError, RuntimeError):
        return source


def source_digest(source, base_dir=None):
    """Return the first 16 hexadecimal SHA-256 characters of the identity."""
    identity = normalize_source(source, base_dir=base_dir)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
