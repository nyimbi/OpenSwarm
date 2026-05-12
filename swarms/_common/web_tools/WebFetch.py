"""WebFetch — page scraping via Firecrawl.

Takes a URL, returns clean markdown of the main content. Handles
JavaScript-rendered pages because Firecrawl delegates to a headless
Chromium browser with stealth patches.

Configure via FIRECRAWL_URL env var. Defaults to http://localhost:3002.

Hardening (Commit 3 of ralplan-fix-all-issues + reviewer follow-up):
- H1: SSRF guard. The target URL the agent passes in is resolved and
  rejected if it lands on a private/loopback/link-local/multicast/IMDS
  address. The Firecrawl endpoint itself stays unguarded — it commonly
  runs on a private network address.
- H1 reviewer follow-up: DNS rebinding is mitigated by pinning the
  hostname to its first safe-resolved address for the duration of the
  request (monkeypatching `socket.getaddrinfo` inside a context
  manager). Without this, a hostile authoritative resolver could
  answer once with a public IP for the guard, then with 127.0.0.1 for
  httpx's own resolution.
- H1 reviewer follow-up: IPv6 zone IDs (`fe80::1%en0`) are stripped
  before parsing; otherwise `ipaddress.ip_address` would raise and the
  guard would `continue`, silently allowing the link-local address.
- H1 reviewer follow-up: IPv4-mapped IPv6 forms of the IMDS address
  (`::ffff:169.254.169.254`) are now caught.
- H2: response is streamed; a bytes cap of `max_chars * 4` protects
  against pathologically large pages.
- M7: split connect/read/write/pool timeouts so a slow body cannot
  hold the connection open forever.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import socket
from typing import Iterator
from urllib.parse import urlparse

import httpx
from agency_swarm.tools import BaseTool
from pydantic import Field


# Explicit deny — even when an address would otherwise pass the
# private/loopback heuristics, the AWS / GCP / Azure IMDS endpoint is
# the canonical SSRF target and gets its own line so the refusal
# message is unambiguous.
_IMDS_ADDRESS = "169.254.169.254"


def _canonical_ip(ip_str: str) -> ipaddress._BaseAddress | None:
    """Parse `ip_str` into an ipaddress object, stripping IPv6 zone IDs.

    IPv6 link-local addresses returned by getaddrinfo include the
    interface zone (`fe80::1%en0`). `ipaddress.ip_address` raises on
    that form, so the original guard silently dropped these.
    """
    bare = ip_str.split("%", 1)[0]
    try:
        return ipaddress.ip_address(bare)
    except ValueError:
        return None


def _classify_address(ip: ipaddress._BaseAddress) -> str:
    """Return a refusal-reason string if `ip` is non-public, else ""."""
    # Unwrap IPv4-mapped IPv6 so the v4 classification rules apply
    # (e.g. `::ffff:169.254.169.254` must still be caught as IMDS).
    check = getattr(ip, "ipv4_mapped", None) or ip
    if str(check) == _IMDS_ADDRESS:
        return f"IMDS address {_IMDS_ADDRESS}"
    if (
        check.is_private
        or check.is_loopback
        or check.is_link_local
        or check.is_reserved
        or check.is_multicast
        or check.is_unspecified
    ):
        return f"resolves to non-public address {check}"
    return ""


def _resolve_safe(host: str) -> tuple[str, str]:
    """Resolve `host` and return (safe_ip, "") or ("", reason).

    Walks every getaddrinfo entry and rejects on the first non-public
    address. Returns the first safe IPv4/IPv6 literal so the caller can
    pin DNS for the actual request — mitigating the DNS rebinding race
    between the guard's resolution and httpx's.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return "", f"DNS resolution failed: {exc}"

    safe_ip = ""
    for _f, _s, _p, _c, sockaddr in infos:
        ip = _canonical_ip(sockaddr[0])
        if ip is None:
            continue
        bad = _classify_address(ip)
        if bad:
            return "", bad
        if not safe_ip:
            safe_ip = sockaddr[0].split("%", 1)[0]

    if not safe_ip:
        return "", "no resolvable public addresses"
    return safe_ip, ""


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Return (True, "") if the URL targets a public host, else (False, reason).

    This is the public surface preserved for compatibility — internal
    callers prefer `_resolve_safe()` which also returns the pinned IP.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"only http/https allowed (got {parsed.scheme or 'no scheme'!r})"
    host = parsed.hostname
    if not host:
        return False, "no hostname"
    _ip, reason = _resolve_safe(host)
    if reason:
        return False, reason
    return True, ""


@contextlib.contextmanager
def _pin_dns(host: str, pinned_ip: str) -> Iterator[None]:
    """Monkeypatch socket.getaddrinfo so any resolution of `host` returns
    `pinned_ip` for the duration of the with-block.

    This closes the DNS rebinding race: between the SSRF guard's
    resolution and httpx's, a hostile authoritative resolver could
    have flipped the answer from public IP to loopback. With the pin
    in place, httpx sees exactly the address the guard already
    validated.

    Resolutions for any *other* hostname pass through to the real
    resolver — Firecrawl traffic is unaffected.
    """
    original = socket.getaddrinfo

    def pinned(h, port, *args, **kwargs):
        if h == host:
            # Prefer the right family for the pinned IP
            try:
                ip_obj = ipaddress.ip_address(pinned_ip)
            except ValueError:
                return original(h, port, *args, **kwargs)
            family = socket.AF_INET6 if ip_obj.version == 6 else socket.AF_INET
            return [(family, socket.SOCK_STREAM, 0, "", (pinned_ip, port or 0))]
        return original(h, port, *args, **kwargs)

    socket.getaddrinfo = pinned
    try:
        yield
    finally:
        socket.getaddrinfo = original


class WebFetch(BaseTool):
    """
    Fetch a URL and return its content as clean markdown.

    Use this when you have a specific URL (e.g. from WebSearch results,
    a link the user gave you, or a known docs page) and need to read what's
    on it. Strips navigation/footer/sidebar by default to keep the content
    focused.

    The output is truncated if the page is very long — set `max_chars` to
    increase the cap (defaults to 20,000 characters).
    """

    url: str = Field(
        ...,
        min_length=8,
        description="HTTP(S) URL to fetch. Must include the scheme.",
    )
    only_main_content: bool = Field(
        default=True,
        description=(
            "Strip navs, footers, sidebars before returning. Set False when "
            "you specifically want the surrounding chrome (rare)."
        ),
    )
    wait_for: int = Field(
        default=0,
        ge=0,
        le=15000,
        description=(
            "Milliseconds to wait after page load for JS-rendered content "
            "to settle. Increase to 2000-5000 for SPA / React pages."
        ),
    )
    max_chars: int = Field(
        default=20000,
        ge=500,
        le=200000,
        description="Cap on returned markdown length. Default 20k chars.",
    )

    def run(self) -> str:
        # H1: SSRF guard runs first so a refused URL never touches the
        # Firecrawl endpoint at all.
        parsed = urlparse(self.url)
        if parsed.scheme not in ("http", "https"):
            return (
                f"WebFetch refused {self.url}: target resolves to non-public "
                f"address (only http/https allowed (got "
                f"{parsed.scheme or 'no scheme'!r}))."
            )
        host = parsed.hostname
        if not host:
            return (
                f"WebFetch refused {self.url}: target resolves to non-public "
                f"address (no hostname)."
            )
        pinned_ip, reason = _resolve_safe(host)
        if reason:
            return (
                f"WebFetch refused {self.url}: target resolves to non-public "
                f"address ({reason})."
            )

        base = os.environ.get("FIRECRAWL_URL", "http://localhost:3002").rstrip("/")
        body: dict = {
            "url": self.url,
            "formats": ["markdown"],
            "onlyMainContent": self.only_main_content,
        }
        if self.wait_for:
            body["waitFor"] = self.wait_for

        # M7: split timeouts. A slow body must not hold the connection
        # forever; a slow connect must fail fast so the agent can move on.
        timeout = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

        # H2: stream the response and cap accumulation at max_chars * 4
        # bytes. JSON parsing happens after the body is fully collected
        # (or capped), so a pathological Firecrawl response cannot
        # exhaust memory.
        byte_cap = self.max_chars * 4
        body_chunks: list[bytes] = []
        total = 0
        truncated_at_cap = False
        status_code: int | None = None

        # H1 (DNS rebinding mitigation): pin the target hostname to the
        # resolved-safe IP for the duration of the request. Firecrawl's
        # own hostname is unaffected — the pin only intercepts lookups
        # for `host`. The pin guarantees httpx sees exactly the address
        # the guard already validated.
        try:
            with _pin_dns(host, pinned_ip):
                with httpx.stream(
                    "POST",
                    f"{base}/v1/scrape",
                    json=body,
                    timeout=timeout,
                ) as response:
                    status_code = response.status_code
                    for chunk in response.iter_bytes():
                        body_chunks.append(chunk)
                        total += len(chunk)
                        if total > byte_cap:
                            truncated_at_cap = True
                            break
        except httpx.RequestError as exc:
            return (
                f"Error reaching Firecrawl at {base}: {exc}. "
                "Set FIRECRAWL_URL to a reachable instance."
            )

        if status_code != 200:
            preview = b"".join(body_chunks)[:200].decode("utf-8", errors="replace")
            return f"Firecrawl returned HTTP {status_code}: {preview}"

        if truncated_at_cap:
            return (
                f"Firecrawl response exceeded {byte_cap} bytes for {self.url} "
                f"and was refused. Re-fetch with a smaller scope (lower "
                f"wait_for, more specific URL) or raise max_chars."
            )

        raw = b"".join(body_chunks)
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except (ValueError, UnicodeDecodeError):
            preview = raw[:200].decode("utf-8", errors="replace")
            return f"Firecrawl returned non-JSON: {preview}"

        if not data.get("success", False):
            err = data.get("error") or "unknown error"
            return f"Firecrawl failed for {self.url}: {err}"

        payload = data.get("data", {})
        markdown = (payload.get("markdown") or "").strip()
        if not markdown:
            return f"Firecrawl returned no content for {self.url}."

        meta = payload.get("metadata", {}) or {}
        title = meta.get("title") or ""
        source = meta.get("sourceURL") or self.url

        head_lines = [f"# Fetched: {source}"]
        if title and title.lower() != source.lower():
            head_lines.append(f"Title: {title}")
        head = "\n".join(head_lines)

        if len(markdown) > self.max_chars:
            cut = markdown[: self.max_chars]
            footer = (
                f"\n\n... [truncated at {self.max_chars} chars; "
                f"original length {len(markdown)} chars. "
                "Re-fetch with a larger max_chars if needed.]"
            )
            return f"{head}\n\n{cut}{footer}"

        return f"{head}\n\n{markdown}"
