"""GeopoliticalAnalysis — 5 agents for international affairs work."""

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
        "Routes geopolitical analysis tasks.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    researcher = make_agent(
        "Researcher",
        "Gathers current events, primary documents, official statements, news.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, WebSearch, WebFetch],
    )
    regional = make_agent(
        "RegionalAnalyst",
        "Provides area expertise: history, internal politics, identities, recent dynamics.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, WebSearch, WebFetch],
        reasoning="high",
    )
    strategic = make_agent(
        "StrategicAnalyst",
        "Actor interests, capabilities, motivations; alliance and rivalry dynamics.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, WebSearch, WebFetch],
        reasoning="high",
    )
    synthesizer = make_agent(
        "Synthesizer",
        "Final brief: what's happening, why, what to watch, what could happen next.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )

    agents = [orch, researcher, regional, strategic, synthesizer]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    from swarms._common.comms import build_handoff_flows
    handoff_flows = build_handoff_flows(agents, send_message_flows, Handoff)

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="GeopoliticalAnalysis",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
