"""Internal helper — runs git commands with a timeout and a clean error string."""

from __future__ import annotations

import subprocess


def run_git(args: list[str], cwd: str = ".", timeout: int = 15) -> str:
    """Run `git <args>` in cwd. Return stdout, or a friendly error string."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return "Error: `git` not found in PATH."
    except subprocess.TimeoutExpired:
        return f"Error: `git {' '.join(args)}` timed out after {timeout}s."
    except Exception as exc:  # noqa: BLE001
        return f"Error running git: {type(exc).__name__}: {exc}"

    if result.returncode != 0:
        # Many git failures (not a repo, no commits yet, etc.) come through stderr.
        return f"git {' '.join(args)} failed (exit {result.returncode}):\n{result.stderr.strip() or result.stdout.strip()}"
    return result.stdout
