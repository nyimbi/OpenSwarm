"""Run a registered swarm to completion and return its result.

Subroutine-style delegation: builds a fresh sub-agency, runs it
synchronously against the task, and returns the final string output.
The sub-agency is discarded after the run — no thread state survives.

This is distinct from `SwitchSwarm`, which migrates the user's whole
session to a different swarm. Use `DispatchToSwarm` for "do this
discrete piece of work and bring me the result"; use `SwitchSwarm` for
"the user wants to keep working in that domain."
"""

from __future__ import annotations

from agency_swarm.tools import BaseTool
from pydantic import Field


class DispatchToSwarm(BaseTool):
    """
    Run a sub-swarm to completion against a task and return its final output.

    The sub-swarm is built fresh for this call (its own agency, its own
    threads) and is discarded when the call returns. Token cost mirrors a
    full conversation in that swarm — only dispatch when the work is
    discrete and completable in one pass.
    """

    swarm: str = Field(
        ...,
        description=(
            "Slug of the sub-swarm to run. See swarms/__init__.py for the "
            "registry — e.g. 'openswarm', 'softdev'. Cannot be 'metaswarm' "
            "(no recursive self-dispatch)."
        ),
    )
    task: str = Field(
        ...,
        min_length=1,
        description=(
            "The task to give the sub-swarm. Phrase it as if you were "
            "writing a clear, self-contained brief — the sub-swarm has no "
            "memory of this conversation. Include constraints, expected "
            "output format, and any file paths the sub-swarm should "
            "operate on."
        ),
    )

    def run(self) -> str:
        slug = self.swarm.strip().lower()

        # Lazy import: keeps tool-load fast, avoids circulars with the registry
        from swarms import SWARMS, get_factory

        if slug == "metaswarm":
            return (
                "Refusing dispatch: cannot recursively dispatch to metaswarm. "
                "Dispatch to a leaf swarm (e.g. openswarm or softdev) instead."
            )
        if slug not in SWARMS:
            return (
                f"Unknown swarm '{self.swarm}'. Available: "
                f"{', '.join(s for s in SWARMS if s != 'metaswarm')}."
            )

        try:
            factory = get_factory(slug)
            sub_agency = factory()
        except Exception as exc:
            return (
                f"Failed to construct sub-swarm '{slug}': "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            result = sub_agency.get_response_sync(self.task)
        except Exception as exc:
            return (
                f"Sub-swarm '{slug}' raised {type(exc).__name__} during "
                f"execution: {exc}"
            )

        # RunResult exposes the final assistant text via .final_output on
        # current openai-agents-sdk; fall back to str() for safety.
        output = getattr(result, "final_output", None) or str(result)
        return f"[{slug}] {output}"
