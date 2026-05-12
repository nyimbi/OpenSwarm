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
    """Make httpx.get return a canned response."""
    import httpx
    monkeypatch.setattr(httpx, "get", lambda *_a, **_kw: _make_response(status, payload))


class _StreamCM:
    """Context-manager mimicking httpx.stream's response object."""

    def __init__(self, status: int, body: bytes, chunk_size: int = 8192):
        self.status_code = status
        self._body = body
        self._chunk_size = chunk_size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_bytes(self, chunk_size: int | None = None):
        size = max(chunk_size or self._chunk_size, 1)
        view = memoryview(self._body)
        for start in range(0, len(view), size):
            yield bytes(view[start : start + size])


def _stub_httpx_stream(monkeypatch, status: int, payload, *, chunk_size: int = 8192):
    """Replace httpx.stream with a context manager returning canned bytes."""
    import httpx

    if isinstance(payload, (dict, list)):
        body = json.dumps(payload).encode("utf-8")
    elif isinstance(payload, bytes):
        body = payload
    else:
        body = str(payload).encode("utf-8")

    monkeypatch.setattr(httpx, "stream", lambda *_a, **_kw: _StreamCM(status, body, chunk_size))


@pytest.fixture(autouse=True)
def _stub_dns_to_public(monkeypatch):
    """Pretend every hostname resolves to a public IP so the SSRF guard
    doesn't block tests that aren't specifically exercising it. Tests
    that DO exercise the SSRF guard override this with their own
    monkeypatch.setattr."""
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        # 93.184.216.34 is example.com's real public IP — a stable
        # choice that's unambiguously public.
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


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


def test_websearch_passes_limit_to_searxng(monkeypatch):
    """M4: WebSearch must pass `count=<limit>` to SearXNG so the upstream
    can stop early instead of fetching its default per-engine cap and us
    discarding the tail. The client-side slice still bounds the output."""
    monkeypatch.setenv("SEARXNG_URL", "http://stub:8888")

    captured: dict = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params", {})
        return _make_response(200, {"results": [
            {"title": f"r{i}", "url": f"https://e/{i}", "content": "x"}
            for i in range(5)
        ]})

    import httpx
    monkeypatch.setattr(httpx, "get", fake_get)

    WebSearch(query="x", limit=7).run()

    assert captured["params"].get("count") == "7", (
        f"WebSearch must send count={{limit}} to SearXNG; "
        f"got params={captured['params']}"
    )


def test_websearch_clamps_results_when_upstream_returns_more(monkeypatch):
    """Even with `count` sent upstream, the client-side slice must still
    enforce the limit — SearXNG aggregates across engines and can exceed
    its per-engine count when several reply at once."""
    monkeypatch.setenv("SEARXNG_URL", "http://stub:8888")
    _stub_httpx_get(
        monkeypatch,
        200,
        {"results": [
            {"title": f"r{i}", "url": f"https://e/{i}", "content": "x"}
            for i in range(20)  # upstream returns 20, we asked for 3
        ]},
    )
    out = WebSearch(query="x", limit=3).run()
    # 3 numbered entries; never a 4th
    assert "\n1. r0" in out and "\n3. r2" in out
    assert "4. r3" not in out


def test_webfetch_returns_markdown(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    _stub_httpx_stream(
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
    """Post-parse truncation kicks in when the markdown body itself is
    longer than max_chars but the wire response stays under the byte cap.

    Pick max_chars so that byte_cap (max_chars * 4) comfortably exceeds
    the encoded JSON envelope — otherwise the H2 cap would refuse the
    response before we ever get to truncate."""
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    long_md = "x" * 5000
    _stub_httpx_stream(
        monkeypatch,
        200,
        {"success": True, "data": {"markdown": long_md, "metadata": {"sourceURL": "https://example.com"}}},
    )
    # max_chars=2000 → byte_cap=8000, payload ~5.1KB, fits comfortably.
    out = WebFetch(url="https://example.com", max_chars=2000).run()
    assert "truncated at 2000 chars" in out
    assert "5000 chars" in out  # original length reported


def test_webfetch_handles_failed_scrape(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    _stub_httpx_stream(
        monkeypatch,
        200,
        {"success": False, "error": "robots.txt blocked"},
    )
    out = WebFetch(url="https://example.com").run()
    assert "Firecrawl failed" in out
    assert "robots.txt blocked" in out


def test_webfetch_handles_http_error(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")
    _stub_httpx_stream(monkeypatch, 408, "timeout")
    out = WebFetch(url="https://example.com").run()
    assert "HTTP 408" in out


def test_webfetch_validates_url():
    """Empty url, or url too short, should fail Pydantic validation."""
    with pytest.raises(Exception):
        WebFetch(url="")
    with pytest.raises(Exception):
        WebFetch(url="x")  # min_length=8


# ── H1: SSRF guard ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ip,reason_fragment",
    [
        ("127.0.0.1", "non-public"),
        ("169.254.169.254", "IMDS"),
        ("10.0.0.5", "non-public"),
        ("192.168.1.1", "non-public"),
        ("172.16.0.1", "non-public"),
        ("0.0.0.0", "non-public"),
        ("224.0.0.1", "non-public"),  # multicast
    ],
)
def test_webfetch_ssrf_blocks_non_public_target(monkeypatch, ip, reason_fragment):
    """The SSRF guard must refuse any target that resolves to a non-public
    address, well before any HTTP request is made."""
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port or 0))
        ],
    )

    # Sabotage httpx.stream so we can prove run() never reached it
    import httpx

    def fail(*_a, **_kw):
        raise AssertionError("SSRF guard did not refuse: httpx.stream was called")

    monkeypatch.setattr(httpx, "stream", fail)

    out = WebFetch(url=f"https://attacker.example/").run()
    assert "WebFetch refused" in out
    assert reason_fragment in out


def test_webfetch_ssrf_refuses_non_http_scheme(monkeypatch):
    """Only http/https are allowed; file://, ftp://, gopher:// are out."""
    import httpx

    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("scheme check should have blocked first")
    ))
    out = WebFetch(url="file:///etc/passwd").run()
    assert "refused" in out
    assert "http/https" in out


def test_webfetch_ssrf_refuses_url_with_no_host(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("host check should have blocked")
    ))
    # urlparse treats "https:///path" as hostname=""
    out = WebFetch(url="https:///path").run()
    assert "refused" in out


def test_webfetch_ssrf_blocks_ipv6_link_local_with_zone_id(monkeypatch):
    """IPv6 link-local addresses arrive from getaddrinfo with a zone ID
    suffix (`fe80::1%en0`). `ipaddress.ip_address` raises on that form,
    so the original guard silently dropped the entry on `continue` —
    the address was treated as safe. The reviewer-followup fix strips
    the zone ID before parsing."""
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *a, **kw: [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("fe80::1%en0", port or 0, 0, 0))
        ],
    )

    import httpx
    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("SSRF guard let through fe80:: link-local")
    ))

    out = WebFetch(url="https://attacker.example/").run()
    assert "refused" in out
    assert "fe80" in out or "link-local" in out or "non-public" in out


def test_webfetch_ssrf_blocks_ipv4_mapped_imds(monkeypatch):
    """`::ffff:169.254.169.254` is the same address as 169.254.169.254
    but the string-equality check used in the first pass missed it."""
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *a, **kw: [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "",
             ("::ffff:169.254.169.254", port or 0, 0, 0))
        ],
    )

    import httpx
    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("SSRF guard let through IPv4-mapped IMDS")
    ))

    out = WebFetch(url="https://attacker.example/").run()
    assert "refused" in out
    assert "IMDS" in out or "169.254.169.254" in out


def test_webfetch_pins_dns_for_request(monkeypatch):
    """The DNS-rebinding mitigation: after the guard validates the
    target host, any further `socket.getaddrinfo(host)` call (e.g.
    from httpx during connection setup) must return the pinned IP,
    not whatever the resolver feels like answering on second look."""
    import socket

    original_getaddrinfo = socket.getaddrinfo
    safe_ip = "93.184.216.34"
    call_count = {"n": 0}

    def flipping_resolver(host, port, *a, **kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Pretend the guard's first lookup returns the public IP
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (safe_ip, port or 0))]
        # On every subsequent lookup, the malicious resolver returns loopback
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", flipping_resolver)

    # Capture what httpx sees when it resolves
    seen_addrs: list[str] = []
    import httpx

    def stream(*_a, **_kw):
        # Simulate httpx's own DNS resolution inside its connection step
        infos = socket.getaddrinfo("attacker.example", 443)
        seen_addrs.append(infos[0][4][0])

        class _CM:
            status_code = 200

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def iter_bytes(self_inner):
                yield json.dumps({
                    "success": True,
                    "data": {
                        "markdown": "ok",
                        "metadata": {"sourceURL": "https://attacker.example"},
                    },
                }).encode()

        return _CM()

    monkeypatch.setattr(httpx, "stream", stream)

    WebFetch(url="https://attacker.example/").run()

    socket.getaddrinfo = original_getaddrinfo

    # Without pinning, the second resolution would return 127.0.0.1.
    # With pinning, httpx sees the safe IP the guard already validated.
    assert seen_addrs == [safe_ip], (
        f"DNS rebinding mitigation failed — httpx saw {seen_addrs}, "
        f"expected pinned IP {safe_ip!r}"
    )


def test_webfetch_firecrawl_localhost_allowed(monkeypatch):
    """The SSRF guard inspects the *target* URL — Firecrawl itself
    typically lives at localhost:3002 and must not be blocked."""
    monkeypatch.setenv("FIRECRAWL_URL", "http://localhost:3002")
    # Public DNS for the target URL is set by the autouse fixture.
    _stub_httpx_stream(
        monkeypatch,
        200,
        {"success": True, "data": {
            "markdown": "ok",
            "metadata": {"sourceURL": "https://example.com"}
        }},
    )
    out = WebFetch(url="https://example.com").run()
    assert "Fetched" in out


# ── H2: response-body cap ──────────────────────────────────────────────────


def test_webfetch_byte_cap_refuses_oversized_response(monkeypatch):
    """A pathologically large Firecrawl response is refused without
    being fully buffered into memory."""
    monkeypatch.setenv("FIRECRAWL_URL", "http://stub:3002")

    # max_chars=500 → byte_cap = 500 * 4 = 2000. Send 10_000 bytes.
    big = b"{" + b"\"x\":" + b"\"" + (b"A" * 10_000) + b"\"}"

    _stub_httpx_stream(monkeypatch, 200, big, chunk_size=256)
    out = WebFetch(url="https://example.com", max_chars=500).run()
    assert "exceeded" in out and "bytes" in out


# ── M7: split timeouts ────────────────────────────────────────────────────


def test_webfetch_uses_split_timeouts(monkeypatch):
    """The Timeout object passed to httpx.stream must be a per-phase
    httpx.Timeout — connect must be short so a dead Firecrawl fails fast."""
    import httpx

    captured: dict = {}

    def capture(*_args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")

        class _CM:
            status_code = 200

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def iter_bytes(self_inner):
                yield json.dumps({
                    "success": True,
                    "data": {
                        "markdown": "ok",
                        "metadata": {"sourceURL": "https://example.com"},
                    },
                }).encode()

        return _CM()

    monkeypatch.setattr(httpx, "stream", capture)
    WebFetch(url="https://example.com").run()

    timeout = captured["timeout"]
    assert isinstance(timeout, httpx.Timeout), (
        f"WebFetch must use httpx.Timeout, got {type(timeout)}"
    )
    # All four phases must be set independently
    assert timeout.connect == 5.0
    assert timeout.read == 60.0
    assert timeout.write == 10.0
    assert timeout.pool == 5.0


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
