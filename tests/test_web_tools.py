"""WebSearch + WebFetch — verifies plumbing without hitting real servers.

Uses pytest's monkeypatch to stub httpx so the tests run anywhere with
no network. Also includes one round-trip test against a real SearXNG /
Firecrawl pair, gated by the SEARXNG_URL / FIRECRAWL_URL env vars (skipped
otherwise — same opt-in pattern as test_live_providers.py).
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from swarms._common.web_tools import WebSearch, WebFetch


# ── plumbing tests (no network) ────────────────────────────────────────────


def _make_response(status: int, payload):
    text = json.dumps(payload) if isinstance(payload, dict) else payload
    if isinstance(payload, dict):
        json_fn = lambda: payload
    else:
        def _raise():
            raise ValueError("not json")
        json_fn = _raise
    return SimpleNamespace(status_code=status, text=text, json=json_fn)


def _stub_httpx_get(monkeypatch, status: int, payload):
    """Make httpx.get return a canned response. Patches the httpx module
    directly (importlib is the indirection — package __init__.py re-exports
    the class under the same dotted path as the submodule, so importing
    the module by name resolves to the class)."""
    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _make_response(status, payload))


def _stub_httpx_post(monkeypatch, status: int, payload):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _make_response(status, payload))


def test_websearch_returns_structured_results(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://stub:8888")
    _stub_httpx_get(
        monkeypatch,
        200,
        {
            "results": [
                {
                    "title": "Example Result",
                    "url": "https://example.com/foo",
                    "content": "A snippet about foo.",
                    "engine": "wikipedia",
                    "publishedDate": "2026-03-01",
                },
                {
                    "title": "Other Result",
                    "url": "https://example.com/bar",
                    "content": "A snippet about bar.",
                    "engine": "google",
                },
            ]
        },
    )
    out = WebSearch(query="foo").run()
    assert "Example Result" in out
    assert "https://example.com/foo" in out
    assert "Other Result" in out
    assert "wikipedia" in out


def test_websearch_handles_no_results(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://stub:8888")
    _stub_httpx_get(monkeypatch, 200, {"results": []})
    out = WebSearch(query="nothing matches this").run()
    assert "No results" in out


def test_websearch_handles_http_error(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://stub:8888")
    _stub_httpx_get(monkeypatch, 500, "Internal Server Error")
    out = WebSearch(query="anything").run()
    assert "HTTP 500" in out


def test_websearch_handles_connection_error(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://stub:8888")
    import httpx

    def raise_request_error(*args, **kwargs):
        raise httpx.RequestError("connection refused")

    monkeypatch.setattr(httpx, "get", raise_request_error)
    out = WebSearch(query="anything").run()
    assert "Error reaching SearXNG" in out
    assert "connection refused" in out


def test_websearch_clamps_limit():
    """Pydantic should reject limits outside [1, 30]."""
    with pytest.raises(Exception):
        WebSearch(query="x", limit=0)
    with pytest.raises(Exception):
        WebSearch(query="x", limit=100)


def test_webfetch_returns_markdown(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    _stub_httpx_post(
        monkeypatch,
        200,
        {
            "success": True,
            "data": {
                "markdown": "# Page Title\n\nContent here.",
                "metadata": {
                    "title": "Page Title",
                    "sourceURL": "https://example.com/page",
                },
            },
        },
    )
    out = WebFetch(url="https://example.com/page").run()
    assert "Fetched: https://example.com/page" in out
    assert "Page Title" in out
    assert "Content here." in out


def test_webfetch_truncates_long_content(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    long_md = "x" * 5000
    _stub_httpx_post(
        monkeypatch,
        200,
        {"success": True, "data": {"markdown": long_md, "metadata": {"sourceURL": "https://example.com"}}},
    )
    out = WebFetch(url="https://example.com", max_chars=1000).run()
    assert "truncated at 1000 chars" in out
    assert "5000 chars" in out  # original length reported


def test_webfetch_handles_failed_scrape(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    _stub_httpx_post(
        monkeypatch,
        200,
        {"success": False, "error": "robots.txt blocked"},
    )
    out = WebFetch(url="https://example.com").run()
    assert "Firecrawl failed" in out
    assert "robots.txt blocked" in out


def test_webfetch_handles_http_error(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    _stub_httpx_post(monkeypatch, 408, "timeout")
    out = WebFetch(url="https://example.com").run()
    assert "HTTP 408" in out


def test_webfetch_validates_url():
    """Empty url, or url too short, should fail Pydantic validation."""
    with pytest.raises(Exception):
        WebFetch(url="")
    with pytest.raises(Exception):
        WebFetch(url="x")  # min_length=8


# ── live tests (opt-in via env vars; skipped by default) ────────────────────


@pytest.mark.live
def test_websearch_live():
    if not os.environ.get("SEARXNG_URL"):
        pytest.skip("SEARXNG_URL not set")
    out = WebSearch(query="python", limit=3).run()
    # Either succeeds with results or fails with the connection-error path,
    # but must not crash. SearXNG sometimes returns 0 results when all
    # engines are rate-limited; that's an "operational" success not a bug.
    assert isinstance(out, str) and out.strip()


@pytest.mark.live
def test_webfetch_live():
    if not os.environ.get("FIRECRAWL_URL"):
        pytest.skip("FIRECRAWL_URL not set")
    out = WebFetch(url="https://example.com", max_chars=2000).run()
    assert isinstance(out, str) and out.strip()
