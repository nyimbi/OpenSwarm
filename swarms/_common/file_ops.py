"""File-op tools shared across swarms.

ReadFile, WriteFile, EditFile, ListDir are provider-agnostic enough that
most non-softdev swarms (technical_docs, courses, sci-fi, etc.) want
them. Defining them here under `_common/` removes the boundary
violation where `_common.file_ops` used to import them from
`swarms.softdev.shared_tools` — fixed in fix-all-issues Commit 4.
"""

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


__all__ = ["ReadFile", "WriteFile", "EditFile", "ListDir"]
