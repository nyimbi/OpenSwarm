"""CorpusAnalysis swarm — 5 agents for textual + statistical corpus work."""

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

    # IPython interpreter is the primary tool for any statistical or
    # text-mining work. Imported lazily because it requires the jupyter
    # extra of agency-swarm.
    try:
        from agency_swarm.tools import IPythonInterpreter
        _ipython_tool: list[type] = [IPythonInterpreter]
    except ImportError:
        _ipython_tool = []

    orch = make_agent(
        "Orchestrator",
        "Routes corpus-analysis requests to the right specialist.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    loader = make_agent(
        "Loader",
        "Ingests, parses, and normalizes input documents (text, CSV, JSON, markdown).",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, *_ipython_tool],
    )
    text_analyst = make_agent(
        "TextAnalyst",
        "Theme extraction, sentiment, classification, named-entity work.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, *_ipython_tool],
        reasoning="high",
    )
    stat_analyst = make_agent(
        "StatAnalyst",
        "Frequencies, distributions, correlations, statistical tests.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, *_ipython_tool],
        reasoning="high",
    )
    reporter = make_agent(
        "Reporter",
        "Synthesizes the analyst findings into a single report with figures.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, *_ipython_tool],
    )

    agents = [orch, loader, text_analyst, stat_analyst, reporter]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    from swarms._common.comms import build_handoff_flows
    handoff_flows = build_handoff_flows(agents, send_message_flows, Handoff)

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="CorpusAnalysis",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
