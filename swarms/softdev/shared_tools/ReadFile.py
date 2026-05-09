"""ReadFile — read a text file with sensible truncation."""

from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field


class ReadFile(BaseTool):
    """Read a text file. Returns its contents with line numbers prepended."""

    path: str = Field(..., description="Path to the file (relative to cwd or absolute).")
    start_line: int = Field(default=1, ge=1, description="Line to start reading from (1-indexed).")
    end_line: int | None = Field(
        default=None,
        description="Last line to read (inclusive). If unset, reads to end of file.",
    )

    def run(self) -> str:
        p = Path(self.path)
        if not p.is_file():
            return f"Error: {p} is not a file."
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: {p} is not a UTF-8 text file."
        lines = text.splitlines()
        end = self.end_line if self.end_line else len(lines)
        sel = lines[self.start_line - 1 : end]
        numbered = [f"{i + self.start_line:5d}  {line}" for i, line in enumerate(sel)]
        return "\n".join(numbered) or "(empty range)"
