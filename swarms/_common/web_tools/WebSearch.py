"""WebSearch — metasearch via SearXNG.

Aggregates results from multiple search engines (Google, Bing, DuckDuckGo,
Brave, Wikipedia) through a self-hosted SearXNG instance. Returns a clean
structured list of {title, url, snippet, engine, published_date}.

Configure via SEARXNG_URL env var. Defaults to http://localhost:8888 for
self-hosted dev. Falls back to a clear error if neither resolves.
"""

from __future__ import annotations

import os

import httpx
from agency_swarm.tools import BaseTool
from pydantic import Field


class WebSearch(BaseTool):
    """
    Search the web via SearXNG. Returns a list of relevant results with
    titles, URLs, and short content snippets. To read the full content
    of a returned result, follow up with WebFetch on its URL.

    Use this for: discovering sources for research, current events,
    library docs, finding examples or prior art. Don't use it to read
    a known URL — use WebFetch directly.
    """

    query: str = Field(
        ...,
        min_length=1,
        description="Search query. Plain text; no special operators required.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum number of results to return (1-30). Defaults to 10.",
    )
    time_range: str | None = Field(
        default=None,
        description=(
            "Recency filter: 'day', 'week', 'month', 'year'. Leave unset for "
            "no time filter."
        ),
    )
    engines: str | None = Field(
        default=None,
        description=(
            "Comma-separated list of engines to use, e.g. 'google,duckduckgo'. "
            "Leave unset for SearXNG defaults."
        ),
    )
    categories: str | None = Field(
        default=None,
        description=(
            "Search category: 'general', 'news', 'images', 'videos', 'science'. "
            "Leave unset for general."
        ),
    )

    def run(self) -> str:
        # NOTE: SEARXNG_URL should be https in shared deployments — when
        # the query body crosses a network boundary in plaintext, search
        # terms (and any sensitive context an agent may have folded into
        # them) leak to anything sniffing the link.
        base = os.environ.get("SEARXNG_URL", "http://localhost:8888").rstrip("/")
        params: dict[str, str] = {
            "q": self.query,
            "format": "json",
            # SearXNG's `count` is the per-engine result cap. Passing it
            # in lets the upstream stop early instead of fetching its
            # default 30+ per engine and us discarding the tail. The
            # client-side slice below stays as a guarantee.
            "count": str(self.limit),
        }
        if self.time_range:
            params["time_range"] = self.time_range
        if self.engines:
            params["engines"] = self.engines
        if self.categories:
            params["categories"] = self.categories

        try:
            response = httpx.get(f"{base}/search", params=params, timeout=20.0)
        except httpx.RequestError as exc:
            return (
                f"Error reaching SearXNG at {base}: {exc}. "
                "Set SEARXNG_URL to a reachable instance."
            )

        if response.status_code != 200:
            return (
                f"SearXNG returned HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError:
            return f"SearXNG returned non-JSON content: {response.text[:200]}"

        # Client-side clamp: SearXNG may still return more than `count`
        # if aggregating multiple engines. The slice keeps the output
        # bounded regardless of upstream behavior.
        results = data.get("results", [])[: self.limit]
        if not results:
            return f"No results for query: {self.query!r}"

        lines = [f"Search results for: {self.query!r}", ""]
        for i, r in enumerate(results, 1):
            title = r.get("title", "(no title)")
            url = r.get("url", "")
            snippet = (r.get("content") or "").strip()
            engine = r.get("engine", "")
            published = r.get("publishedDate") or ""
            meta = " · ".join(x for x in (engine, published) if x)
            lines.append(f"{i}. {title}")
            lines.append(f"   {url}")
            if snippet:
                # Clip snippets so a 10-result page stays scannable
                clipped = snippet[:300] + ("..." if len(snippet) > 300 else "")
                lines.append(f"   {clipped}")
            if meta:
                lines.append(f"   [{meta}]")
            lines.append("")

        return "\n".join(lines).rstrip()
