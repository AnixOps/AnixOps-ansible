"""Repository-wide text hygiene gate.

Every tracked (or new, not-ignored) text file must be plain UTF-8 without BOM,
use LF line endings, end with exactly one newline, carry no mojibake, no merge
conflict markers and no secrets.  YAML files must parse (duplicate keys count
as a parse error), contain no tabs and no trailing whitespace.  Shell scripts
need a shebang and the executable bit in the git index.

Each check is parametrized per file so a failure names the file, and messages
carry ``file:line`` pointers wherever a line is known.  This source file is
kept pure ASCII (non-ASCII characters are built with ``chr()``) so it can never
trip its own checks.
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
# Rendered YAML templates are YAML too as far as tabs go.
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

# --- mojibake detection -----------------------------------------------------
# Characters that only ever appear when UTF-8 Chinese was decoded as GBK
# (the coordinator's list), plus a structural heuristic: GBK-decoding UTF-8
# bytes (E4..E9 lead bytes) can only produce GB2312 level-2 / GBK-extension
# characters (GBK lead byte outside B0..D7), whereas genuine simplified Chinese
# is dominated by level-1 characters (lead byte B0..D7).  A run of CJK
# characters with no level-1 character is therefore garbage, and a "?" next to
# such characters is a lost byte rather than punctuation.
GBK_MOJIBAKE_CHARS = "".join(chr(cp) for cp in (
    0x923A, 0x93C8, 0x95AE, 0x9428, 0x951B, 0x9286, 0x934F, 0x93B4, 0x6D60,
    0x7481, 0x9359, 0x9422, 0x95B0, 0x93C2, 0x935A, 0x9352, 0x9365,
))
CJK = chr(0x4E00) + "-" + chr(0x9FFF)
EURO = chr(0x20AC)  # GBK byte 0x80 decodes to the euro sign; it shows up inside garbage runs
REPLACEMENT_CHAR = chr(0xFFFD)
MOJIBAKE_CHAR_RE = re.compile("[" + GBK_MOJIBAKE_CHARS + REPLACEMENT_CHAR + "]")
CJK_RUN_RE = re.compile("[" + CJK + "]+")
CJK_QUESTION_RE = re.compile("([" + CJK + "]+)\\?")
QUESTION_NON_ASCII_RE = re.compile("\\?([^\\x00-\\x7f])")
EURO_NEAR_CJK_RE = re.compile("[" + CJK + "]" + EURO + "|" + EURO + "[" + CJK + "]")


def _is_common_hanzi(char: str) -> bool:
    """GB2312 level-1 character (GBK lead byte B0..D7): the bulk of real simplified text."""
    try:
        return 0xB0 <= char.encode("gbk")[0] <= 0xD7
    except UnicodeEncodeError:
        return False


def _looks_garbled(run: str) -> bool:
    common = sum(1 for char in run if _is_common_hanzi(char))
    return common * 2 < len(run)


def _garbage_run(run: str) -> bool:
    """3+ CJK chars without a single common hanzi, or 5+ with at most a quarter common."""
    common = sum(1 for char in run if _is_common_hanzi(char))
    return (len(run) >= 3 and common == 0) or (len(run) >= 5 and common * 4 <= len(run))


def mojibake_problems(text: str) -> list[tuple[int, str, str]]:
    """``[(lineno, reason, snippet), ...]`` for every line that carries mojibake."""
    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        reason = None
        if MOJIBAKE_CHAR_RE.search(line):
            reason = "GBK-decoded UTF-8 character"
        elif any(_garbage_run(m.group(0)) for m in CJK_RUN_RE.finditer(line)):
            reason = "run of CJK characters with (almost) no common hanzi (GBK-decoded UTF-8)"
        elif any(_looks_garbled(m.group(1)[-4:]) for m in CJK_QUESTION_RE.finditer(line)):
            reason = "'?' right after garbled CJK text (lost byte)"
        elif any(not (CJK_RUN_RE.match(m.group(1)) and _is_common_hanzi(m.group(1)))
                 for m in QUESTION_NON_ASCII_RE.finditer(line)):
            reason = "'?' followed by a non-ASCII character (lost byte)"
        elif EURO_NEAR_CJK_RE.search(line):
            reason = "euro sign glued to CJK text (GBK byte 0x80)"
        if reason:
            problems.append((number, reason, line.strip()[:100]))
    return problems


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
def test_encoding_and_line_endings(path: Path) -> None:
    """UTF-8 without BOM, LF only, exactly one trailing newline (empty files are fine)."""
    data = read_bytes(path)
    name = rel(path)
    problems: list[str] = []
    if data.startswith(b"\xef\xbb\xbf"):
        problems.append(f"{name}:1: starts with a UTF-8 BOM (bytes EF BB BF); re-save as UTF-8 without BOM")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        problems.append(
            f"{name}:{_line_of_offset(data, exc.start)}: not valid UTF-8 at byte offset {exc.start} "
            f"({data[exc.start:exc.start + 8]!r}): {exc.reason}; re-save the file as UTF-8"
        )
    offset = data.find(b"\r")
    if offset != -1:
        problems.append(f"{name}:{_line_of_offset(data, offset)}: carriage return found; convert to LF (dos2unix)")
    if data:
        last_line = data.count(b"\n") + (0 if data.endswith(b"\n") else 1)
        if not data.endswith(b"\n"):
            problems.append(f"{name}:{last_line}: missing trailing newline at end of file")
        elif data.endswith(b"\n\n"):
            problems.append(f"{name}:{last_line}: more than one trailing newline at end of file; keep exactly one")
    assert not problems, format_problems(f"{name}: encoding / line endings", problems)


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


INVISIBLE_RE = re.compile("[" + "".join(chr(cp) for cp in (0x00A0, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)) + "]")


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
    hits = mojibake_problems(read_text(path))
    assert not hits, format_problems(
        f"{rel(path)}: mojibake (UTF-8 text that was decoded as GBK, or a lost byte shown as '?'); "
        "the original text cannot be recovered: rewrite the comment/string from scratch",
        [f"{rel(path)}:{number}: {reason}: {snippet!r}" for number, reason, snippet in hits],
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
        match = re.match(
            r"^\s*(?:export\s+)?([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PRIVATE_KEY|API_KEY)[A-Z0-9_]*)=(.*)$", line
        )
        if not match:
            continue
        value = match.group(2).split("#", 1)[0].strip().strip("\"'")
        if value and not PLACEHOLDER_RE.search(value) and len(value) >= 12:
            problems.append(f".env.example:{number}: {match.group(1)} has a real-looking value")
    assert not problems, format_problems(".env.example must only contain placeholders", problems)
