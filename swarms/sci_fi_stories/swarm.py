"""SciFiStories — 4 agents for sci-fi narrative production."""

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

    orch = make_agent(
        "Orchestrator",
        "Routes sci-fi-story tasks.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    worldbuilder = make_agent(
        "Worldbuilder",
        "Builds setting, lore, technology premise, the rules of the world.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir],
        reasoning="high",
    )
    narrator = make_agent(
        "Narrator",
        "Writes plot, characters, scenes, and prose.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )
    editor = make_agent(
        "Editor",
        "Reviews drafts for voice, pacing, internal consistency, dialog rhythm.",
        INSTRUCTIONS,
        tools=[ReadFile, EditFile, ListDir],
    )

    agents = [orch, worldbuilder, narrator, editor]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    from swarms._common.comms import build_handoff_flows
    handoff_flows = build_handoff_flows(agents, send_message_flows, Handoff)

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="SciFiStories",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
