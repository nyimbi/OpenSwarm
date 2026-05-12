"""GitDiff — show diffs of unstaged, staged, or arbitrary commit ranges."""

from agency_swarm.tools import BaseTool
from pydantic import Field

from swarms._common.git_tools._git import run_git


class GitDiff(BaseTool):
    """
    Show a unified diff. By default, shows unstaged changes. Pass
    `staged=True` for the index diff, or `revision` to compare against a
    specific commit / branch / range (e.g. 'HEAD~3', 'main..feature/x').
    """

    cwd: str = Field(default=".", description="Project directory.")
    staged: bool = Field(
        default=False,
        description="If true, show the staged (index) diff instead of unstaged.",
    )
    revision: str | None = Field(
        default=None,
        description=(
            "Optional revision or range. Passed verbatim to `git diff` "
            "(e.g. 'HEAD~1', 'main..HEAD', 'a1b2c3..d4e5f6'). When set, "
            "`staged` is ignored."
        ),
    )
    paths: list[str] | None = Field(
        default=None,
        description="Optional list of paths to limit the diff to.",
    )

    def run(self) -> str:
        args = ["diff"]
        if self.revision:
            args.append(self.revision)
        elif self.staged:
            args.append("--staged")
        if self.paths:
            args.append("--")
            args.extend(self.paths)
        out = run_git(args, cwd=self.cwd)
        return out or "(no diff)"
