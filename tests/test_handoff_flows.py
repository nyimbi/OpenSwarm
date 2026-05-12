"""Edge preservation for the Commit 8 handoff dedup.

Before the dedup: every swarm built `send_message_flows` (orch→specialist)
*and* a full Cartesian `handoff_flows` (every pair, including
orch→specialist). The orchestrator-to-specialist edges existed twice,
once with the SendMessage tool class and once with the Handoff class —
not strictly broken (the dual_comms patch allows multiple classes per
pair), just wasteful.

After the dedup, `build_handoff_flows` drops handoff edges that are
already covered by SendMessage. The invariant enforced here:

    set(edges in send_message_flows ∪ post_handoff_flows)
        ==
    set(edges in send_message_flows ∪ naive_pre_handoff_flows)

i.e. the union of the topology is preserved — no edge silently dropped.

The Scenario 4 ADR concern was that an over-eager dedup could drop a
legitimately-handoff edge. The unit test below fires on hand-rolled
agent fixtures; an end-to-end fixture would have to reconstruct flows
from a built Agency, which agency-swarm already consumes and tosses.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from swarms._common.comms import build_handoff_flows, collect_edge_set


class _Agent:
    """Minimal agent-shape that supports the `a > b` overload via
    `__gt__` so we can exercise the helper without booting agency-swarm."""

    def __init__(self, name: str):
        self.name = name

    def __gt__(self, other: "_Agent"):
        return SimpleNamespace(sender_agent=self, receiver_agent=other)

    def __repr__(self):
        return f"_Agent({self.name!r})"


class _Handoff:
    """Sentinel tool class for the Handoff edges."""


def _naive_handoff_edges(agents) -> set[tuple[str, str]]:
    """The pre-dedup Cartesian-product edges (sender, receiver)."""
    return {(a.name, b.name) for a in agents for b in agents if a is not b}


def _make_swarm(n_specialists: int):
    orch = _Agent("Orchestrator")
    specialists = [_Agent(f"S{i}") for i in range(n_specialists)]
    agents = [orch, *specialists]
    sm_flows = [(orch, s, "SendMessage") for s in specialists]
    return agents, sm_flows


# ── core invariant ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 8])
def test_dedup_preserves_union(n):
    """The union of edges across SendMessage + dedup'd Handoff must
    equal the naive Cartesian-product set for any agent count."""
    agents, sm_flows = _make_swarm(n)
    handoff_flows = build_handoff_flows(agents, sm_flows, _Handoff)

    pre_edges = _naive_handoff_edges(agents)
    actual = collect_edge_set(sm_flows) | collect_edge_set(handoff_flows)
    assert actual == pre_edges, (
        f"n={n}: union mismatch\n  pre  : {sorted(pre_edges)}\n  post : {sorted(actual)}"
    )


def test_dedup_removes_only_send_message_overlap():
    """Edges that ARE in send_message_flows should not appear in
    handoff_flows. Edges that aren't covered must still appear."""
    agents, sm_flows = _make_swarm(3)
    handoff_flows = build_handoff_flows(agents, sm_flows, _Handoff)

    sm_edges = collect_edge_set(sm_flows)
    ho_edges = collect_edge_set(handoff_flows)
    assert sm_edges & ho_edges == set(), (
        "dedup should have removed SendMessage-covered edges from handoff"
    )


def test_dedup_handoff_count_is_naive_minus_sm():
    """Quantitative check: exactly (naive_count - sm_count) edges remain."""
    agents, sm_flows = _make_swarm(4)
    handoff_flows = build_handoff_flows(agents, sm_flows, _Handoff)

    n = len(agents)
    naive_count = n * (n - 1)  # Cartesian minus self-edges
    sm_count = len(sm_flows)
    assert len(handoff_flows) == naive_count - sm_count


def test_dedup_handoff_carries_handoff_class():
    """The tool class on every surviving edge must be the Handoff
    sentinel — not lost in the dedup."""
    agents, sm_flows = _make_swarm(3)
    handoff_flows = build_handoff_flows(agents, sm_flows, _Handoff)
    assert all(entry[1] is _Handoff for entry in handoff_flows)


# ── live registry: every swarm constructs cleanly post-dedup ───────────────


@pytest.fixture(scope="module", autouse=True)
def _apply_patches():
    from patches.patch_agency_swarm_dual_comms import apply_dual_comms_patch
    from patches.patch_file_attachment_refs import apply_file_attachment_reference_patch
    from patches.patch_utf8_file_reads import apply_utf8_file_read_patch
    apply_utf8_file_read_patch()
    apply_dual_comms_patch()
    apply_file_attachment_reference_patch()


def _all_swarm_slugs():
    from swarms import SWARMS
    return [s for s in SWARMS if s != "metaswarm"]  # metaswarm has no flows


@pytest.mark.parametrize("slug", _all_swarm_slugs())
def test_every_swarm_constructs_after_dedup(slug):
    """Smoke: every swarm's factory still constructs after Commit 8.
    The factory tests in test_swarm_factories cover this for free, but
    pinning it here makes the dedup change's blast-radius story
    obviously self-contained."""
    if slug == "openswarm":
        pytest.importorskip("composio", reason="openswarm requires Composio integrations")
    from swarms import get_factory
    agency = get_factory(slug)()
    assert agency is not None
