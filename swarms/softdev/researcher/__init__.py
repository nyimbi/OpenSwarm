"""SoftDev Researcher — library lookups, codebase exploration, external context."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from swarms.softdev.shared_tools import ReadFile, ListDir

load_dotenv()


def create_researcher() -> Agent:
    from agency_swarm.tools import WebSearchTool

    return Agent(
        name="Researcher",
        description=(
            "Gathers external context: library/API docs, design patterns, "
            "blog posts, and prior-art examples. Also explores unfamiliar "
            "codebases to summarize what's there."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[ReadFile, ListDir, WebSearchTool()],
    )
