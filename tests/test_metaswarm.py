"""Quality contract for the metaswarm front-door.

metaswarm has a single agent (MetaOrchestrator) and no domain
specialists; its quality is entirely a function of how clearly the
orchestrator's instructions teach the routing decision. The contracts
that matter:

- the fleet table covers every registered non-metaswarm swarm
- the dispatch-vs-switch decision rule is explicit
- sensitive-data routing is called out (finance / people_ops)
- the orchestrator never executes domain work itself
"""

from __future__ import annotations

import re
from pathlib import Path


INSTR = (
    Path(__file__).resolve().parents[1]
    / "swarms"
    / "metaswarm"
    / "orchestrator"
    / "instructions.md"
)


def _table_slugs() -> set[str]:
    text = INSTR.read_text(encoding="utf-8")
    # Match rows like `| \`slug\` | description |`
    return set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", text, re.MULTILINE))


def test_fleet_table_covers_every_registered_swarm():
    from swarms import SWARMS

    table_slugs = _table_slugs()
    expected = set(SWARMS) - {"metaswarm"}  # metaswarm doesn't list itself
    missing = expected - table_slugs
    assert not missing, (
        f"metaswarm fleet table missing rows for: {sorted(missing)}. "
        f"Update swarms/metaswarm/orchestrator/instructions.md"
    )


def test_dispatch_vs_switch_rule_is_explicit():
    text = INSTR.read_text(encoding="utf-8").lower()
    assert "dispatchtoswarm" in text
    assert "switchswarm" in text
    # The decision rule appears in some form
    assert "dispatch" in text and "switch" in text
    assert "discrete" in text or "completable" in text or "one pass" in text


def test_sensitive_data_routing_called_out():
    text = INSTR.read_text(encoding="utf-8").lower()
    assert "private" in text and ("financial" in text or "hr" in text or "personnel" in text), (
        "metaswarm must explicitly call out sensitive-data routing to "
        "finance / people_ops rather than generic content swarms"
    )


def test_orchestrator_never_executes_domain_work():
    text = INSTR.read_text(encoding="utf-8").lower()
    assert "never" in text and ("execute" in text or "domain work" in text or "routes" in text), (
        "metaswarm must explicitly state the 'never execute domain "
        "work' contract"
    )


def test_clarification_path_exists():
    """When the request is ambiguous, the orchestrator must ask one
    clarifying question, not dispatch blindly. Sub-swarm runs cost
    tokens — a bad route is expensive."""
    text = INSTR.read_text(encoding="utf-8").lower()
    assert "ambiguous" in text or "clarify" in text or "clarifying" in text


def test_administrative_carve_outs_documented():
    text = INSTR.read_text(encoding="utf-8")
    assert "SwitchProvider" in text
    assert "SwitchSwarm" in text
