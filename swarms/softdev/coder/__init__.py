"""SoftDev Coder — implements specs, edits files, runs commands."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from swarms.softdev.shared_tools import (
    ReadFile, WriteFile, EditFile, ListDir, GitStatus, GitDiff,
)

load_dotenv()


def create_coder() -> Agent:
    # PersistentShellTool ships with agency-swarm; imported lazily to avoid
    # a hard dep at module load time if the framework's optional integration
    # surface changes.
    from agency_swarm.tools import PersistentShellTool

    return Agent(
        name="Coder",
        description=(
            "Implements features from the Architect's spec or the user's "
            "direct request. Edits files, runs commands, makes the change "
            "the rest of the swarm reviews and tests."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[
            ReadFile, WriteFile, EditFile, ListDir,
            GitStatus, GitDiff,
            PersistentShellTool,
        ],
    )
