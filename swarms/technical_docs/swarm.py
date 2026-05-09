"""TechnicalDocs swarm — 4 agents for documentation production."""

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
    from swarms.softdev.shared_tools import GitDiff

    orch = make_agent(
        "Orchestrator",
        "Routes documentation requests to the right specialist.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    architect = make_agent(
        "DocArchitect",
        "Plans documentation structure: TOC, audience, scope, depth.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, WebSearchTool],
        reasoning="high",
    )
    writer = make_agent(
        "TechWriter",
        "Writes the actual prose: API refs, guides, tutorials, READMEs.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearchTool],
    )
    editor = make_agent(
        "Editor",
        "Reviews docs for clarity, accuracy, voice, and consistency.",
        INSTRUCTIONS,
        tools=[ReadFile, EditFile, ListDir, GitDiff],
        reasoning="high",
    )

    agents = [orch, architect, writer, editor]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    handoff_flows = [(a > b, Handoff) for a in agents for b in agents if a is not b]

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="TechnicalDocs",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
