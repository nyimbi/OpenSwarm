"""MetaOrchestrator — front-door router across the swarm fleet."""

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider

# Imported separately because they're scoped to this swarm.
from swarms.metaswarm.orchestrator.tools import DispatchToSwarm

# Reused from the OpenSwarm orchestrator's tool directory — the same
# administrative carve-outs apply at the meta level too.
from orchestrator.tools import SwitchProvider, SwitchSwarm


def create_meta_orchestrator() -> Agent:
    return Agent(
        name="MetaOrchestrator",
        description=(
            "Front-door router. Given a user request, decides which swarm "
            "should handle it and either dispatches synchronously (running "
            "the sub-swarm to completion via DispatchToSwarm) or migrates "
            "the whole session to that swarm (via SwitchSwarm)."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[DispatchToSwarm, SwitchSwarm, SwitchProvider],
        conversation_starters=[
            "I want to ship a feature for my project.",
            "Build me a slide deck about quarterly results.",
            "Research a topic and turn it into a report with charts.",
            "Set up CI/CD for my project and write a deploy guide.",
        ],
    )
