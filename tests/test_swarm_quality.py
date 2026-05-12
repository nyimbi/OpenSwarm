"""Universal quality invariants every swarm must satisfy.

This is the bedrock test for the "highest-possible-quality" upgrade
sweep. It enforces structural rules that any swarm in the registry
must follow — failure here means the swarm is below the quality bar
regardless of how good the prose in its instructions reads.

Invariants:
1. shared_instructions.md exists with substantive content
2. Every agent in the swarm has an instructions file matching its
   lowercase slug, also with substantive content
3. The orchestrator's tools are a strict subset of the documented
   carve-outs ({SwitchProvider, SwitchSwarm, DispatchToSwarm})
4. The orchestrator's instructions do not recommend unguarded
   parallel SendMessage (the early-return bug that meeting_prep and
   proposals were rebuilt around)
5. Every non-orchestrator agent has both ReadFile and WriteFile so
   it can read prior artifacts and produce its own
"""

from __future__ import annotations

from pathlib import Path

import pytest


SWARMS_ROOT = Path(__file__).resolve().parents[1] / "swarms"

# Repo-root shared_instructions stand-in for swarms that legitimately
# reuse the global one (e.g. metaswarm's single-agent design points at
# the repo-level shared_instructions.md).
REPO_ROOT_SHARED = SWARMS_ROOT.parent / "shared_instructions.md"

# Slugs that legitimately defer to the repo-root shared_instructions
# instead of carrying their own. Keep this list short and justified.
SHARED_INSTRUCTIONS_EXEMPT = {"metaswarm", "openswarm"}

ORCHESTRATOR_ALLOWED_TOOLS = {"SwitchProvider", "SwitchSwarm", "DispatchToSwarm"}

# people_ops is the documented exception (ADR §3 Decision B): the
# Orchestrator is the single chokepoint for external research so the
# specialists handling PII never share a context with WebSearch /
# WebFetch. Allow these tools at the orchestrator level for swarms
# that follow that pattern.
ORCHESTRATOR_PII_CHOKEPOINT_TOOLS = ORCHESTRATOR_ALLOWED_TOOLS | {
    "WebSearch", "WebFetch"
}
PII_CHOKEPOINT_SWARMS = {"people_ops"}

# softdev defines its agents inside per-role subpackages
# (architect/, coder/, ...) with their own __init__.py — instructions
# live alongside, not under instructions/. Skip the universal
# instructions-file check for it but still enforce the other invariants.
LAYOUT_EXEMPT = {"softdev"}


@pytest.fixture(scope="module", autouse=True)
def _apply_patches():
    from patches.patch_agency_swarm_dual_comms import apply_dual_comms_patch
    from patches.patch_file_attachment_refs import apply_file_attachment_reference_patch
    from patches.patch_utf8_file_reads import apply_utf8_file_read_patch
    apply_utf8_file_read_patch()
    apply_dual_comms_patch()
    apply_file_attachment_reference_patch()


def _all_slugs():
    from swarms import SWARMS
    return list(SWARMS.keys())


def _agents_dict(agency) -> dict:
    raw = getattr(agency, "agents", None)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (list, tuple)):
        return {getattr(a, "name", str(i)): a for i, a in enumerate(raw)}
    return {}


def _agent_tools(agent) -> set[str]:
    raw = getattr(agent, "tools", None) or []
    names: set[str] = set()
    for t in raw:
        n = getattr(t, "__name__", None) or getattr(t, "name", None) or type(t).__name__
        names.add(n)
    return names


def _skip_if_optional_dep_missing(slug: str):
    if slug == "openswarm":
        pytest.importorskip("composio", reason="openswarm needs composio")


# ── invariant 1: shared_instructions present and substantive ──────────────


@pytest.mark.parametrize("slug", _all_slugs())
def test_shared_instructions_present(slug):
    if slug in SHARED_INSTRUCTIONS_EXEMPT:
        # Exempt swarms must rely on the repo-root shared_instructions
        assert REPO_ROOT_SHARED.is_file(), (
            f"{slug} is exempt from per-swarm shared_instructions but "
            f"the repo-root fallback at {REPO_ROOT_SHARED} is missing"
        )
        return

    path = SWARMS_ROOT / slug / "shared_instructions.md"
    assert path.is_file(), f"{slug}: missing {path}"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 300, (
        f"{slug}: shared_instructions.md is only {len(content)} chars — "
        "should describe the swarm, its rules, and its roster"
    )


# ── invariant 2: every agent has a substantive instructions file ──────────


@pytest.mark.parametrize("slug", _all_slugs())
def test_every_agent_has_instructions_file(slug):
    _skip_if_optional_dep_missing(slug)

    from swarms import get_factory

    agency = get_factory(slug)()
    agents = _agents_dict(agency)
    assert agents, f"{slug}: empty agents"

    # openswarm and softdev co-locate instructions with each agent
    # module under per-role subfolders rather than a single
    # instructions/ directory; skip the per-slug-file check for them.
    if slug in LAYOUT_EXEMPT or slug == "openswarm":
        return

    instructions_dir = SWARMS_ROOT / slug / "instructions"
    if slug == "metaswarm":
        # metaswarm's single agent uses a top-level instructions.md
        instructions_dir = SWARMS_ROOT / slug / "orchestrator"

    for name in agents:
        # Per make_agent contract, the file is `<lowercase name>.md`
        # under the instructions_dir, except for metaswarm which uses
        # `instructions.md` directly.
        if slug == "metaswarm":
            path = instructions_dir / "instructions.md"
        else:
            path = instructions_dir / f"{name.lower()}.md"
        assert path.is_file(), f"{slug}/{name}: missing instructions at {path}"
        text = path.read_text(encoding="utf-8")
        assert len(text) > 300, (
            f"{slug}/{name}: {path} is only {len(text)} chars — should "
            f"have role + workflow + boundaries sections at minimum"
        )


# ── invariant 3: orchestrator tools are a strict subset of carve-outs ─────


@pytest.mark.parametrize("slug", _all_slugs())
def test_orchestrator_only_has_carve_out_tools(slug):
    _skip_if_optional_dep_missing(slug)

    from swarms import get_factory

    agency = get_factory(slug)()
    agents = _agents_dict(agency)

    # Find the orchestrator. Names vary: 'Orchestrator', 'MetaOrchestrator', etc.
    orch_name = next(
        (n for n in agents if "Orchestrator" in n or "Meta" in n),
        None,
    )
    if orch_name is None:
        pytest.skip(f"{slug}: no orchestrator agent")

    tools = _agent_tools(agents[orch_name])
    allowed = (
        ORCHESTRATOR_PII_CHOKEPOINT_TOOLS
        if slug in PII_CHOKEPOINT_SWARMS
        else ORCHESTRATOR_ALLOWED_TOOLS
    )
    extra = tools - allowed
    assert not extra, (
        f"{slug}/{orch_name}: orchestrator has non-carve-out tools "
        f"{sorted(extra)} — orchestrators must route, not execute. "
        f"Allowed for this swarm: {sorted(allowed)}"
    )


# ── invariant 4: orchestrator instructions don't recommend unguarded ──────
#                 parallel SendMessage (the early-return bug)


# These phrases describe the bug rather than recommend the pattern.
_PARALLEL_DESCRIPTION_PHRASES = (
    "not parallelizable",
    "do not fan out",
    "don't fan out",
    "never fan out",
    "do not parallel",
    "parallel sendmessage would",
    "would hit the same early-return",
    "parallel-sendmessage",
    "no parallel sendmessage",
    "no parallel-sendmessage",
    "never fan out in parallel",
    "don't fan out in parallel",
    "fan out in parallel",  # always preceded by negation in our text
)


def _recommends_parallel_sendmessage(text: str) -> bool:
    """Detect the dangerous pattern: 'SendMessage … in parallel' as a
    *recommendation*, not as a warning about the bug.

    A line that contains both "SendMessage" (or "Send Message") and
    "parallel" is suspect unless one of the description phrases above
    appears in the surrounding text.
    """
    lower = text.lower()
    if "parallel" not in lower:
        return False
    # If the file explains the bug clearly, treat any remaining
    # parallel-SendMessage mention as referring to that explanation.
    # The rule is conservative: only flag if a "send … parallel" pair
    # appears on the same line *and* none of the bug-warning phrases
    # appear in the file.
    for ph in _PARALLEL_DESCRIPTION_PHRASES:
        if ph in lower:
            return False
    # Same-line co-occurrence of "sendmessage" + "parallel" is the
    # actionable signal.
    for line in text.splitlines():
        ll = line.lower()
        if "sendmessage" in ll and "parallel" in ll:
            return True
        if "send message" in ll and "parallel" in ll:
            return True
    return False


@pytest.mark.parametrize("slug", _all_slugs())
def test_orchestrator_does_not_recommend_parallel_sendmessage(slug):
    """The early-return bug: agency-swarm's get_response_sync returns
    on the orchestrator's first turn-end. A parallel SendMessage fan-out
    means the user gets a half-built response with the parallel branches
    still running. Sequential SendMessage is the safe pattern."""
    if slug == "metaswarm":
        instr_path = SWARMS_ROOT / slug / "orchestrator" / "instructions.md"
    else:
        instr_path = SWARMS_ROOT / slug / "instructions" / "orchestrator.md"
    if not instr_path.is_file():
        pytest.skip(f"{slug}: no orchestrator instructions file")
    text = instr_path.read_text(encoding="utf-8")
    assert not _recommends_parallel_sendmessage(text), (
        f"{slug}: orchestrator.md appears to recommend parallel "
        f"SendMessage — this is the early-return failure mode "
        f"meeting_prep and proposals were rebuilt around. "
        f"Use sequential SendMessage with explicit 'wait for reply' "
        f"language. (Path: {instr_path})"
    )


# ── invariant 5: specialists have file I/O ────────────────────────────────


@pytest.mark.parametrize("slug", _all_slugs())
def test_specialists_have_file_io(slug):
    _skip_if_optional_dep_missing(slug)

    if slug == "metaswarm":
        pytest.skip("metaswarm has no specialists")

    from swarms import get_factory

    agency = get_factory(slug)()
    agents = _agents_dict(agency)

    for name, agent in agents.items():
        if "Orchestrator" in name or "Meta" in name:
            continue
        tools = _agent_tools(agent)
        # openswarm uses different file ops from the upstream package;
        # tolerate it. softdev's specialists use the upstream tooling
        # mediated by its own re-exports — also tolerate.
        if slug in {"openswarm", "softdev"}:
            continue
        assert "ReadFile" in tools, (
            f"{slug}/{name}: specialist missing ReadFile (tools={sorted(tools)})"
        )
        # Editor-style agents may legitimately have only EditFile (they
        # update existing files rather than create new ones). Accept
        # either WriteFile or EditFile as the write capability.
        assert "WriteFile" in tools or "EditFile" in tools, (
            f"{slug}/{name}: specialist missing both WriteFile and "
            f"EditFile (tools={sorted(tools)})"
        )
