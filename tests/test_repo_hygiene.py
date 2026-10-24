"""Repository-wide text hygiene gate.

Every tracked (or new, not-ignored) text file must be plain UTF-8 without BOM,
use LF line endings, end with exactly one newline, carry no mojibake, no merge
conflict markers and no secrets.  YAML files must parse (duplicate keys count
as a parse error), contain no tabs and no trailing whitespace.  Shell scripts
need a shebang and the executable bit in the git index.

Each check is parametrized per file so a failure names the file, and messages
carry ``file:line`` pointers wherever a line is known.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

from conftest import (
    REPO_ROOT,
    find_lines,
    format_problems,
    git_ignores,
    git_index_modes,
    ids_for,
    load_yaml,
    read_bytes,
    read_text,
    rel,
    tracked_files,
    tracked_text_files,
    yaml_files,
)

pytestmark = pytest.mark.hygiene

TEXT_FILES = tracked_text_files()
YAML_FILES = yaml_files()
# Rendered YAML templates are YAML too as far as tabs/invisible characters go.
YAML_LIKE_FILES = tuple(
    p for p in TEXT_FILES
    if p.suffix.lower() in (".yml", ".yaml") or p.name.lower().endswith((".yml.j2", ".yaml.j2"))
)
SHELL_SCRIPTS = tuple(p for p in TEXT_FILES if p.suffix == ".sh")

TRAILING_WS_SUFFIXES = {".yml", ".yaml", ".py", ".sh", ".cfg", ".ini", ".toml", ".json", ".txt", ".example"}
TRAILING_WS_NAMES = {"VERSION", ".gitignore", ".ansible-lint", ".env.example", ".pre-commit-config.yaml"}
TRAILING_WS_FILES = tuple(
    p for p in TEXT_FILES if p.suffix.lower() in TRAILING_WS_SUFFIXES or p.name in TRAILING_WS_NAMES
)

INVISIBLE_SUFFIXES = {".yml", ".yaml", ".py", ".sh", ".cfg", ".ini", ".j2", ".toml"}
INVISIBLE_FILES = tuple(p for p in TEXT_FILES if p.suffix.lower() in INVISIBLE_SUFFIXES)

# Characters that only ever appear when UTF-8 Chinese was decoded as GBK, a
# CJK character directly followed by "?" (a lost trailing byte), "?" followed by
# any non-ASCII character, and the U+FFFD replacement character.  Written as
# escapes so this file never trips its own check.
MOJIBAKE_RE = re.compile(
    "[鈺鏈閮鐨锛銆鍏鎴浠璁鍙鐢閰鏂鍚鍒鍥]"
    "|[一-鿿]\\?"
    "|\\?[^\\x00-\\x7f]"
    "|�"
)
INVISIBLE_RE = re.compile("[ ​‌‍⁠﻿]")
CONFLICT_RE = re.compile(r"^(?:<{7} |>{7} |\|{7} )")

_PEM_HEADER = "-----BEGIN " + r"(?:RSA |OPENSSH |EC |DSA |ENCRYPTED )?PRIVATE KEY" + "-----"
SECRET_PATTERNS = (
    # A header alone is documentation; a header followed by base64 material is a key.
    ("private key material", re.compile(_PEM_HEADER + r"[ \t]*\r?\n[ \t]*[A-Za-z0-9+/=]{40,}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20}\b")),
    ("Anthropic/OpenAI style key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{24,}\b")),
)
PLACEHOLDER_RE = re.compile(r"(.)\1{5,}|xxxx|example|placeholder|replace|change_?me|your[_-]|dummy|sample", re.I)

FORBIDDEN_TRACKED_NAMES = {".env", ".vault_password.txt", ".vault_pass", "vault_password.txt", "vault.pass"}
FORBIDDEN_TRACKED_SUFFIXES = {".pem", ".p12", ".pfx"}
FORBIDDEN_TRACKED_PREFIXES = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")


def _line_of_offset(data: bytes, offset: int) -> int:
    return data.count(b"\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# Encoding and line endings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", TEXT_FILES, ids=ids_for(TEXT_FILES))
def test_decodes_as_utf8(path: Path) -> None:
    data = read_bytes(path)
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = _line_of_offset(data, exc.start)
        pytest.fail(
            f"{rel(path)}:{line}: not valid UTF-8 at byte offset {exc.start} "
            f"({data[exc.start:exc.start + 8]!r}): {exc.reason}. Re-save the file as UTF-8."
        )


@pytest.mark.parametrize("path", TEXT_FILES, ids=ids_for(TEXT_FILES))
def test_no_utf8_bom(path: Path) -> None:
    data = read_bytes(path)
    assert not data.startswith(b"\xef\xbb\xbf"), (
        f"{rel(path)}:1: starts with a UTF-8 BOM (EF BB BF); strip it: "
        f"sed -i '1s/^\\xEF\\xBB\\xBF//' {rel(path)}"
    )


@pytest.mark.parametrize("path", TEXT_FILES, ids=ids_for(TEXT_FILES))
def test_no_crlf_line_endings(path: Path) -> None:
    data = read_bytes(path)
    offset = data.find(b"\r")
    assert offset == -1, (
        f"{rel(path)}:{_line_of_offset(data, offset)}: carriage return found; "
        f"convert to LF line endings (e.g. `sed -i 's/\\r$//' {rel(path)}`)"
    )


@pytest.mark.parametrize("path", TEXT_FILES, ids=ids_for(TEXT_FILES))
def test_ends_with_exactly_one_newline(path: Path) -> None:
    data = read_bytes(path)
    if not data:
        return  # empty files are fine
    last_line = data.count(b"\n") + (0 if data.endswith(b"\n") else 1)
    assert data.endswith(b"\n"), f"{rel(path)}:{last_line}: missing trailing newline at end of file"
    assert not data.endswith(b"\n\n"), (
        f"{rel(path)}:{last_line}: more than one trailing newline at end of file; keep exactly one"
    )


# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", YAML_LIKE_FILES, ids=ids_for(YAML_LIKE_FILES))
def test_no_tabs_in_yaml(path: Path) -> None:
    hits = find_lines(path, "\t")
    assert not hits, format_problems(
        f"{rel(path)}: tab characters are not allowed in YAML (use two spaces)",
        [f"{rel(path)}:{number}: {line.rstrip()!r}" for number, line in hits],
        limit=10,
    )


@pytest.mark.parametrize("path", TRAILING_WS_FILES, ids=ids_for(TRAILING_WS_FILES))
def test_no_trailing_whitespace(path: Path) -> None:
    hits = find_lines(path, r"[ \t]+$")
    assert not hits, format_problems(
        f"{rel(path)}: trailing whitespace",
        [f"{rel(path)}:{number}: {line.rstrip()!r}" for number, line in hits],
        limit=10,
    )


@pytest.mark.parametrize("path", INVISIBLE_FILES, ids=ids_for(INVISIBLE_FILES))
def test_no_invisible_unicode_characters(path: Path) -> None:
    hits = find_lines(path, INVISIBLE_RE)
    assert not hits, format_problems(
        f"{rel(path)}: non-breaking / zero-width / BOM characters inside the file",
        [
            f"{rel(path)}:{number}: contains U+{ord(INVISIBLE_RE.search(line).group(0)):04X}"
            for number, line in hits
        ],
        limit=10,
    )


# ---------------------------------------------------------------------------
# Content sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", TEXT_FILES, ids=ids_for(TEXT_FILES))
def test_no_mojibake(path: Path) -> None:
    hits = find_lines(path, MOJIBAKE_RE)
    assert not hits, format_problems(
        f"{rel(path)}: mojibake (UTF-8 text decoded as GBK, or a lost byte shown as '?'); "
        "the original text cannot be recovered: rewrite the comment/string from scratch",
        [f"{rel(path)}:{number}: {line.strip()[:100]!r}" for number, line in hits],
        limit=10,
    )


@pytest.mark.parametrize("path", TEXT_FILES, ids=ids_for(TEXT_FILES))
def test_no_merge_conflict_markers(path: Path) -> None:
    hits = find_lines(path, CONFLICT_RE)
    assert not hits, format_problems(
        f"{rel(path)}: unresolved merge conflict markers",
        [f"{rel(path)}:{number}: {line.rstrip()!r}" for number, line in hits],
    )


@pytest.mark.parametrize("path", TEXT_FILES, ids=ids_for(TEXT_FILES))
def test_no_secret_looking_strings(path: Path) -> None:
    text = read_text(path)
    problems = []
    for label, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(0)
            if PLACEHOLDER_RE.search(token):
                continue
            line = text.count("\n", 0, match.start()) + 1
            problems.append(f"{rel(path)}:{line}: looks like a {label} ({token[:12]}...)")
    assert not problems, format_problems(
        f"{rel(path)}: possible committed secret; remove it, rotate it and use vault/CI secrets",
        problems,
    )


# ---------------------------------------------------------------------------
# Shell scripts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", SHELL_SCRIPTS, ids=ids_for(SHELL_SCRIPTS))
def test_shell_script_has_shebang(path: Path) -> None:
    first_line = read_text(path).splitlines()[0] if read_bytes(path) else ""
    assert first_line.startswith("#!"), (
        f"{rel(path)}:1: shell scripts must start with a shebang (e.g. '#!/usr/bin/env bash'), "
        f"found {first_line[:40]!r}"
    )


@pytest.mark.parametrize("path", SHELL_SCRIPTS, ids=ids_for(SHELL_SCRIPTS))
def test_shell_script_is_executable(path: Path) -> None:
    index_mode = git_index_modes().get(rel(path))
    if index_mode is not None:
        assert index_mode == "100755", (
            f"{rel(path)}: tracked with mode {index_mode}; a clone will not be able to run it. "
            f"Fix with: git update-index --chmod=+x {rel(path)}"
        )
    else:  # new file not yet in the index: check the working tree bit
        assert os.access(path, os.X_OK), f"{rel(path)}: not executable; run chmod +x {rel(path)}"


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", YAML_FILES, ids=ids_for(YAML_FILES))
def test_yaml_parses(path: Path) -> None:
    try:
        load_yaml(path)
    except yaml.YAMLError as exc:
        message = str(exc).replace('"<unicode string>"', rel(path))
        pytest.fail(f"{rel(path)}: YAML does not parse (duplicate keys count as errors):\n{message}")


# ---------------------------------------------------------------------------
# Tracked-file policy
# ---------------------------------------------------------------------------


def test_no_secret_files_tracked() -> None:
    names = set(git_index_modes()) | {rel(p) for p in tracked_files()}
    offenders = sorted(
        name
        for name in names
        if Path(name).name in FORBIDDEN_TRACKED_NAMES
        or Path(name).suffix in FORBIDDEN_TRACKED_SUFFIXES
        or (Path(name).name.startswith(FORBIDDEN_TRACKED_PREFIXES) and not name.endswith(".pub"))
    )
    assert not offenders, format_problems(
        "secret-bearing files must never be tracked (git rm --cached them and rotate the secrets)",
        offenders,
    )


@pytest.mark.parametrize("relative", [".env", "inventories/.env", ".vault_password.txt", "id_rsa.pem"])
def test_secret_files_are_gitignored(relative: str) -> None:
    assert git_ignores(relative), (
        f"{relative} is not covered by .gitignore; add it so a local copy can never be committed"
    )


def test_env_example_exists_and_has_no_values_for_secrets() -> None:
    example = REPO_ROOT / ".env.example"
    assert example.is_file(), ".env.example is missing; operators need it to bootstrap a local .env"
    problems = []
    for number, line in enumerate(read_text(example).splitlines(), start=1):
        match = re.match(r"^\s*(?:export\s+)?([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PRIVATE_KEY|API_KEY)[A-Z0-9_]*)=(.*)$", line)
        if not match:
            continue
        value = match.group(2).split("#", 1)[0].strip().strip("\"'")
        if value and not PLACEHOLDER_RE.search(value) and len(value) >= 12:
            problems.append(f".env.example:{number}: {match.group(1)} has a real-looking value")
    assert not problems, format_problems(".env.example must only contain placeholders", problems)
