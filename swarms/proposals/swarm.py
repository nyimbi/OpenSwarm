"""Proposals — 6 agents for business-proposal production.

Pipeline: Discovery -> Strategy -> Drafter + Pricer -> Editor.
Compliance audit against the original RFP is built into the Editor pass.
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
    from swarms._common.file_ops import ReadFile, WriteFile, EditFile, ListDir
    from swarms._common.web_tools import WebSearch, WebFetch

    orch = make_agent(
        "Orchestrator",
        "Routes proposal-development work to the right specialist; never writes proposal text.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    discovery = make_agent(
        "DiscoveryAnalyst",
        "Reads the RFP/brief, researches the prospect, extracts requirements, surfaces constraints.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
        reasoning="high",
    )
    strategist = make_agent(
        "Strategist",
        "Sets win themes and the storyline of the proposal from discovery findings.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )
    drafter = make_agent(
        "Drafter",
        "Writes the proposal text section by section following the Strategist's storyline.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
    )
    pricer = make_agent(
        "Pricer",
        "Builds pricing tables, scope assumptions, commercial terms, payment milestones.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )
    editor = make_agent(
        "Editor",
        "RFP-compliance audit + voice polish. Maps every RFP requirement to where it's addressed.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )

    agents = [orch, discovery, strategist, drafter, pricer, editor]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    from swarms._common.comms import build_handoff_flows
    handoff_flows = build_handoff_flows(agents, send_message_flows, Handoff)

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="Proposals",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
