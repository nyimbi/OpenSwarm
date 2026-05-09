"""Cross-swarm web tooling: WebSearch (SearXNG) + WebFetch (Firecrawl).

Replaces openai-agents-sdk's WebSearchTool, which only works through the
hosted Responses API and fails on every LiteLLM-routed provider (Azure,
Anthropic, Ollama, ...). These tools are plain HTTP wrappers that work
with any model and any provider.

Configure via env vars:
- SEARXNG_URL    — base URL of a SearXNG instance (e.g. http://host:8888)
- FIRECRAWL_URL  — base URL of a Firecrawl instance (e.g. http://host:3002)

Both default to localhost for self-hosted dev. If unset, the tools return
a clear error rather than failing cryptically.
"""

from swarms._common.web_tools.WebSearch import WebSearch
from swarms._common.web_tools.WebFetch import WebFetch

__all__ = ["WebSearch", "WebFetch"]
