"""Lightweight Agent constructor used by the secondary swarms.

The OpenSwarm and SoftDev swarms put each agent in its own folder with a
dedicated `create_<name>()` factory, which is fine when an agent has
non-trivial setup. Most agents in the topic-area swarms (technical_docs,
courses, sci-fi, etc.) are plain — name + description + tools +
instructions file. This helper keeps their swarm.py compact instead of
producing 4-8 near-identical factory modules per swarm.

Convention: instructions files live in `<swarm>/instructions/<name>.md`
where <name> is the agent's lowercase name with non-alpha chars stripped.
"""

from pathlib import Path
from typing import Iterable

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider


def make_agent(
    name: str,
    description: str,
    instructions_dir: Path,
    tools: Iterable[type] = (),
    reasoning: str = "medium",
) -> Agent:
    """Build an Agent with conventional defaults.

    `instructions_dir` is the swarm's instructions folder; the agent's
    individual file is loaded from `<instructions_dir>/<slug>.md` where
    slug is the lowercase, alphanumeric-only form of `name`.
    """
    slug = "".join(c for c in name.lower() if c.isalnum() or c == "_")
    instructions_path = instructions_dir / f"{slug}.md"

    # H7: eager validation. A missing instruction file would otherwise be
    # accepted silently and the agent would run with no system prompt.
    if not instructions_path.is_file():
        raise FileNotFoundError(
            f"Agent '{name}' has no instructions file at {instructions_path}. "
            f"Expected slug: '{slug}.md' under {instructions_dir}."
        )

    return Agent(
        name=name,
        description=description,
        instructions=str(instructions_path),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=(
                Reasoning(effort=reasoning, summary="auto")
                if is_openai_provider()
                else None
            ),
        ),
        tools=list(tools),
    )
