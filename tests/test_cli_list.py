"""README ↔ registry parity (H3).

The README's "fleet" table is the user-facing claim about which swarms
exist and how many agents each has. The registry at `swarms/__init__.py`
is what the launcher and the live system actually run. These tests
enforce that those two surfaces agree.

When a swarm is added/removed or its agent count changes:
- update `swarms/__init__.py` (the registry)
- update README.md's fleet table
- update `EXPECTED_AGENT_COUNT` in tests/test_swarm_factories.py
- this test will fail until all three agree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def readme_table():
    """Parse the fleet table from README.md.

    Returns a dict {slug: (agent_count, description)} for every row.
    """
    text = README.read_text(encoding="utf-8")
    # The fleet table starts with the heading and ends at the next "##".
    fleet_match = re.search(
        r"## The fleet\s*\n(.+?)(?:\n##\s|\Z)", text, re.DOTALL
    )
    assert fleet_match, "could not find '## The fleet' section in README"
    body = fleet_match.group(1)

    # Match rows like `| \`slug\` | <count> | <description> |`
    row_re = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*(\d+)\s*\|\s*(.+?)\s*\|$", re.MULTILINE)
    rows = {m.group(1): (int(m.group(2)), m.group(3)) for m in row_re.finditer(body)}
    assert rows, "README fleet table parsed empty — check format"
    return rows


def test_readme_lists_every_registered_swarm(readme_table):
    from swarms import SWARMS

    readme_slugs = set(readme_table.keys())
    registry_slugs = set(SWARMS.keys())

    missing_from_readme = registry_slugs - readme_slugs
    extra_in_readme = readme_slugs - registry_slugs

    assert not missing_from_readme, (
        f"README fleet table missing rows for registered swarms: {sorted(missing_from_readme)}"
    )
    assert not extra_in_readme, (
        f"README fleet table has rows for unregistered swarms: {sorted(extra_in_readme)}"
    )


def test_readme_agent_counts_match_manifest(readme_table):
    """README's agent counts must equal the EXPECTED_AGENT_COUNT manifest,
    which itself is enforced against live factory output in
    test_swarm_factories.py."""
    from tests.test_swarm_factories import EXPECTED_AGENT_COUNT

    mismatches: list[tuple[str, int, int]] = []
    for slug, (readme_count, _desc) in readme_table.items():
        expected = EXPECTED_AGENT_COUNT.get(slug)
        if expected is None:
            continue
        if readme_count != expected:
            mismatches.append((slug, readme_count, expected))

    assert not mismatches, (
        "README ↔ manifest agent-count mismatch:\n"
        + "\n".join(
            f"  {slug}: README says {got}, manifest says {exp}"
            for slug, got, exp in mismatches
        )
    )


def test_readme_total_agent_count_matches_sum(readme_table):
    """The header claim "(N agents total)" must match the column sum."""
    text = README.read_text(encoding="utf-8")
    header = re.search(r"\((\d+)\s+agents total\)", text)
    assert header, "README missing '(N agents total)' header claim"
    claimed = int(header.group(1))

    column_sum = sum(count for count, _ in readme_table.values())
    assert claimed == column_sum, (
        f"README header claims {claimed} agents total, but the fleet "
        f"table column sums to {column_sum}."
    )
