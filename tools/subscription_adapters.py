"""Low-risk discovery adapters for Chubby subscription sources.

P0 deliberately supports only public HTTPS feeds and YouTube's public Atom feed.
The module never writes state or starts ingestion; callers own policy and queues.
"""

from __future__ import annotations

import email.utils
import ipaddress
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Public RSS hosts sometimes blacklist application names while accepting the
# standard client identity that urllib actually uses. Keep this accurate instead
# of impersonating a browser or sending a project-branded UA.
USER_AGENT = f"Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"
MAX_BODY_BYTES = 16 * 1024 * 1024  # large podcast feeds with full content commonly exceed 2 MiB
MAX_REDIRECTS = 3
# Clash and similar local proxy clients use this IANA benchmarking range as a
# synthetic DNS answer. The domain name remains part of the HTTP request and
# the OS proxy transparently resolves it upstream. Rejecting it would make all
# public subscriptions fail on those machines, while every other non-global IP
# remains blocked below.
FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")


class AdapterError(RuntimeError):
    """A source fetch or parsing failure with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retry_after: int | None = None,
        http_status: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after
        self.http_status = http_status


@dataclass(frozen=True)
class DiscoveredEntry:
    external_id: str
    url: str
    title: str
    author: str
    published_at: str
    updated_at: str
    content_html: str
    summary_html: str
    enclosure_url: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    body: bytes
    etag: str
    last_modified: str
    final_url: str
    not_modified: bool = False


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _first_child(node: ET.Element, *names: str) -> ET.Element | None:
    wanted = set(names)
    for child in node:
        if _local_name(child.tag) in wanted:
            return child
    return None


def _children(node: ET.Element, *names: str) -> list[ET.Element]:
    wanted = set(names)
    return [child for child in node if _local_name(child.tag) in wanted]


def normalize_timestamp(value: str) -> str:
    """Return a timezone-aware ISO timestamp or an empty string."""

    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError, OverflowError):
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat()


def _validate_public_https(url: str) -> urllib.parse.SplitResult:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise AdapterError("invalid_url", f"invalid feed URL: {exc}") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise AdapterError(
            "invalid_url", "feed URLs must be public HTTPS URLs without credentials"
        )
    if parsed.port not in {None, 443}:
        raise AdapterError("invalid_url", "feed URLs may only use HTTPS port 443")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
        ".local"
    ):
        raise AdapterError("unsafe_url", "local feed hosts are not allowed")
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AdapterError("network", f"cannot resolve feed host: {exc}") from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if address in FAKE_IP_NETWORK:
            continue
        if not address.is_global:
            raise AdapterError(
                "unsafe_url", "feed host resolves to a non-public address"
            )
    return parsed


def classify_http_error(status: int) -> tuple[str, bool]:
    """Return the stable code and whether the source needs manual repair."""

    if status in {401, 403, 404}:
        return f"http_{status}", True
    if status == 429:
        return "http_429", False
    if 500 <= status <= 599:
        return "http_5xx", False
    if 400 <= status <= 499:
        return "http_4xx", True
    return "http", False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public_feed(
    url: str,
    *,
    etag: str = "",
    last_modified: str = "",
    timeout: int = 20,
    user_agent: str = "",
    max_bytes: int = MAX_BODY_BYTES,
) -> FetchResult:
    """Fetch one public feed with conditional headers and validated redirects."""

    current_url = url
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    for _ in range(MAX_REDIRECTS + 1):
        _validate_public_https(current_url)
        headers = {
            "User-Agent": user_agent or USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/feed+json, application/json, text/xml, application/xml;q=0.9, */*;q=0.1",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        request = urllib.request.Request(current_url, headers=headers, method="GET")
        try:
            response = opener.open(request, timeout=timeout)
            try:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise AdapterError(
                        "body_too_large", f"feed exceeds {max_bytes} bytes"
                    )
                status = getattr(response, "status", 200)
                return FetchResult(
                    status,
                    body,
                    response.headers.get("ETag", ""),
                    response.headers.get("Last-Modified", ""),
                    response.geturl(),
                )
            finally:
                response.close()
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return FetchResult(
                    304, b"", etag, last_modified, current_url, not_modified=True
                )
            if exc.code in {301, 302, 303, 307, 308}:
                target = exc.headers.get("Location", "")
                if not target:
                    raise AdapterError(
                        "http_3xx", f"redirect {exc.code} had no Location header"
                    ) from exc
                current_url = urllib.parse.urljoin(current_url, target)
                continue
            try:
                retry_after = max(0, int(exc.headers.get("Retry-After", "")))
            except ValueError:
                retry_after = None
            error_code, _ = classify_http_error(exc.code)
            raise AdapterError(
                error_code,
                f"feed request returned HTTP {exc.code}",
                retry_after=retry_after,
                http_status=exc.code,
            ) from exc
        except AdapterError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AdapterError("network", f"feed request failed: {exc}") from exc
    raise AdapterError("redirect_limit", f"feed exceeded {MAX_REDIRECTS} redirects")


def youtube_feed_url(channel_id: str) -> str:
    channel = (channel_id or "").strip()
    if not channel or any(char.isspace() for char in channel):
        raise AdapterError("invalid_config", "youtube channel_id is required")
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={urllib.parse.quote(channel, safe='_-')}"


CHANNEL_ID_RE = re.compile(r"UC[A-Za-z0-9_-]{22}")


def resolve_youtube_channel_id(value: str) -> str:
    """Resolve a channel_id from a raw UC id, @handle, or channel page URL."""
    raw = (value or "").strip()
    if CHANNEL_ID_RE.fullmatch(raw):
        return raw
    if raw.startswith("@"):
        url = f"https://www.youtube.com/{raw}"
    elif "youtube.com" in raw or "youtu.be" in raw:
        url = raw if raw.startswith("http") else "https://" + raw
    else:
        raise AdapterError(
            "invalid_config",
            "unrecognized YouTube channel: pass a channel_id, @handle or channel URL",
        )
    # Channel pages are heavier than feeds; the id appears early in the HTML.
    result = fetch_public_feed(url, max_bytes=8 * 1024 * 1024)
    text = result.body.decode("utf-8", "replace")
    for pattern in (
        r'"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',
        r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[A-Za-z0-9_-]{22})"',
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    raise AdapterError(
        "parse", "no channel_id found in the page (not a channel page?)"
    )


def _entry_from_json(item: dict[str, Any]) -> DiscoveredEntry:
    attachments = (
        item.get("attachments") if isinstance(item.get("attachments"), list) else []
    )
    enclosure = ""
    for attachment in attachments:
        if isinstance(attachment, dict) and isinstance(attachment.get("url"), str):
            enclosure = attachment["url"].strip()
            if enclosure:
                break
    content = item.get("content_html") or item.get("content_text") or ""
    summary = item.get("summary") or ""
    return DiscoveredEntry(
        external_id=str(item.get("id") or "").strip(),
        url=str(item.get("url") or item.get("external_url") or "").strip(),
        title=str(item.get("title") or "Untitled feed entry").strip(),
        author=str(item.get("author") or "").strip(),
        published_at=normalize_timestamp(str(item.get("date_published") or "")),
        updated_at=normalize_timestamp(str(item.get("date_modified") or "")),
        content_html=str(content),
        summary_html=str(summary),
        enclosure_url=enclosure,
        raw=item,
    )


def _parse_json_feed(data: Any) -> list[DiscoveredEntry]:
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise AdapterError("parse", "JSON feed must contain an items array")
    return [_entry_from_json(item) for item in data["items"] if isinstance(item, dict)]


def _rss_entries(root: ET.Element) -> list[DiscoveredEntry]:
    channel = next(
        (child for child in root if _local_name(child.tag) == "channel"), root
    )
    result = []
    for item in _children(channel, "item"):
        title = _text(_first_child(item, "title")) or "Untitled feed entry"
        link = _text(_first_child(item, "link"))
        guid = _text(_first_child(item, "guid", "id"))
        author = _text(_first_child(item, "author", "creator"))
        published = _text(_first_child(item, "pubDate", "published", "date"))
        updated = _text(_first_child(item, "updated"))
        summary = _text(_first_child(item, "description", "summary"))
        content_node = _first_child(item, "encoded", "content")
        enclosure = ""
        for node in _children(item, "enclosure"):
            enclosure = (node.attrib.get("url") or "").strip()
            if enclosure:
                break
        result.append(
            DiscoveredEntry(
                guid,
                link,
                title,
                author,
                normalize_timestamp(published),
                normalize_timestamp(updated),
                _text(content_node),
                summary,
                enclosure,
                {"kind": "rss", "id": guid, "link": link},
            )
        )
    return result


def _atom_entries(root: ET.Element) -> list[DiscoveredEntry]:
    result = []
    for entry in _children(root, "entry"):
        title = _text(_first_child(entry, "title")) or "Untitled feed entry"
        external_id = _text(_first_child(entry, "id"))
        url = ""
        enclosure = ""
        for link in _children(entry, "link"):
            href = (link.attrib.get("href") or "").strip()
            rel = (link.attrib.get("rel") or "alternate").lower()
            if rel == "enclosure" and href and not enclosure:
                enclosure = href
            elif rel in {"alternate", ""} and href and not url:
                url = href
        if not url:
            url = _text(_first_child(entry, "link"))
        author_node = _first_child(entry, "author")
        author = (
            _text(_first_child(author_node, "name")) if author_node is not None else ""
        )
        result.append(
            DiscoveredEntry(
                external_id,
                url,
                title,
                author,
                normalize_timestamp(_text(_first_child(entry, "published"))),
                normalize_timestamp(_text(_first_child(entry, "updated"))),
                _text(_first_child(entry, "content")),
                _text(_first_child(entry, "summary")),
                enclosure,
                {"kind": "atom", "id": external_id, "link": url},
            )
        )
    return result


def parse_feed(body: bytes, *, declared_format: str = "auto") -> list[DiscoveredEntry]:
    """Parse RSS 2.0, Atom and JSON Feed using dependency-free structures."""

    if len(body) > MAX_BODY_BYTES:
        raise AdapterError("body_too_large", f"feed exceeds {MAX_BODY_BYTES} bytes")
    stripped = body.lstrip()
    if declared_format not in {"auto", "rss", "atom", "json"}:
        raise AdapterError("invalid_config", f"unknown feed format: {declared_format}")
    if declared_format == "json" or (
        declared_format == "auto" and stripped.startswith((b"{", b"["))
    ):
        try:
            return _parse_json_feed(json.loads(body.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterError("parse", f"invalid JSON Feed: {exc}") from exc
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise AdapterError("parse", f"invalid XML feed: {exc}") from exc
    name = _local_name(root.tag).lower()
    if declared_format == "atom" or name == "feed":
        return _atom_entries(root)
    if declared_format == "rss" or name in {"rss", "rdf"}:
        return _rss_entries(root)
    raise AdapterError("parse", f"unsupported XML feed root: {name}")


def fetch_entries(
    subscription: dict[str, Any], state: dict[str, Any]
) -> tuple[FetchResult, list[DiscoveredEntry]]:
    """Fetch and parse entries for one validated P0 subscription."""

    kind = subscription["kind"]
    source_config = subscription["config"]
    if kind == "youtube_channel":
        url = youtube_feed_url(source_config["channel_id"])
        declared_format = "atom"
    elif kind == "feed":
        url = source_config["feed_url"]
        declared_format = source_config.get("format", "auto")
    else:
        raise AdapterError(
            "invalid_config", f"unsupported P0 subscription kind: {kind}"
        )
    result = fetch_public_feed(
        url,
        etag=state.get("etag", ""),
        last_modified=state.get("last_modified", ""),
        user_agent=(subscription.get("policy") or {}).get("user_agent", ""),
    )
    return result, [] if result.not_modified else parse_feed(
        result.body, declared_format=declared_format
    )
