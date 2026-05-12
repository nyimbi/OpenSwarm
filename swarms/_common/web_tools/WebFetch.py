"""WebFetch — page scraping via Firecrawl.

Takes a URL, returns clean markdown of the main content. Handles
JavaScript-rendered pages because Firecrawl delegates to a headless
Chromium browser with stealth patches.

Configure via FIRECRAWL_URL env var. Defaults to http://localhost:3002.

Hardening (Commit 3 of ralplan-fix-all-issues):
- H1: SSRF guard. The target URL the agent passes in is resolved and
  rejected if it lands on a private/loopback/link-local/multicast/IMDS
  address. The Firecrawl endpoint itself stays unguarded — it commonly
  runs on a private network address.
- H2: response is streamed; a bytes cap of `max_chars * 4` protects
  against pathologically large pages.
- M7: split connect/read/write/pool timeouts so a slow body cannot
  hold the connection open forever.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
from urllib.parse import urlparse

import httpx
from agency_swarm.tools import BaseTool
from pydantic import Field


# Explicit deny — even when an address would otherwise pass the
# private/loopback heuristics, the AWS / GCP / Azure IMDS endpoint is
# the canonical SSRF target and gets its own line so the refusal
# message is unambiguous.
_IMDS_ADDRESS = "169.254.169.254"


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Return (True, "") if the URL targets a public host, else (False, reason).

    Resolves the hostname via getaddrinfo and inspects every returned
    address — DNS rebinding tricks that return one address for the guard
    and another for the actual request are mitigated because httpx is
    given the original URL and goes through the same resolver, but the
    guard already refuses if *any* resolved address is non-public.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"only http/https allowed (got {parsed.scheme or 'no scheme'!r})"
    host = parsed.hostname
    if not host:
        return False, "no hostname"

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return False, f"DNS resolution failed: {exc}"

    for family, _socktype, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        if ip_str == _IMDS_ADDRESS:
            return False, f"IMDS address {_IMDS_ADDRESS}"
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False, f"resolves to non-public address {ip}"

    return True, ""


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
        ok, reason = _is_safe_url(self.url)
        if not ok:
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

        try:
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
