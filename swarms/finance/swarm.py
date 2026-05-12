"""Finance — 5 agents for budgets, P&L, projections.

The arithmetic happens in IPython (pandas / numpy), not in agent reasoning.
LLMs are confidently wrong about numbers; the IPython tool is the
authoritative computer for any figure that goes into a deliverable.
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

    # IPython is the math substrate. Lazy-imported because it requires the
    # `agency-swarm[jupyter]` extra; we degrade gracefully if it's missing.
    try:
        from agency_swarm.tools import IPythonInterpreter
        _ipython: list[type] = [IPythonInterpreter]
    except ImportError:
        _ipython = []

    orch = make_agent(
        "Orchestrator",
        "Routes finance work; never does arithmetic itself.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    loader = make_agent(
        "DataLoader",
        "Ingests financial data: CSV, Excel, QuickBooks exports, bank statements.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, *_ipython],
    )
    analyst = make_agent(
        "Analyst",
        "Variance analysis, ratios, trend identification, period comparisons.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, *_ipython],
        reasoning="high",
    )
    modeler = make_agent(
        "Modeler",
        "Forecasts, scenarios, what-if models, budget projections.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, *_ipython],
        reasoning="high",
    )
    reporter = make_agent(
        "Reporter",
        "Synthesizes the analyst + modeler output into a board/owner-readable report.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, *_ipython],
        reasoning="high",
    )

    agents = [orch, loader, analyst, modeler, reporter]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    from swarms._common.comms import build_handoff_flows
    handoff_flows = build_handoff_flows(agents, send_message_flows, Handoff)

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="Finance",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )
