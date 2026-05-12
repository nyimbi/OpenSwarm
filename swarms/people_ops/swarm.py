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

    # ADR §3 Decision A (PII boundary narrowing): specialists handling
    # personnel data have NO direct web egress. WebSearch + WebFetch are
    # available only at the Orchestrator, which mediates any external
    # lookup and hands facts to specialists via SendMessage. This brings
    # people_ops into line with the finance swarm's tool-layer enforcement.
    #
    # ADR §3 Decision B (capability expansion, audit event): the
    # Orchestrator NOW carries WebSearch + WebFetch — a contract change
    # from prior versions where it had only [SwitchProvider, SwitchSwarm].
    # Rationale: a single chokepoint for outbound traffic that does not
    # see specialist PII in the same prompt context as the lookup.
    orch = make_agent(
        "Orchestrator",
        "Routes HR / operations tasks. Performs external lookups (regulations, "
        "industry benchmarks) and hands facts to specialists; never authors HR docs.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm, WebSearch, WebFetch],
    )
    policy_writer = make_agent(
        "PolicyWriter",
        "Drafts handbooks, SOPs, safety policies, employment policies. "
        "External facts are provided by the Orchestrator; this agent has no web egress.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
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
        "Builds onboarding paths, role-specific training plans, refreshers. "
        "External examples are provided by the Orchestrator; this agent has no web egress.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
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
