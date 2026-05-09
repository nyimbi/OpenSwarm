"""SoftDev Tester — writes tests, runs the suite, debugs failures."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from swarms.softdev.shared_tools import (
    ReadFile, WriteFile, EditFile, ListDir, GitDiff, RunTests,
)

load_dotenv()


def create_tester() -> Agent:
    from agency_swarm.tools import PersistentShellTool

    return Agent(
        name="Tester",
        description=(
            "Writes new tests, runs the existing suite, debugs failures. "
            "Hands code-level fixes back to the Coder; owns test code "
            "directly."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[
            ReadFile, WriteFile, EditFile, ListDir, GitDiff,
            RunTests, PersistentShellTool,
        ],
    )
