"""HistoricalAnalysis — 4 agents for evidence-based historical work."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agency_swarm import Agency

INSTRUCTIONS = Path(__file__).parent / "instructions"


def create_agency(load_threads_callback=None) -> "Agency":
    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage, WebSearchTool

    from orchestrator.tools import SwitchProvider, SwitchSwarm
    from swarms._common.agent_factory import make_agent
    from swarms._common.file_ops import ReadFile, WriteFile, EditFile, ListDir

    orch = make_agent(
        "Orchestrator",
        "Routes historical research and synthesis tasks.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    researcher = make_agent(
        "Researcher",
        "Gathers primary and secondary sources, period context, key actors.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, WebSearchTool],
    )
    analyst = make_agent(
        "Analyst",
        "Interprets evidence: causation, patterns, competing accounts, biases.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, WebSearchTool],
        reasoning="high",
    )
    synthesizer = make_agent(
        "Synthesizer",
        "Combines research + analysis into a final report with citations.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )

    agents = [orch, researcher, analyst, synthesizer]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    handoff_flows = [(a > b, Handoff) for a in agents for b in agents if a is not b]

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="HistoricalAnalysis",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
