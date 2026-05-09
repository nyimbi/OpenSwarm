"""ListDir — directory listing with optional pattern filter."""

from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field


class ListDir(BaseTool):
    """List files in a directory. Use for orientation when the user names a folder."""

    path: str = Field(default=".", description="Directory path.")
    pattern: str = Field(
        default="*",
        description="Glob pattern (e.g. '*.py'). Defaults to all files.",
    )
    recursive: bool = Field(default=False, description="Recurse into subdirectories.")

    def run(self) -> str:
        p = Path(self.path)
        if not p.is_dir():
            return f"Error: {p} is not a directory."
        glob = p.rglob if self.recursive else p.glob
        try:
            entries = sorted(str(x.relative_to(p)) for x in glob(self.pattern))
        except OSError as exc:
            return f"Error listing {p}: {exc}"
        if not entries:
            return f"(no matches for '{self.pattern}' in {p})"
        return "\n".join(entries[:200]) + (
            f"\n... [{len(entries) - 200} more]" if len(entries) > 200 else ""
        )
