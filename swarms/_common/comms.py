"""Shared communication-topology helpers.

Every swarm in this repo builds a topology where the Orchestrator has
SendMessage flows to its specialists, plus a full Handoff mesh covering
every distinct pair. The naive "Cartesian product minus self-edges"
form duplicates the orchestrator→specialist edges as both SendMessage
and Handoff: each pair gets two tool classes registered.

The dual_comms patch tolerates that — same pair, different tool classes
is allowed — but it's not the cleanest registration. Building two flow
entries when one would do means:
- twice the tool-registration work at construction time,
- a longer flow list to read when debugging routing.

This helper builds the handoff mesh with the SendMessage edges removed
so the combined topology is identical (union is preserved) without the
duplication.

Verification: the union of edges (sender_name, receiver_name) across
`send_message_flows ∪ handoff_flows` is preserved before and after the
dedup — tests/test_handoff_flows.py enforces this for every swarm.
"""

from __future__ import annotations

from typing import Any, Iterable


def build_handoff_flows(
    agents: list[Any],
    send_message_flows: Iterable[tuple],
    handoff_tool_class: type,
) -> list[tuple]:
    """Return the handoff mesh for `agents`, minus any edge already
    covered by `send_message_flows`.

    `send_message_flows` is the iterable of `(sender, receiver, tool_cls)`
    triples (or `(sender, receiver)` pairs — the third element is
    optional). `handoff_tool_class` is the Handoff class to attach to
    each surviving edge.

    Returns a list of `(sender > receiver, Handoff)` entries suitable
    for concatenation with `send_message_flows` and passing to
    `Agency(communication_flows=...)`.
    """
    sm_edges: set[tuple[int, int]] = set()
    for entry in send_message_flows:
        if len(entry) >= 2:
            sender, receiver = entry[0], entry[1]
            sm_edges.add((id(sender), id(receiver)))

    flows: list[tuple] = []
    for sender in agents:
        for receiver in agents:
            if sender is receiver:
                continue
            if (id(sender), id(receiver)) in sm_edges:
                continue
            flows.append((sender > receiver, handoff_tool_class))
    return flows


def collect_edge_set(flows: Iterable[tuple]) -> set[tuple[str, str]]:
    """Project a flow list down to `{(sender_name, receiver_name)}`.

    Tolerates both shapes used in this codebase:
    - SendMessage triples: `(sender_agent, receiver_agent, tool_class)`
    - Handoff entries: `(agent_flow, tool_class)` where `agent_flow`
      has `.sender_agent` / `.receiver_agent` attributes (or
      `.sender` / `.receiver` on older agency-swarm versions).

    Used by the edge-preservation test to confirm dedup'd topologies
    cover the same set of edges as the naive Cartesian-product form.
    """
    edges: set[tuple[str, str]] = set()
    for entry in flows:
        if len(entry) >= 3 and hasattr(entry[0], "name") and hasattr(entry[1], "name"):
            edges.add((entry[0].name, entry[1].name))
            continue
        # Handoff shape: first element is an AgentFlow-like object
        flow = entry[0]
        sender = (
            getattr(flow, "sender_agent", None)
            or getattr(flow, "sender", None)
        )
        receiver = (
            getattr(flow, "receiver_agent", None)
            or getattr(flow, "receiver", None)
        )
        if sender is not None and receiver is not None:
            edges.add((getattr(sender, "name", str(sender)),
                       getattr(receiver, "name", str(receiver))))
    return edges
