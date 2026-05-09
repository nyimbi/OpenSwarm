"""SoftDev DevOps — CI/CD, build pipelines, deploy automation, container configs."""

from pathlib import Path

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from swarms.softdev.shared_tools import (
    ReadFile, WriteFile, EditFile, ListDir, GitStatus, GitDiff, GitLog,
)

load_dotenv()


def create_devops() -> Agent:
    from agency_swarm.tools import PersistentShellTool

    return Agent(
        name="DevOps",
        description=(
            "Owns CI/CD configs, Dockerfiles, build scripts, deploy "
            "automation, and package metadata. Doesn't touch application "
            "code — that's the Coder's surface."
        ),
        instructions=str(Path(__file__).parent / "instructions.md"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[
            ReadFile, WriteFile, EditFile, ListDir,
            GitStatus, GitDiff, GitLog,
            PersistentShellTool,
        ],
    )
