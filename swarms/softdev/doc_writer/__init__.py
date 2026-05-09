"""SoftDev DocWriter — keeps prose docs in sync with code."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from swarms.softdev.shared_tools import (
    ReadFile, WriteFile, EditFile, ListDir, GitDiff,
)

load_dotenv()


def create_doc_writer() -> Agent:
    return Agent(
        name="DocWriter",
        description=(
            "Updates READMEs, docstrings, comments, and architecture notes "
            "to reflect code changes. Keeps prose tight and accurate."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[ReadFile, WriteFile, EditFile, ListDir, GitDiff],
    )
