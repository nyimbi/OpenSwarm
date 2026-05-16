"""Quality contract for the finance swarm.

Highest-stakes sensitive-data swarm alongside people_ops. The contracts
that matter here are math-discipline (every figure traces to an
IPython cell) and PII discipline (no external research, all output
local).
"""

from __future__ import annotations

from pathlib import Path

import pytest


SWARM_ROOT = Path(__file__).resolve().parents[1] / "swarms" / "finance"
EXPECTED_AGENTS = {"Orchestrator", "DataLoader", "Analyst", "Modeler", "Reporter"}


@pytest.fixture(scope="module")
def finance_agency():
    from patches.patch_agency_swarm_dual_comms import apply_dual_comms_patch
    from patches.patch_file_attachment_refs import apply_file_attachment_reference_patch
    from patches.patch_utf8_file_reads import apply_utf8_file_read_patch

    apply_utf8_file_read_patch()
    apply_dual_comms_patch()
    apply_file_attachment_reference_patch()

    from swarms import get_factory
    return get_factory("finance")()


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


# ── PII discipline: no agent has WebSearch / WebFetch ─────────────────────


def test_no_finance_agent_has_web_tools(finance_agency):
    """The defining contract: WebSearch + WebFetch are not wired on
    ANY finance agent at construction time. Tool-layer enforcement
    of the data-handling rule from shared_instructions.md."""
    agents = _agents_dict(finance_agency)
    for name, agent in agents.items():
        tools = _agent_tools(agent)
        assert "WebSearch" not in tools, (
            f"{name}: has WebSearch — finance must be web-isolated at "
            f"the tool layer (no exceptions, including orchestrator)"
        )
        assert "WebFetch" not in tools, (
            f"{name}: has WebFetch — finance must be web-isolated at "
            f"the tool layer (no exceptions, including orchestrator)"
        )


# ── math discipline in instructions ───────────────────────────────────────


def _instructions_text(filename: str) -> str:
    return (SWARM_ROOT / "instructions" / filename).read_text(encoding="utf-8")


def test_dataloader_teaches_inspection_before_transform():
    text = _instructions_text("dataloader.md")
    lower = text.lower()
    assert "inspect" in lower or "before transforming" in lower, (
        "DataLoader must teach inspect-before-transform discipline"
    )


def test_analyst_teaches_no_numbers_from_memory():
    text = _instructions_text("analyst.md")
    lower = text.lower()
    assert (
        "every reported number" in lower
        or "every number" in lower
        or "from code" in lower
    ), "Analyst must teach the 'every number from code' rule"


def test_modeler_requires_explicit_assumptions():
    text = _instructions_text("modeler.md")
    lower = text.lower()
    assert "assumption" in lower
    assert "sensitivity" in lower, (
        "Modeler must teach sensitivity-analysis discipline"
    )


def test_reporter_forbids_new_figures():
    text = _instructions_text("reporter.md")
    lower = text.lower()
    assert "don't introduce new figures" in lower or "no new figures" in lower or (
        "every number cited is reported via the analyst or modeler" in lower
    ), (
        "Reporter must teach the no-new-figures rule (every number "
        "must come from Analyst or Modeler artifacts)"
    )


def test_orchestrator_is_sequential():
    """Already enforced by test_swarm_quality, but pin it here too —
    finance is high-stakes and a regression here would corrupt
    board-style reports silently."""
    text = _instructions_text("orchestrator.md")
    lower = text.lower()
    assert "one at a time" in lower or "sequential" in lower
    assert "wait" in lower and "reply" in lower


# ── output location discipline ────────────────────────────────────────────


def test_shared_instructions_pins_private_directory():
    text = (SWARM_ROOT / "shared_instructions.md").read_text(encoding="utf-8")
    assert "mnt/finance/private/" in text, (
        "shared_instructions must pin the private output directory"
    )
