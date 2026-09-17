"""Public HTTP(S) podcast downloads with no redirect or local-file escape."""
from __future__ import annotations

import html
import ipaddress
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from urllib.parse import urlsplit, urlunsplit


def public_url(value: str) -> tuple[str, str, int, str]:
    """Validate and resolve once; curl is pinned to this verified public address."""
    if not isinstance(value, str):
        raise ValueError("Podcast URL must be public HTTP(S)")
    value = html.unescape(value)
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value) or "\\" in value:
        raise ValueError("Podcast URL contains unsupported characters")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise ValueError("Podcast URL must be public HTTP(S)") from None
    if (parts.scheme not in {"http", "https"} or not host or parts.username is not None
            or parts.password is not None or "%" in host or not 0 < port < 65536):
        raise ValueError("Podcast URL must be public HTTP(S) without credentials")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii")
            addresses = {entry[4][0] for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
        except (OSError, UnicodeError):
            raise RuntimeError("Could not resolve podcast host") from None
    else:
        addresses = {str(literal)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Podcast downloads cannot access private, loopback or reserved addresses")
    address = sorted(addresses, key=lambda item: (":" in item, item))[0]
    authority = f"[{host}]" if ":" in host else host
    if parts.port is not None:
        authority += f":{port}"
    normalized = urlunsplit((parts.scheme, authority, parts.path, parts.query, ""))
    return normalized, host, port, address


def download(url: str, output_path, *, timeout: float = 1800, max_bytes: int = 512 * 1024 * 1024) -> None:
    """Create output exclusively; reject 3xx and pin DNS, bypassing environment proxies."""
    url, host, port, address = public_url(url)
    output = Path(output_path)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Podcast download output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".podcast-download-", dir=output.parent)
    os.close(descriptor)
    try:
        command = ["curl", "--disable", "--silent", "--show-error", "--fail",
                   "--proto", "=http,https", "--proto-redir", "=http,https",
                   "--max-redirs", "0", "--noproxy", "*",
                   "--connect-timeout", "15", "--max-time", str(timeout),
                   "--max-filesize", str(max_bytes), "--output", temporary,
                   "--write-out", "%{http_code}", "--header", "User-Agent: Mozilla/5.0"]
        if host != address:
            pinned = f"[{address}]" if ":" in address else address
            command.extend(["--resolve", f"{host}:{port}:{pinned}"])
        command.extend(["--", url])
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 5, check=False)
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError("Podcast download failed; no redirected or private URL was fetched") from None
        status = result.stdout.strip()
        if status.startswith("3"):
            raise RuntimeError("Podcast URL redirects are disabled; provide the final public URL")
        if result.returncode != 0 or status != "200":
            raise RuntimeError("Podcast download failed or returned a non-200 response")
        size = os.path.getsize(temporary)
        if size == 0 or size > max_bytes:
            raise RuntimeError("Podcast response is empty or too large")
        os.link(temporary, output)
    finally:
        os.unlink(temporary)


def fetch_text(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="podcast-page-") as temporary:
        path = Path(temporary) / "page.txt"
        download(url, path, timeout=30, max_bytes=8 * 1024 * 1024)
        return path.read_text(encoding="utf-8", errors="replace")
