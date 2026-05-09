"""Marketing — 5 agents for website, copy, SEO, campaigns."""

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
        "Routes marketing work; doesn't write copy itself.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    strategist = make_agent(
        "Strategist",
        "Owns positioning, voice, campaign architecture, audience definition.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
        reasoning="high",
    )
    copywriter = make_agent(
        "CopyWriter",
        "Writes the actual copy: web pages, ads, emails, social posts.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
    )
    seo = make_agent(
        "SEOSpecialist",
        "Keywords, meta tags, schema, headings, on-page optimization.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearch, WebFetch],
    )
    editor = make_agent(
        "Editor",
        "Voice consistency, brand-line check, polish.",
        INSTRUCTIONS,
        tools=[ReadFile, EditFile, ListDir],
        reasoning="high",
    )

    agents = [orch, strategist, copywriter, seo, editor]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    handoff_flows = [(a > b, Handoff) for a in agents for b in agents if a is not b]

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="Marketing",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
