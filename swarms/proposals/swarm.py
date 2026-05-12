"""Proposals — 6 agents for business-proposal production.

Pipeline: Discovery → Strategy → Drafter → Pricer → Editor.

Compliance audit against the original RFP runs in the Editor pass.
Web research is wired only on DiscoveryAnalyst — at the tool layer —
so the Drafter cannot reach out for new sources mid-write and invent
citations. If the Drafter needs more research, it hands back to
Discovery; that's the contract.
"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agency_swarm import Agency

INSTRUCTIONS = Path(__file__).parent / "instructions"


def create_agency(load_threads_callback=None) -> "Agency":
    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage

    from orchestrator.tools import SwitchProvider, SwitchSwarm
    from swarms._common.agent_factory import make_agent
    from swarms._common.comms import build_handoff_flows
    from swarms._common.file_ops import ReadFile, WriteFile, EditFile, ListDir
    from swarms._common.web_tools import WebSearch, WebFetch

    orch = make_agent(
        "Orchestrator",
        "Routes proposal-development work to the right specialist; never writes proposal text.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    # DiscoveryAnalyst is the ONLY agent with external research tools.
    # This is the proposal-quality contract: every external fact in
    # the proposal traces to discovery.md, which has provenance.
    discovery = make_agent(
        "DiscoveryAnalyst",
        "Reads the RFP/brief, researches the prospect and competitive landscape, extracts the requirements table, surfaces constraints.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
        reasoning="high",
    )
    strategist = make_agent(
        "Strategist",
        "Sets win themes, storyline, and counter-positioning against likely competitors.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )
    # Drafter intentionally has NO web tools — research belongs to
    # Discovery. Drafter synthesizes from discovery.md + strategy.md,
    # and hands back if the strategy isn't supportable.
    drafter = make_agent(
        "Drafter",
        "Writes the proposal text section by section from discovery + strategy. No external research — hand back to Discovery if more is needed.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )
    pricer = make_agent(
        "Pricer",
        "Builds pricing tables, scope assumptions, commercial terms, payment milestones, keyed to the Drafter's phases.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )
    editor = make_agent(
        "Editor",
        "RFP-compliance audit, voice polish, version freeze. Maps every requirement to where it's addressed and produces the compliance matrix.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )

    agents = [orch, discovery, strategist, drafter, pricer, editor]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    handoff_flows = build_handoff_flows(agents, send_message_flows, Handoff)

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="Proposals",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
