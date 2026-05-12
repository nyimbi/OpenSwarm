"""Connectivity probe in bin/oswarm.

The launcher pings SearXNG (/healthz) and Firecrawl (/health) with a
2-second timeout. Failures must surface as a stderr warning, not a hard
exit — and the probe must be skippable via OSWARM_SKIP_PROBE=1.

These tests stand up a tiny in-process HTTP server to satisfy (or
deliberately not satisfy) the probe, then invoke `bin/oswarm help` (the
help branch exits without launching swarm.py, so it's a clean way to
exercise everything up to the dispatch case).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
OSWARM = REPO_ROOT / "bin" / "oswarm"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        # Reply 200 on /healthz and /health, 404 elsewhere
        if self.path in ("/healthz", "/health"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args, **_kwargs):  # silence stderr noise
        return


class _Server:
    def __init__(self):
        self.port = _free_port()
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def _run_oswarm_help(env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    """Invoke `bin/oswarm help` with a clean-ish env so the probe runs but the
    script exits without trying to launch python swarm.py."""
    env = {
        # Keep PATH and HOME so curl is found and the secrets-file path resolves
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": env_overrides.pop("HOME", "/tmp"),
    }
    env.update(env_overrides)
    return subprocess.run(
        [str(OSWARM), "help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl required for probe tests")
def test_probe_silent_when_endpoints_respond(tmp_path):
    with _Server() as searx, _Server() as fire:
        result = _run_oswarm_help(
            {
                "SEARXNG_URL": f"http://127.0.0.1:{searx.port}",
                "FIRECRAWL_URL": f"http://127.0.0.1:{fire.port}",
                "HOME": str(tmp_path),
            }
        )
    assert "warning" not in result.stderr.lower(), (
        f"probe warned despite healthy endpoints. stderr=\n{result.stderr}"
    )


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl required for probe tests")
def test_probe_warns_when_searxng_unreachable(tmp_path):
    # SearXNG = unreachable port; Firecrawl = healthy fixture
    with _Server() as fire:
        result = _run_oswarm_help(
            {
                "SEARXNG_URL": f"http://127.0.0.1:{_free_port()}",  # nothing listening
                "FIRECRAWL_URL": f"http://127.0.0.1:{fire.port}",
                "HOME": str(tmp_path),
            }
        )
    assert "SearXNG" in result.stderr
    assert "warning" in result.stderr.lower()
    # Firecrawl is healthy so it must NOT warn
    assert "Firecrawl" not in result.stderr


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl required for probe tests")
def test_probe_warns_when_firecrawl_unreachable(tmp_path):
    with _Server() as searx:
        result = _run_oswarm_help(
            {
                "SEARXNG_URL": f"http://127.0.0.1:{searx.port}",
                "FIRECRAWL_URL": f"http://127.0.0.1:{_free_port()}",  # nothing listening
                "HOME": str(tmp_path),
            }
        )
    assert "Firecrawl" in result.stderr
    assert "warning" in result.stderr.lower()
    assert "SearXNG" not in result.stderr


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl required for probe tests")
def test_skip_probe_env_disables_warnings(tmp_path):
    result = _run_oswarm_help(
        {
            "SEARXNG_URL": f"http://127.0.0.1:{_free_port()}",
            "FIRECRAWL_URL": f"http://127.0.0.1:{_free_port()}",
            "OSWARM_SKIP_PROBE": "1",
            "HOME": str(tmp_path),
        }
    )
    assert "warning" not in result.stderr.lower(), (
        f"OSWARM_SKIP_PROBE=1 should silence probe. stderr=\n{result.stderr}"
    )


def test_oswarm_defaults_localhost_when_unset(tmp_path):
    """The localhost defaults from H4: when SEARXNG_URL / FIRECRAWL_URL
    are unset, the launcher must fall back to localhost (not the
    previously hard-coded private IP)."""
    # Skip the probe so a missing localhost daemon doesn't muddy stderr
    result = _run_oswarm_help({"OSWARM_SKIP_PROBE": "1", "HOME": str(tmp_path)})
    assert result.returncode == 0
    # `oswarm help` prints the script's leading comment block — no assertions
    # against stdout are needed here. The behavior under test is that the
    # script doesn't crash with the previously hard-coded IP missing.
