"""Run a registered swarm to completion and return its result.

Subroutine-style delegation: builds a fresh sub-agency, runs it
synchronously against the task, and returns the final string output.
The sub-agency is discarded after the run — no thread state survives.

This is distinct from `SwitchSwarm`, which migrates the user's whole
session to a different swarm. Use `DispatchToSwarm` for "do this
discrete piece of work and bring me the result"; use `SwitchSwarm` for
"the user wants to keep working in that domain."

Audit log (M6 / fix-all-issues Commit 6): every dispatch writes a
JSON line to `.omc/logs/dispatch.jsonl` so it's possible to reconstruct
*which* sub-swarm did *what* without re-tracing a model conversation.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field


_DEFAULT_AUDIT_PATH = Path(".omc") / "logs" / "dispatch.jsonl"


def _audit_path() -> Path:
    """Resolve the dispatch-audit log path.

    Override via OSWARM_DISPATCH_LOG for tests or alternative layouts.
    Defaults to `.omc/logs/dispatch.jsonl` under the current working
    directory (which is the repo root when launched via `bin/oswarm`).

    Path-traversal defense: the override must resolve under either
    the current working directory or the system temp directory.
    Anything else (`/etc/cron.d/...`, `/home/other-user/...`, etc.)
    falls back to the default. This prevents a hostile env var from
    corrupting privileged files when the launcher happens to run
    with elevated permissions. The system-temp escape hatch keeps
    `pytest`'s `tmp_path`-based fixtures working.
    """
    override = os.environ.get("OSWARM_DISPATCH_LOG")
    if not override:
        return _DEFAULT_AUDIT_PATH

    try:
        candidate = Path(override).resolve()
    except OSError:
        return _DEFAULT_AUDIT_PATH

    allowed_roots = [Path.cwd().resolve()]
    try:
        import tempfile
        allowed_roots.append(Path(tempfile.gettempdir()).resolve())
    except OSError:
        pass
    # macOS aliases /var/folders/... — resolve covers it; also accept
    # /private/var which is the real backing path.
    if Path("/private/var").exists():
        try:
            allowed_roots.append(Path("/private/var").resolve())
        except OSError:
            pass

    for root in allowed_roots:
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    return _DEFAULT_AUDIT_PATH


def _write_audit_event(event: dict) -> None:
    """Append one JSON line to the audit log. Best-effort — log failures
    must not block a successful dispatch."""
    path = _audit_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        # Disk full, permission denied, /etc/nologin — don't propagate.
        pass


class DispatchToSwarm(BaseTool):
    """
    Run a sub-swarm to completion against a task and return its final output.

    The sub-swarm is built fresh for this call (its own agency, its own
    threads) and is discarded when the call returns. Token cost mirrors a
    full conversation in that swarm — only dispatch when the work is
    discrete and completable in one pass.
    """

    swarm: str = Field(
        ...,
        description=(
            "Slug of the sub-swarm to run. See swarms/__init__.py for the "
            "registry — e.g. 'openswarm', 'softdev'. Cannot be 'metaswarm' "
            "(no recursive self-dispatch)."
        ),
    )
    task: str = Field(
        ...,
        min_length=1,
        description=(
            "The task to give the sub-swarm. Phrase it as if you were "
            "writing a clear, self-contained brief — the sub-swarm has no "
            "memory of this conversation. Include constraints, expected "
            "output format, and any file paths the sub-swarm should "
            "operate on."
        ),
    )

    def run(self) -> str:
        slug = self.swarm.strip().lower()
        started_at = time.time()

        # Lazy import: keeps tool-load fast, avoids circulars with the registry
        from swarms import SWARMS, get_factory

        if slug == "metaswarm":
            msg = (
                "Refusing dispatch: cannot recursively dispatch to metaswarm. "
                "Dispatch to a leaf swarm (e.g. openswarm or softdev) instead."
            )
            _write_audit_event({
                "ts": started_at,
                "swarm": slug,
                "outcome": "refused",
                "reason": "recursive_metaswarm",
                "task_len": len(self.task),
            })
            return msg
        if slug not in SWARMS:
            msg = (
                f"Unknown swarm '{self.swarm}'. Available: "
                f"{', '.join(s for s in SWARMS if s != 'metaswarm')}."
            )
            _write_audit_event({
                "ts": started_at,
                "swarm": slug,
                "outcome": "refused",
                "reason": "unknown_swarm",
                "task_len": len(self.task),
            })
            return msg

        try:
            factory = get_factory(slug)
            sub_agency = factory()
        except Exception as exc:
            _write_audit_event({
                "ts": started_at,
                "swarm": slug,
                "outcome": "construct_failed",
                "error_type": type(exc).__name__,
                "task_len": len(self.task),
                "elapsed_ms": int((time.time() - started_at) * 1000),
            })
            return (
                f"Failed to construct sub-swarm '{slug}': "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            result = sub_agency.get_response_sync(self.task)
        except Exception as exc:
            _write_audit_event({
                "ts": started_at,
                "swarm": slug,
                "outcome": "execution_failed",
                "error_type": type(exc).__name__,
                "task_len": len(self.task),
                "elapsed_ms": int((time.time() - started_at) * 1000),
            })
            return (
                f"Sub-swarm '{slug}' raised {type(exc).__name__} during "
                f"execution: {exc}"
            )

        # RunResult exposes the final assistant text via .final_output on
        # current openai-agents-sdk; fall back to str() for safety.
        output = getattr(result, "final_output", None) or str(result)
        _write_audit_event({
            "ts": started_at,
            "swarm": slug,
            "outcome": "success",
            "task_len": len(self.task),
            "output_len": len(output),
            "elapsed_ms": int((time.time() - started_at) * 1000),
        })
        return f"[{slug}] {output}"
