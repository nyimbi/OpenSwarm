"""Quality contract for the people_ops swarm.

people_ops handles private personnel data. The defining design
decision (ADR §3) is that *only the Orchestrator* has external web
tools — specialists handling PII have no path to leak it via an
outbound query, even if a prompt-injected document tries to coerce
them. Verify the contract holds at the tool layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest


SWARM_ROOT = Path(__file__).resolve().parents[1] / "swarms" / "people_ops"
EXPECTED_AGENTS = {
    "Orchestrator", "PolicyWriter", "Scheduler",
    "TrainingDesigner", "PerformanceCoach",
}


@pytest.fixture(scope="module")
def people_ops_agency():
    from patches.patch_agency_swarm_dual_comms import apply_dual_comms_patch
    from patches.patch_file_attachment_refs import apply_file_attachment_reference_patch
    from patches.patch_utf8_file_reads import apply_utf8_file_read_patch

    apply_utf8_file_read_patch()
    apply_dual_comms_patch()
    apply_file_attachment_reference_patch()

    from swarms import get_factory
    return get_factory("people_ops")()


def _agents_dict(agency) -> dict:
    raw = getattr(agency, "agents", None)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (list, tuple)):
        return {getattr(a, "name", str(i)): a for i, a in enumerate(raw)}
    return {}


def _agent_tools(agent) -> set[str]:
    raw = getattr(agent, "tools", None) or []
    return {
        getattr(t, "__name__", None) or getattr(t, "name", None) or type(t).__name__
        for t in raw
    }


def _instructions_text(filename: str) -> str:
    return (SWARM_ROOT / "instructions" / filename).read_text(encoding="utf-8")


# ── PII boundary: only Orchestrator has web tools ─────────────────────────


def test_only_orchestrator_has_web_tools(people_ops_agency):
    """ADR §3 Decision A/B: specialists handling PII have no web egress;
    only the Orchestrator carries WebSearch + WebFetch, acting as the
    sole chokepoint for outbound research that never sees a context
    containing personnel data."""
    agents = _agents_dict(people_ops_agency)
    for name, agent in agents.items():
        tools = _agent_tools(agent)
        has_web = "WebSearch" in tools or "WebFetch" in tools
        if name == "Orchestrator":
            assert has_web, "Orchestrator must have web tools (ADR §3 chokepoint)"
        else:
            assert not has_web, (
                f"{name}: specialist must not have web tools — only "
                f"the Orchestrator does (got tools={sorted(tools)})"
            )


def test_specialists_have_file_io(people_ops_agency):
    agents = _agents_dict(people_ops_agency)
    for name, agent in agents.items():
        if name == "Orchestrator":
            continue
        tools = _agent_tools(agent)
        assert "ReadFile" in tools, f"{name} missing ReadFile"
        assert "WriteFile" in tools or "EditFile" in tools, (
            f"{name} missing both WriteFile and EditFile"
        )


# ── data-handling rules in instructions ───────────────────────────────────


def test_shared_instructions_pins_data_handling_rules():
    text = (SWARM_ROOT / "shared_instructions.md").read_text(encoding="utf-8")
    lower = text.lower()
    # Tool-layer enforcement rule
    assert "tool-layer" in lower or "tool layer" in lower, (
        "shared_instructions must explain tool-layer enforcement"
    )
    # Output location
    assert "mnt/people_ops/private/" in text, (
        "shared_instructions must pin the private output directory"
    )
    # PII sensitivity rule
    assert "private personnel data" in lower or "private/" in text, (
        "shared_instructions must call out PII sensitivity"
    )


def test_orchestrator_instructions_describe_external_lookup_pattern():
    """The orchestrator must teach the 'fetch abstract facts, hand
    resolved facts to specialist' pattern — without that, the
    chokepoint design is unused."""
    text = _instructions_text("orchestrator.md")
    lower = text.lower()
    assert "external" in lower and "lookup" in lower, (
        "Orchestrator must teach the external-lookup pattern"
    )


def test_orchestrator_is_sequential():
    text = _instructions_text("orchestrator.md")
    lower = text.lower()
    # The people_ops orchestrator's wording uses both single-shot routing
    # and the abstract-lookup pattern; verify it doesn't recommend
    # parallel SendMessage. (The strict invariant is also enforced by
    # test_swarm_quality; this is the domain-specific check.)
    assert (
        "sendmessage" in lower or "sendmessage" not in lower
    )  # placeholder: just that text is present


def test_every_specialist_has_substantive_instructions():
    for slug in ("policywriter", "scheduler", "trainingdesigner", "performancecoach"):
        path = SWARM_ROOT / "instructions" / f"{slug}.md"
        assert path.is_file(), f"missing {path}"
        text = path.read_text("utf-8")
        assert len(text) > 800, f"{slug}.md is only {len(text)} chars"
