"""RunTests — auto-detect the project's test runner and execute it.

Auto-detection priority: pytest (Python projects with tests/ or pyproject
test config) → npm test (JS projects) → cargo test (Rust) → go test (Go).
The caller can override with an explicit `command`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field


def _detect_command(cwd: Path) -> tuple[str, list[str]] | None:
    """Return (label, argv) for the detected runner, or None."""
    # Python — pytest
    if (cwd / "pyproject.toml").exists() or (cwd / "tests").is_dir() or (cwd / "setup.cfg").exists():
        return ("pytest", ["pytest"])
    # JS — npm test
    if (cwd / "package.json").exists():
        return ("npm test", ["npm", "test", "--silent"])
    # Rust
    if (cwd / "Cargo.toml").exists():
        return ("cargo test", ["cargo", "test"])
    # Go
    if (cwd / "go.mod").exists():
        return ("go test", ["go", "test", "./..."])
    return None


class RunTests(BaseTool):
    """
    Run the project's test suite, auto-detecting the framework.

    Returns the command used + truncated output. For long output, only
    the last ~100 lines are returned. If auto-detection fails, the caller
    can pass an explicit `command` (split on spaces) and the tool will
    just run that.
    """

    cwd: str = Field(default=".", description="Project directory.")
    command: str | None = Field(
        default=None,
        description=(
            "Optional explicit command override (e.g. 'pytest -k mytest' "
            "or 'npm run test:integration'). When unset, the tool detects "
            "the framework from project files."
        ),
    )
    timeout: int = Field(
        default=300,
        ge=10,
        le=1800,
        description="Hard timeout in seconds (10-1800). Default 5 minutes.",
    )

    def run(self) -> str:
        cwd_path = Path(self.cwd).resolve()
        if not cwd_path.is_dir():
            return f"Error: cwd {cwd_path} is not a directory."

        if self.command:
            label = self.command
            argv = self.command.split()
        else:
            detected = _detect_command(cwd_path)
            if not detected:
                return (
                    "Could not auto-detect test framework in "
                    f"{cwd_path}. Pass an explicit `command` (e.g. "
                    "'pytest', 'npm test', 'cargo test')."
                )
            label, argv = detected

        try:
            result = subprocess.run(
                argv,
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError:
            return f"Error: `{argv[0]}` not found in PATH. Is the framework installed?"
        except subprocess.TimeoutExpired:
            return f"`{label}` timed out after {self.timeout}s."

        # Truncate long output to keep token cost predictable.
        combined = (result.stdout or "") + (result.stderr or "")
        lines = combined.splitlines()
        if len(lines) > 100:
            tail = "\n".join(lines[-100:])
            output = f"... [{len(lines) - 100} earlier lines elided] ...\n{tail}"
        else:
            output = combined

        status = "passed" if result.returncode == 0 else f"failed (exit {result.returncode})"
        return f"$ {label}\n[{status}]\n{output}"
