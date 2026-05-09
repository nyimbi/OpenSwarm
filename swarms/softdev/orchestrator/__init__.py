"""SoftDev Orchestrator — routes work to specialists, executes nothing itself."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider

# Administrative carve-outs — same tools the OpenSwarm orchestrator has.
from orchestrator.tools import SwitchProvider, SwitchSwarm

load_dotenv()


def create_orchestrator() -> Agent:
    return Agent(
        name="Orchestrator",
        description=(
            "SoftDev's primary coordinator: plans multi-agent workflows for "
            "software engineering tasks, runs independent workstreams in "
            "parallel, hands off when a specialist owns the next step."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[SwitchProvider, SwitchSwarm],
        conversation_starters=[
            "Plan and implement a new feature in this repo.",
            "Review the latest diff for bugs and regressions.",
            "Add tests for the module I'm working on.",
            "Set up CI for this project.",
        ],
    )
