"""Git introspection tools shared across swarms.

Lightweight wrappers around the `git` binary. Lives under `_common/`
because more than one swarm needs them (softdev for code review and
incident-response workflows; technical_docs for ADR / release-notes
generation off recent commits). Moved here from softdev/shared_tools/
in fix-all-issues Commit 4 — that boundary violation (technical_docs
importing across into softdev) is what H5 in the original code review
flagged.
"""

from swarms._common.git_tools.GitDiff import GitDiff
from swarms._common.git_tools.GitLog import GitLog
from swarms._common.git_tools.GitStatus import GitStatus

__all__ = ["GitDiff", "GitLog", "GitStatus"]
