#!/usr/bin/env python3
"""Export allow-listed GitHub Actions secrets into ``GITHUB_ENV``.

The ``secrets`` context cannot be iterated inside a workflow expression, so the
caller passes it serialised (``toJSON(secrets)``) through the ``SECRETS_JSON``
environment variable. Every secret whose NAME matches ``ALLOW_PATTERN`` is
appended to the file named by ``GITHUB_ENV`` using the multi-line heredoc
syntax, so values that contain newlines (PEM certificates, SSH keys) survive.

Only the names of exported secrets are ever printed; values never reach the
log (GitHub masks them anyway, but we do not rely on that).
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from typing import Dict, Iterable, List, Mapping, TextIO

# GitHub secret names are already restricted to this shape; enforcing it again
# guarantees nothing but a well-formed environment variable name can be written.
VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Never exported, whatever the allow-list says: the token must stay with the
# steps that explicitly request it through `${{ github.token }}`.
ALWAYS_DENIED = {"github_token"}


def select_secrets(secrets: Mapping[str, object], allow_pattern: str) -> Dict[str, str]:
    """Return ``{name: value}`` for every non-empty secret whose name matches."""
    regex = re.compile(allow_pattern)
    selected: Dict[str, str] = {}
    for name in sorted(secrets):
        if name.lower() in ALWAYS_DENIED or not VALID_NAME.match(name):
            continue
        if not regex.search(name):
            continue
        value = secrets[name]
        if value is None or str(value) == "":
            continue
        selected[name] = str(value)
    return selected


def render_env_block(name: str, value: str) -> str:
    """Render one ``NAME<<DELIM`` heredoc block understood by GITHUB_ENV."""
    delimiter = f"__ANIXOPS_SECRET_{uuid.uuid4().hex}__"
    while delimiter in value:  # pragma: no cover - astronomically unlikely
        delimiter = f"__ANIXOPS_SECRET_{uuid.uuid4().hex}__"
    return f"{name}<<{delimiter}\n{value}\n{delimiter}\n"


def write_github_env(selected: Mapping[str, str], handle: TextIO) -> List[str]:
    """Append every selected secret to ``handle`` and return the names written."""
    written: List[str] = []
    for name, value in selected.items():
        handle.write(render_env_block(name, value))
        written.append(name)
    return written


def summarise(written: Iterable[str], total: int) -> str:
    names = list(written)
    header = f"Exported {len(names)} of {total} secrets to GITHUB_ENV (names only, values are never logged)."
    if not names:
        return header
    return header + "\n  " + "\n  ".join(names)


def main() -> int:
    raw = os.environ.get("SECRETS_JSON", "")
    allow_pattern = os.environ.get("ALLOW_PATTERN", "")
    github_env = os.environ.get("GITHUB_ENV", "")
    github_output = os.environ.get("GITHUB_OUTPUT", "")

    if not raw:
        print("::error::SECRETS_JSON is empty; pass secrets-json: ${{ toJSON(secrets) }}", file=sys.stderr)
        return 1
    if not allow_pattern:
        print("::error::ALLOW_PATTERN is empty", file=sys.stderr)
        return 1
    if not github_env:
        print("::error::GITHUB_ENV is not set; this script only runs inside GitHub Actions", file=sys.stderr)
        return 1

    try:
        secrets = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"::error::SECRETS_JSON is not valid JSON: {exc.msg}", file=sys.stderr)
        return 1
    if not isinstance(secrets, dict):
        print("::error::SECRETS_JSON must be a JSON object", file=sys.stderr)
        return 1

    try:
        selected = select_secrets(secrets, allow_pattern)
    except re.error as exc:
        print(f"::error::ALLOW_PATTERN is not a valid regular expression: {exc}", file=sys.stderr)
        return 1

    with open(github_env, "a", encoding="utf-8") as handle:
        written = write_github_env(selected, handle)

    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write("exported-names=" + ",".join(written) + "\n")
            handle.write(f"exported-count={len(written)}\n")

    print(summarise(written, len(secrets)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
