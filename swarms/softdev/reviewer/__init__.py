"""SoftDev Reviewer — reads diffs, catches bugs, flags style and regression risks."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from swarms.softdev.shared_tools import (
    ReadFile, ListDir, GitStatus, GitDiff, GitLog,
)

load_dotenv()


def create_reviewer() -> Agent:
    return Agent(
        name="Reviewer",
        description=(
            "Reviews code diffs for bugs, regressions, style issues, and "
            "design concerns. Reports findings; doesn't write fixes — "
            "hands those back to the Coder."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto") if is_openai_provider() else None,
        ),
        tools=[ReadFile, ListDir, GitStatus, GitDiff, GitLog],
    )
