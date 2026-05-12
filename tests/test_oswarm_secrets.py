"""Strict-secrets parser used by bin/oswarm.

Tests cover:
- accepts well-formed KEY=VALUE lines (with and without `export `)
- accepts quoted values, strips one matching pair of quotes
- rejects unsafe-shell substrings (command substitution, chaining, ...)
- rejects keys that don't match the uppercase-identifier shape
- tolerates comments and blank lines
- end-to-end: invoking the script with a file produces tab-separated stdout
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from swarms._common.secrets_parser import parse_secrets


def _parsed(text: str) -> dict[str, str]:
    return dict(parse_secrets(text.splitlines()))


# ── shape acceptance ───────────────────────────────────────────────────────


def test_accepts_simple_key_value():
    assert _parsed("OPENAI_API_KEY=sk-test") == {"OPENAI_API_KEY": "sk-test"}


def test_accepts_export_prefix():
    assert _parsed("export OPENAI_API_KEY=sk-test") == {"OPENAI_API_KEY": "sk-test"}


def test_strips_matching_double_quotes():
    assert _parsed('OPENAI_API_KEY="sk-test"') == {"OPENAI_API_KEY": "sk-test"}


def test_strips_matching_single_quotes():
    assert _parsed("OPENAI_API_KEY='sk-test'") == {"OPENAI_API_KEY": "sk-test"}


def test_preserves_mismatched_quotes_as_literal():
    """A leading quote without a matching trailer is part of the value."""
    out = _parsed('OPENAI_API_KEY="dangling')
    assert out == {"OPENAI_API_KEY": '"dangling'}


def test_accepts_underscore_leading_key():
    assert _parsed("_INTERNAL=1") == {"_INTERNAL": "1"}


def test_tolerates_blank_lines_and_comments():
    text = "\n# top comment\n\nFOO=1\n  # indented comment\nBAR=2\n"
    assert _parsed(text) == {"FOO": "1", "BAR": "2"}


# ── shape rejection ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "line",
    [
        "lowercase=nope",
        "1STARTS_WITH_DIGIT=nope",
        "HAS-DASH=nope",
        "HAS SPACE=nope",
        "NO_VALUE_NO_EQUAL",
        "=missing_key",
    ],
)
def test_rejects_malformed_keys(line):
    assert _parsed(line) == {}


@pytest.mark.parametrize(
    "value",
    [
        "$(curl https://evil)",
        "`whoami`",
        "harmless;rm -rf /",
        "ok && evil",
        "ok || evil",
    ],
)
def test_rejects_unsafe_value_substrings(value):
    assert _parsed(f"OPENAI_API_KEY={value}") == {}


def test_embedded_newline_in_single_chunk_is_rejected():
    """If a caller passes a chunk that contains a raw newline (not split
    into lines yet), the parser must refuse — the newline is the chief
    multi-line injection vector."""
    assert list(parse_secrets(["KEY=safe\nINJECTED=value"])) == []


# ── script entry point ────────────────────────────────────────────────────


def test_script_emits_tab_separated_pairs(tmp_path):
    env = tmp_path / "api_keys.env"
    env.write_text(
        "# header comment\n"
        "export OPENAI_API_KEY=sk-real\n"
        "AZURE_API_BASE=https://example.openai.azure.com\n"
        "evil=$(rm -rf /)\n"
        "FOO=bar=baz\n",  # legitimate value containing '='
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[1] / "swarms" / "_common" / "secrets_parser.py"
    result = subprocess.run(
        [sys.executable, str(script), str(env)],
        capture_output=True,
        text=True,
        check=True,
    )
    pairs = dict(line.split("\t", 1) for line in result.stdout.strip().splitlines())
    assert pairs == {
        "OPENAI_API_KEY": "sk-real",
        "AZURE_API_BASE": "https://example.openai.azure.com",
        "FOO": "bar=baz",
    }


def test_script_missing_file_exits_non_zero(tmp_path):
    script = Path(__file__).resolve().parents[1] / "swarms" / "_common" / "secrets_parser.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "nope.env")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "not found" in result.stderr


# ── end-to-end: bin/oswarm exports the right vars ──────────────────────────


def test_oswarm_launcher_exports_parsed_secrets(tmp_path, monkeypatch):
    """Run `bin/oswarm help` with HOME pointing at a fixture containing
    a mix of safe and unsafe lines. The help branch never reaches python,
    so we instead test the parser-stage by sourcing the parsing block
    manually via a small test driver."""
    repo_root = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    secrets_dir = home / ".config" / "secrets"
    secrets_dir.mkdir(parents=True)
    secrets_file = secrets_dir / "api_keys.env"
    secrets_file.write_text(
        "GOOD_KEY=good-value\n"
        "BAD_KEY=$(curl https://evil)\n"
        "export QUOTED='with spaces'\n",
        encoding="utf-8",
    )

    driver = tmp_path / "driver.sh"
    driver.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="{repo_root}"
SECRETS="{secrets_file}"
while IFS=$'\\t' read -r _key _value; do
  [[ -n "$_key" ]] && export "$_key=$_value"
done < <(python3 "${{REPO_ROOT}}/swarms/_common/secrets_parser.py" "$SECRETS")
echo "GOOD_KEY=${{GOOD_KEY:-MISSING}}"
echo "BAD_KEY=${{BAD_KEY:-MISSING}}"
echo "QUOTED=${{QUOTED:-MISSING}}"
""",
        encoding="utf-8",
    )
    driver.chmod(0o755)

    result = subprocess.run(["bash", str(driver)], capture_output=True, text=True, check=True)
    lines = dict(line.split("=", 1) for line in result.stdout.strip().splitlines())
    assert lines["GOOD_KEY"] == "good-value"
    assert lines["BAD_KEY"] == "MISSING", "unsafe value leaked into env"
    assert lines["QUOTED"] == "with spaces"
