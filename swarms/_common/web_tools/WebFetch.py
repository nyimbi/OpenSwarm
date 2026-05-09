"""WebFetch — page scraping via Firecrawl.

Takes a URL, returns clean markdown of the main content. Handles
JavaScript-rendered pages because Firecrawl delegates to a headless
Chromium browser with stealth patches.

Configure via FIRECRAWL_URL env var. Defaults to http://localhost:3002.
"""

from __future__ import annotations

import os

import httpx
from agency_swarm.tools import BaseTool
from pydantic import Field


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
        base = os.environ.get("FIRECRAWL_URL", "http://localhost:3002").rstrip("/")
        body: dict = {
            "url": self.url,
            "formats": ["markdown"],
            "onlyMainContent": self.only_main_content,
        }
        if self.wait_for:
            body["waitFor"] = self.wait_for

        try:
            response = httpx.post(
                f"{base}/v1/scrape",
                json=body,
                timeout=60.0,
            )
        except httpx.RequestError as exc:
            return (
                f"Error reaching Firecrawl at {base}: {exc}. "
                "Set FIRECRAWL_URL to a reachable instance."
            )

        if response.status_code != 200:
            return (
                f"Firecrawl returned HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError:
            return f"Firecrawl returned non-JSON: {response.text[:200]}"

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
