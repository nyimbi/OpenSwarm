"""GitStatus — short-form working tree status."""

from agency_swarm.tools import BaseTool
from pydantic import Field

from swarms._common.git_tools._git import run_git


class GitStatus(BaseTool):
    """
    Show modified, staged, and untracked files in the working tree.

    Output is `git status --short` (one file per line, columns indicate
    index/worktree state). Use this before any commit/diff workflow to
    understand what's changed.
    """

    cwd: str = Field(
        default=".",
        description=(
            "Project directory to inspect. Defaults to the current "
            "working directory of the OpenSwarm process."
        ),
    )

    def run(self) -> str:
        out = run_git(["status", "--short", "--branch"], cwd=self.cwd)
        return out or "Working tree clean."
