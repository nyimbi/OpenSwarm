"""PeopleOps — 5 agents for HR / operations work on a small team."""

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
        "Routes HR / operations tasks; doesn't author docs itself.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    policy_writer = make_agent(
        "PolicyWriter",
        "Drafts handbooks, SOPs, safety policies, employment policies.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
        reasoning="high",
    )
    scheduler = make_agent(
        "Scheduler",
        "Builds rosters, leave plans, shift schedules; flags conflicts.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
    )
    trainer = make_agent(
        "TrainingDesigner",
        "Builds onboarding paths, role-specific training plans, refreshers.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
        reasoning="high",
    )
    coach = make_agent(
        "PerformanceCoach",
        "Frames 1:1 agendas, performance reviews, feedback drafts.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
        reasoning="high",
    )

    agents = [orch, policy_writer, scheduler, trainer, coach]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    handoff_flows = [(a > b, Handoff) for a in agents for b in agents if a is not b]

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="PeopleOps",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
