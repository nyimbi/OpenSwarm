"""EditFile — exact-string find-and-replace, fails if old_string is ambiguous."""

from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field


class EditFile(BaseTool):
    """
    Replace a single occurrence of `old_string` with `new_string` in the file.

    Refuses to operate when `old_string` matches more than once or
    doesn't match at all — pass enough surrounding context to make the
    match unique. Pass `replace_all=True` to override.
    """

    path: str = Field(..., description="Path to the file.")
    old_string: str = Field(..., min_length=1, description="Exact text to replace.")
    new_string: str = Field(..., description="Text to replace it with.")
    replace_all: bool = Field(default=False, description="Replace every match instead of erroring on multiples.")

    def run(self) -> str:
        p = Path(self.path)
        if not p.is_file():
            return f"Error: {p} is not a file."
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: {p} is not UTF-8."

        count = text.count(self.old_string)
        if count == 0:
            return f"Error: old_string not found in {p}."
        if count > 1 and not self.replace_all:
            return (
                f"Error: old_string matches {count} times in {p}. Add more "
                "context to make the match unique, or pass replace_all=True."
            )

        new_text = text.replace(self.old_string, self.new_string, -1 if self.replace_all else 1)
        try:
            p.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            return f"Error writing {p}: {exc}"
        return f"Replaced {count if self.replace_all else 1} occurrence(s) in {p}."
