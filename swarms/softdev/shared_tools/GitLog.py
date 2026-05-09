"""GitLog — recent commit history."""

from agency_swarm.tools import BaseTool
from pydantic import Field

from swarms.softdev.shared_tools._git import run_git


class GitLog(BaseTool):
    """
    Show recent commits in compact form (one line each: SHA, author, message).

    Use this to understand what's happened recently before making changes
    that touch the same areas. Defaults to the last 10 commits.
    """

    cwd: str = Field(default=".", description="Project directory.")
    n: int = Field(default=10, ge=1, le=100, description="Number of commits to show (1-100).")
    paths: list[str] | None = Field(
        default=None,
        description="Optional list of paths to filter the log to.",
    )

    def run(self) -> str:
        args = ["log", f"-{self.n}", "--oneline", "--no-color"]
        if self.paths:
            args.append("--")
            args.extend(self.paths)
        out = run_git(args, cwd=self.cwd)
        return out or "No commits."
