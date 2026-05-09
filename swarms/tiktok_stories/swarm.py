"""TikTokStories — 5 agents for short-form vertical-video story production."""

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
        "Routes short-form story tasks.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    hook_writer = make_agent(
        "HookWriter",
        "Writes the opening 3-second hook + premise that earns the rest of the watch.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir],
        reasoning="high",
    )
    storyteller = make_agent(
        "Storyteller",
        "Writes the full 30-90s narrative arc that follows the hook.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
    )
    storyboarder = make_agent(
        "Storyboarder",
        "Translates the script into a shot-by-shot visual sequence.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
    )
    polisher = make_agent(
        "Polisher",
        "Final pass: captions, voiceover script, music/SFX cues, hashtags.",
        INSTRUCTIONS,
        tools=[ReadFile, EditFile, ListDir],
    )

    agents = [orch, hook_writer, storyteller, storyboarder, polisher]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    handoff_flows = [(a > b, Handoff) for a in agents for b in agents if a is not b]

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="TikTokStories",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
