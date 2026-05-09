"""WriteFile — overwrite a file with new content. Creates parent dirs if needed."""

from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field


class WriteFile(BaseTool):
    """
    Overwrite a file with new content.

    Use for new files or full rewrites. For surgical changes to an
    existing file, prefer EditFile (cheaper, less risk of dropping
    surrounding context).
    """

    path: str = Field(..., description="Path to write (relative to cwd or absolute).")
    content: str = Field(..., description="Full new content of the file.")

    def run(self) -> str:
        p = Path(self.path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.content, encoding="utf-8")
        except OSError as exc:
            return f"Error writing {p}: {exc}"
        return f"Wrote {len(self.content)} chars to {p}."
