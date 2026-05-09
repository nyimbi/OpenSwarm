"""SoftDev Architect — plans features, designs components, writes specs."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from swarms.softdev.shared_tools import (
    ReadFile, WriteFile, ListDir, GitStatus, GitDiff, GitLog,
)

load_dotenv()


def create_architect() -> Agent:
    return Agent(
        name="Architect",
        description=(
            "Designs features and refactors. Reads the codebase to understand "
            "constraints, then produces a clear plan/spec that the Coder can "
            "implement directly. Doesn't write the implementation itself."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto") if is_openai_provider() else None,
        ),
        tools=[ReadFile, WriteFile, ListDir, GitStatus, GitDiff, GitLog],
    )
