"""Switch the running swarm at runtime.

Symmetric to SwitchProvider — writes OPENSWARM_SWARM to .env, refreshes
os.environ in this process, and signals run_utils.main() to rebuild on
the next TUI loop iteration. Available to every orchestrator (so you can
go from MetaSwarm → SoftDev → MetaSwarm → OpenSwarm in one session).

Note on FastAPI: switching at runtime is a TUI concept. The FastAPI
server already exposes every swarm at its own URL path
(`/openswarm/...`, `/softdev/...`, `/metaswarm/...`), so API clients
just hit the swarm they want directly — no tool needed.
"""

from __future__ import annotations

import os
from pathlib import Path

from agency_swarm.tools import BaseTool
from dotenv import load_dotenv, set_key
from pydantic import Field

# Import the registry lazily so this module loads even if a swarm's tools
# fail to import — the registry itself uses lazy factories.
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
SWITCH_FLAG_VAR = "OPENSWARM_SWITCH_FLAG"


def _available_slugs() -> list[str]:
    from swarms import SWARMS
    return list(SWARMS)


class SwitchSwarm(BaseTool):
    """
    Switch the running swarm. Persists OPENSWARM_SWARM to .env and signals
    the TUI to rebuild with the new swarm on next loop iteration.

    Use when the user says "switch to softdev", "open the metaswarm",
    "jump to OpenSwarm", or asks to leave one swarm for another. After
    the tool returns, the change is live for subsequent agency builds —
    in the TUI, the user exits (`/quit` or Ctrl-C) to refresh the
    display; in FastAPI, every swarm already has its own URL path so
    this tool isn't usually needed there.
    """

    swarm: str = Field(
        ...,
        description=(
            "Slug of the swarm to switch to. See the swarms registry for "
            "available slugs (e.g. openswarm, softdev, metaswarm)."
        ),
    )

    def run(self) -> str:
        slug = self.swarm.strip().lower()
        available = _available_slugs()
        if slug not in available:
            return (
                f"Unknown swarm '{self.swarm}'. Available: {', '.join(available)}."
            )

        # Atomic .env write so a concurrent reader can't see a half-written file.
        if not ENV_PATH.exists():
            ENV_PATH.write_text("", encoding="utf-8")
        tmp_path = ENV_PATH.with_suffix(ENV_PATH.suffix + ".tmp")
        try:
            tmp_path.write_text(ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            set_key(str(tmp_path), "OPENSWARM_SWARM", slug)
            os.replace(str(tmp_path), str(ENV_PATH))
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

        # Refresh os.environ so any subsequent in-process code sees the new
        # value (parallels the SwitchProvider behavior — useful in case the
        # TUI or a test harness inspects env mid-call).
        load_dotenv(str(ENV_PATH), override=True)

        # Signal the TUI restart loop. Best-effort — the env reload above
        # already made the change visible in-process.
        flag_path = os.environ.get(SWITCH_FLAG_VAR)
        if flag_path:
            try:
                Path(flag_path).touch()
            except OSError:
                pass

        return (
            f"Swarm switched to '{slug}'. Exit the TUI (`/quit` or Ctrl-C) "
            "and OpenSwarm will restart with the new swarm. (FastAPI users "
            "should hit the new swarm's URL path directly instead.)"
        )
