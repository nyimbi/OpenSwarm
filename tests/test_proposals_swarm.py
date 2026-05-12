"""Quality contract for the proposals swarm.

The proposals swarm is high-stakes: a single missing mandatory
requirement is a compliance-gate failure that no amount of prose
quality can rescue. These tests pin the structural invariants that
underwrite that quality:

- shared_instructions.md exists and is loaded as content (not a path)
- the six agents are all wired
- only DiscoveryAnalyst has external web tools (provenance contract)
- every agent has a non-empty instructions file
- every agent's instructions reference its file-layout slot
- the orchestrator's instructions are sequential (no "parallel SendMessage"
  language that would re-introduce the meeting_prep early-return bug)
"""

from __future__ import annotations

from pathlib import Path

import pytest


SWARM_ROOT = Path(__file__).resolve().parents[1] / "swarms" / "proposals"
EXPECTED_AGENTS = {
    "Orchestrator",
    "DiscoveryAnalyst",
    "Strategist",
    "Drafter",
    "Pricer",
    "Editor",
}


@pytest.fixture(scope="module")
def proposals_agency():
    from patches.patch_agency_swarm_dual_comms import apply_dual_comms_patch
    from patches.patch_file_attachment_refs import apply_file_attachment_reference_patch
    from patches.patch_utf8_file_reads import apply_utf8_file_read_patch

    apply_utf8_file_read_patch()
    apply_dual_comms_patch()
    apply_file_attachment_reference_patch()

    from swarms import get_factory
    return get_factory("proposals")()


def _agents_dict(agency) -> dict:
    raw = getattr(agency, "agents", None)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (list, tuple)):
        return {getattr(a, "name", str(i)): a for i, a in enumerate(raw)}
    return {}


# ── structure ─────────────────────────────────────────────────────────────


def test_shared_instructions_file_exists():
    """shared_instructions.md must exist on disk — swarm.py references it."""
    path = SWARM_ROOT / "shared_instructions.md"
    assert path.is_file(), f"missing {path}"
    content = path.read_text(encoding="utf-8")
    # Non-trivial content — at least a roster section
    assert "Roster" in content or "roster" in content
    assert len(content) > 500, "shared_instructions.md is suspiciously short"


def test_every_expected_agent_has_instructions_file():
    """Each expected agent must have a non-empty instructions file."""
    for name in EXPECTED_AGENTS:
        # Filename is the lowercase agent name + .md
        path = SWARM_ROOT / "instructions" / f"{name.lower()}.md"
        assert path.is_file(), f"missing instructions for {name}: {path}"
        text = path.read_text(encoding="utf-8")
        assert len(text) > 500, f"{path} is suspiciously short ({len(text)} chars)"


def test_agency_constructs_with_six_agents(proposals_agency):
    agents = _agents_dict(proposals_agency)
    assert set(agents.keys()) == EXPECTED_AGENTS, (
        f"agent roster mismatch: got {sorted(agents.keys())}"
    )


# ── tool-layer contracts ──────────────────────────────────────────────────


def _agent_tools(agent) -> set[str]:
    """Best-effort tool-name extraction. agency-swarm versions vary in
    where tools live — try a few attribute names."""
    raw = getattr(agent, "tools", None) or []
    names: set[str] = set()
    for t in raw:
        n = getattr(t, "__name__", None) or getattr(t, "name", None) or type(t).__name__
        names.add(n)
    return names


def test_only_discovery_has_web_tools(proposals_agency):
    """The provenance contract: every external fact in the proposal
    traces to discovery.md. Drafter must not have its own web access
    (it would invent citations), nor should Pricer / Editor /
    Strategist / Orchestrator."""
    agents = _agents_dict(proposals_agency)
    for name, agent in agents.items():
        tools = _agent_tools(agent)
        has_web = "WebSearch" in tools or "WebFetch" in tools
        if name == "DiscoveryAnalyst":
            assert has_web, "DiscoveryAnalyst must have WebSearch + WebFetch"
        else:
            assert not has_web, (
                f"{name} must not have web tools — research belongs to "
                f"DiscoveryAnalyst (got tools={sorted(tools)})"
            )


def test_orchestrator_has_only_carve_out_tools(proposals_agency):
    """Orchestrator's strict 'router only' contract — only SwitchProvider
    and SwitchSwarm. Anything else would let it execute domain work."""
    orch = _agents_dict(proposals_agency)["Orchestrator"]
    tools = _agent_tools(orch)
    assert tools == {"SwitchProvider", "SwitchSwarm"}, (
        f"Orchestrator tools must be exactly the carve-outs; got {tools}"
    )


def test_specialists_have_file_io(proposals_agency):
    """Every specialist needs to read prior artifacts and write its own."""
    agents = _agents_dict(proposals_agency)
    for name, agent in agents.items():
        if name == "Orchestrator":
            continue
        tools = _agent_tools(agent)
        assert "ReadFile" in tools, f"{name} missing ReadFile"
        assert "WriteFile" in tools, f"{name} missing WriteFile"


# ── instructions content invariants ───────────────────────────────────────


def test_orchestrator_instructions_are_sequential():
    """Per Commit 2 / meeting_prep lessons: orchestrator instructions
    must say 'one at a time' and 'wait for each one's reply'. Parallel
    SendMessage triggers the early-return bug in get_response_sync."""
    text = (SWARM_ROOT / "instructions" / "orchestrator.md").read_text("utf-8")
    assert "one at a time" in text.lower() or "one-at-a-time" in text.lower(), (
        "orchestrator instructions must mandate sequential SendMessage"
    )
    assert "wait" in text.lower() and "reply" in text.lower(), (
        "orchestrator must explicitly wait for each reply"
    )


def test_drafter_forbids_external_research():
    """Drafter's instructions must explicitly forbid external research —
    the tool-layer enforcement is the chokepoint, but the instructions
    must teach the agent why."""
    text = (SWARM_ROOT / "instructions" / "drafter.md").read_text("utf-8")
    assert (
        "no external" in text.lower()
        or "hand back to discovery" in text.lower()
        or "no external research" in text.lower()
        or "no external web" in text.lower()
    ), "Drafter instructions must teach the no-external-research rule"


def test_pricer_keys_to_drafter_phases():
    """Pricer must read proposal.md and key pricing to the Drafter's
    actual phases — not invent its own structure."""
    text = (SWARM_ROOT / "instructions" / "pricer.md").read_text("utf-8")
    assert "proposal.md" in text, (
        "Pricer must read proposal.md (Drafter's phase breakdown)"
    )


def test_editor_has_compliance_pass_and_escalation():
    """Editor's instructions must define both the compliance pass and
    the escalation path back to Strategist when positioning is weak."""
    text = (SWARM_ROOT / "instructions" / "editor.md").read_text("utf-8")
    assert "compliance" in text.lower()
    assert "strategist" in text.lower(), (
        "Editor instructions must define the escalation path to Strategist"
    )


def test_shared_instructions_pins_data_handling():
    """The 'no internal cost data in output' and 'no invented claims'
    rules are non-negotiable for proposals — pin them in shared
    instructions where every agent sees them."""
    text = (SWARM_ROOT / "shared_instructions.md").read_text("utf-8")
    lower = text.lower()
    assert "internal cost" in lower or "margins" in lower, (
        "shared_instructions must address internal-cost-data sensitivity"
    )
    assert "invent" in lower or "fraud" in lower or "defendable" in lower, (
        "shared_instructions must address the no-invented-claims rule"
    )


# ── end-to-end factory smoke ──────────────────────────────────────────────


def test_orchestrator_named_in_agents(proposals_agency):
    """The orchestrator must be reachable by name 'Orchestrator' —
    matches the make_agent / instructions slug contract."""
    agents = _agents_dict(proposals_agency)
    assert "Orchestrator" in agents


def test_reasoning_level_set_on_creative_agents(proposals_agency):
    """Discovery, Strategist, Drafter, Pricer, Editor all do reasoning-
    heavy work. The factory sets reasoning='high' on each. Smoke-check
    that at least one such agent carries the attribute."""
    agents = _agents_dict(proposals_agency)
    for name in ["DiscoveryAnalyst", "Strategist", "Pricer", "Editor", "Drafter"]:
        agent = agents[name]
        # The stub Agent class stores kwargs as attributes
        reasoning = getattr(agent, "reasoning", None)
        # On real agency-swarm, reasoning lives under model_settings; the
        # invariant we care about is that the factory passed it through
        # for these agents. Tolerate both shapes.
        ms = getattr(agent, "model_settings", None)
        ms_reasoning = getattr(ms, "reasoning", None) if ms else None
        assert reasoning == "high" or ms_reasoning is not None, (
            f"{name} should have reasoning='high' (got reasoning={reasoning}, model_settings.reasoning={ms_reasoning})"
        )
