"""Shared helpers and fixtures for the AnixOps-ansible test-suite.

Everything here is import-safe from test modules (``import conftest``) because
pytest prepends ``tests/`` to ``sys.path`` in its default import mode.  The
helpers only need git and PyYAML so the suite runs in a bare CI container in a
few seconds.  Results are cached per process: every file is read once and every
YAML document is parsed once.

Key helpers
-----------
* ``tracked_files()`` / ``tracked_text_files()`` / ``yaml_files()`` /
  ``role_dirs()`` / ``playbook_files()`` / ``task_files()``: enumerate what a
  commit would contain (``git ls-files --cached --others --exclude-standard``).
* ``load_yaml(path)``: multi-document aware; mappings come back as ``LineDict``
  objects that remember the 1-based ``line`` they started on, duplicate keys
  raise, Ansible's ``!vault``/``!unsafe`` tags are tolerated.
* ``iter_tasks(obj, path)``: yields ``(task_dict, path, location)`` for every
  task-like mapping in a playbook or task list, descending into
  pre_tasks/tasks/post_tasks/handlers and block/rescue/always.
* ``task_action()``, ``module_args()``, ``command_text()``, ``where()``:
  small accessors used by the structure tests to build file:line messages.
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROLES_DIR = REPO_ROOT / "roles"
PLAYBOOKS_DIR = REPO_ROOT / "playbooks"
INVENTORIES_DIR = REPO_ROOT / "inventories"
INTEGRATION_DIR = REPO_ROOT / "tests" / "integration"

YAML_SUFFIXES = (".yml", ".yaml")

BINARY_EXTENSIONS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp", ".svgz",
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".tar", ".jar",
        ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".class",
        ".db", ".sqlite", ".sqlite3", ".pickle", ".pkl",
    }
)

# ---------------------------------------------------------------------------
# Paths and git enumeration
# ---------------------------------------------------------------------------


def rel(path: Path | str) -> str:
    """Repo-relative POSIX path, used for parametrize ids and messages."""
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=True,
        capture_output=True,
    ).stdout


@functools.lru_cache(maxsize=None)
def tracked_files() -> tuple[Path, ...]:
    """Tracked files plus new, not-ignored files: what the next commit would contain.

    Files deleted from the working tree (but still in the index) and symlinks are
    skipped so concurrent deletions never break collection.
    """
    out = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    files: set[Path] = set()
    for raw in out.split(b"\0"):
        if not raw:
            continue
        path = REPO_ROOT / os.fsdecode(raw)
        if path.is_file() and not path.is_symlink():
            files.add(path)
    return tuple(sorted(files))


@functools.lru_cache(maxsize=None)
def git_index_modes() -> dict[str, str]:
    """Map of repo-relative path -> mode string (``100644``/``100755``) from the git index."""
    modes: dict[str, str] = {}
    for raw in _git("ls-files", "-s", "-z").split(b"\0"):
        if not raw:
            continue
        meta, _, name = raw.partition(b"\t")
        modes[os.fsdecode(name)] = meta.split()[0].decode()
    return modes


def git_ignores(relative_path: str) -> bool:
    """True when ``git check-ignore`` says *relative_path* would be ignored."""
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", "--", relative_path],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


@functools.lru_cache(maxsize=None)
def read_bytes(path: Path) -> bytes:
    return Path(path).read_bytes()


def read_text(path: Path) -> str:
    """UTF-8 text with undecodable bytes replaced (the hygiene tests check strictly)."""
    return read_bytes(path).decode("utf-8", errors="replace")


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return False
    return b"\0" not in read_bytes(path)[:8192]


@functools.lru_cache(maxsize=None)
def tracked_text_files() -> tuple[Path, ...]:
    return tuple(p for p in tracked_files() if is_text_file(p))


@functools.lru_cache(maxsize=None)
def yaml_files() -> tuple[Path, ...]:
    return tuple(p for p in tracked_text_files() if p.suffix.lower() in YAML_SUFFIXES)


def tracked_under(*parts: str, suffixes: tuple[str, ...] = YAML_SUFFIXES) -> tuple[Path, ...]:
    """Tracked text files below ``REPO_ROOT/parts...`` with one of *suffixes*."""
    base = REPO_ROOT.joinpath(*parts)
    return tuple(
        p for p in tracked_text_files() if p.suffix.lower() in suffixes and p.is_relative_to(base)
    )


@functools.lru_cache(maxsize=None)
def role_dirs() -> tuple[Path, ...]:
    """Role directories under roles/ that still contain at least one tracked file."""
    roles: set[Path] = set()
    for path in tracked_files():
        if path.is_relative_to(ROLES_DIR):
            parts = path.relative_to(ROLES_DIR).parts
            if len(parts) >= 2:  # roles/<role>/<anything>
                roles.add(ROLES_DIR / parts[0])
    return tuple(sorted(roles))


def role_name(path: Path) -> str | None:
    """Role name for any path inside ``roles/<role>/...``, else None."""
    if path.is_relative_to(ROLES_DIR):
        parts = path.relative_to(ROLES_DIR).parts
        if len(parts) >= 2:
            return parts[0]
    return None


def role_files(role_dir: Path, *subdirs: str) -> tuple[Path, ...]:
    """Tracked YAML files below ``roles/<role>/<subdir>`` for each *subdirs*."""
    out: list[Path] = []
    for sub in subdirs:
        out.extend(tracked_under("roles", role_dir.name, sub))
    return tuple(sorted(set(out)))


# ---------------------------------------------------------------------------
# YAML loading with line numbers
# ---------------------------------------------------------------------------


class LineDict(dict):
    """A dict that remembers the 1-based line of the YAML mapping it came from."""

    __slots__ = ("line",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.line: int | None = None


_BaseLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class RepoYamlLoader(_BaseLoader):  # type: ignore[misc,valid-type]
    """SafeLoader that records line numbers, rejects duplicate keys, tolerates Ansible tags."""

    def construct_yaml_map(self, node: yaml.Node) -> Iterator[LineDict]:
        data = LineDict()
        data.line = node.start_mark.line + 1
        yield data
        data.update(self.construct_mapping(node))

    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict:
        if isinstance(node, yaml.MappingNode):
            seen: dict[Any, int] = {}
            for key_node, _value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    continue
                key = self.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                except TypeError:
                    continue
                if key in seen:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key {key!r} (first defined on line {seen[key]})",
                        key_node.start_mark,
                    )
                seen[key] = key_node.start_mark.line + 1
        return super().construct_mapping(node, deep=deep)


RepoYamlLoader.add_constructor("tag:yaml.org,2002:map", RepoYamlLoader.construct_yaml_map)
for _tag in ("!vault", "!vault-encrypted", "!unsafe"):
    RepoYamlLoader.add_constructor(_tag, lambda loader, node: loader.construct_scalar(node))


@functools.lru_cache(maxsize=None)
def load_yaml(path: Path) -> list[Any]:
    """Every YAML document in *path* (multi-document aware). Raises ``yaml.YAMLError``."""
    text = read_text(path)
    if text.startswith("﻿"):
        text = text[1:]
    return list(yaml.load_all(text, Loader=RepoYamlLoader))


def load_yaml_document(path: Path) -> Any:
    """The first non-empty document of *path* (None when the file is empty)."""
    for doc in load_yaml(path):
        if doc is not None:
            return doc
    return None


def safe_load_yaml(path: Path) -> list[Any] | None:
    """Like ``load_yaml`` but returns None on parse errors (the hygiene suite reports those)."""
    try:
        return load_yaml(path)
    except yaml.YAMLError:
        return None


# ---------------------------------------------------------------------------
# Playbook / task walking
# ---------------------------------------------------------------------------

PLAY_TASK_SECTIONS = ("pre_tasks", "tasks", "post_tasks", "handlers")
NESTED_TASK_KEYS = ("block", "rescue", "always")

# Every keyword Ansible accepts on a task, block or handler (ansible-core 2.18
# ``Task/Block/Handler.fattributes``) plus the deprecated ``local_action``.
# Anything else on a task mapping is the module/action key. ``with_*`` lookups
# are matched by prefix in ``action_keys``.
TASK_KEYWORDS = frozenset(
    {
        "action", "always", "any_errors_fatal", "args", "async", "async_val",
        "become", "become_exe", "become_flags", "become_method", "become_user",
        "block", "changed_when", "check_mode", "collections", "connection",
        "debugger", "delay", "delegate_facts", "delegate_to", "diff",
        "environment", "failed_when", "ignore_errors", "ignore_unreachable",
        "listen", "local_action", "loop", "loop_control", "loop_with",
        "module_defaults", "name", "no_log", "notify", "poll", "port",
        "register", "remote_user", "rescue", "retries", "run_once", "tags",
        "throttle", "timeout", "until", "vars", "when",
    }
)


def is_play(obj: Any) -> bool:
    return isinstance(obj, dict) and "hosts" in obj


def is_block(task: dict) -> bool:
    return any(key in task for key in NESTED_TASK_KEYS)


def _join(prefix: str, part: str) -> str:
    return f"{prefix}.{part}" if prefix else part


def iter_tasks(
    obj: Any,
    path: Path | None = None,
    location: str = "",
) -> Iterator[tuple[dict, Path | None, str]]:
    """Yield ``(task_dict, path, location)`` for every task-like mapping in *obj*.

    *obj* may be a parsed playbook (list of plays), a task list (role tasks and
    handlers, included task files) or a single play/task mapping.  Plays are
    walked through pre_tasks/tasks/post_tasks/handlers; block containers are
    yielded themselves (ansible-lint treats them as tasks) and then descended
    through block/rescue/always.  ``location`` is a dotted path such as
    ``plays[0].tasks[3].block[1]``.  A top-level mapping without ``hosts``
    (a vars file) yields nothing.
    """
    if isinstance(obj, dict):
        if is_play(obj):
            for section in PLAY_TASK_SECTIONS:
                yield from iter_tasks(obj.get(section), path, _join(location, section))
            return
        if not location:  # bare top-level mapping: not a task file
            return
        yield obj, path, location
        for key in NESTED_TASK_KEYS:
            yield from iter_tasks(obj.get(key), path, _join(location, key))
        return
    if isinstance(obj, list):
        for index, item in enumerate(obj):
            if not isinstance(item, dict):
                continue
            prefix = location or ("plays" if is_play(item) else "tasks")
            yield from iter_tasks(item, path, f"{prefix}[{index}]")


def iter_file_tasks(path: Path) -> Iterator[tuple[dict, Path, str]]:
    """``iter_tasks`` over every document of a YAML file; unparsable files yield nothing."""
    docs = safe_load_yaml(path)
    if not docs:
        return
    for doc in docs:
        if isinstance(doc, list):
            yield from iter_tasks(doc, path)  # type: ignore[misc]


def iter_plays(path: Path) -> Iterator[tuple[dict, Path, str]]:
    """Yield ``(play_dict, path, location)`` for each play of a playbook file."""
    docs = safe_load_yaml(path)
    if not docs:
        return
    for doc in docs:
        if isinstance(doc, list):
            for index, item in enumerate(doc):
                if is_play(item):
                    yield item, path, f"plays[{index}]"


def is_playbook(path: Path) -> bool:
    docs = safe_load_yaml(path)
    if not docs:
        return False
    return any(isinstance(doc, list) and any(is_play(item) for item in doc) for doc in docs)


@functools.lru_cache(maxsize=None)
def playbook_files() -> tuple[Path, ...]:
    """YAML files under playbooks/ and tests/integration/ that contain plays."""
    candidates = tracked_under("playbooks") + tracked_under("tests", "integration")
    return tuple(p for p in candidates if is_playbook(p))


@functools.lru_cache(maxsize=None)
def role_task_files() -> tuple[Path, ...]:
    """roles/*/tasks/**/*.yml and roles/*/handlers/**/*.yml."""
    files = []
    for path in tracked_under("roles"):
        parts = path.relative_to(ROLES_DIR).parts
        if len(parts) >= 3 and parts[1] in ("tasks", "handlers"):
            files.append(path)
    return tuple(sorted(files))


@functools.lru_cache(maxsize=None)
def handler_files() -> tuple[Path, ...]:
    return tuple(p for p in role_task_files() if p.relative_to(ROLES_DIR).parts[1] == "handlers")


@functools.lru_cache(maxsize=None)
def task_files() -> tuple[Path, ...]:
    """Every YAML file that holds tasks or plays: role tasks/handlers, playbooks
    and the task files playbooks include (e.g. playbooks/maintenance/security-patch/*.yml)."""
    files = set(role_task_files())
    for path in tracked_under("playbooks") + tracked_under("tests", "integration"):
        docs = safe_load_yaml(path)
        if docs and any(isinstance(doc, list) for doc in docs):
            files.add(path)
    return tuple(sorted(files))


# ---------------------------------------------------------------------------
# Task accessors
# ---------------------------------------------------------------------------


def action_keys(task: dict) -> list[str]:
    """Keys of *task* that are not Ansible keywords: normally exactly the module name."""
    return [
        str(key)
        for key in task
        if str(key) not in TASK_KEYWORDS and not str(key).startswith("with_")
    ]


def task_action(task: dict) -> str | None:
    """Module/action name of a task (None for block containers or malformed tasks)."""
    if is_block(task):
        return None
    keys = action_keys(task)
    if len(keys) == 1:
        return keys[0]
    if keys:
        return None
    for keyword in ("action", "local_action"):
        value = task.get(keyword)
        if isinstance(value, str) and value.strip():
            return value.split()[0]
        if isinstance(value, dict) and isinstance(value.get("module"), str):
            return value["module"]
    return None


def short_action(action: str | None) -> str | None:
    """``ansible.builtin.copy`` -> ``copy``."""
    return action.rsplit(".", 1)[-1] if action else None


def module_args(task: dict, action: str | None) -> dict:
    """Merged module parameters: the module mapping (if any) plus the task's ``args:``.

    A free-form string value is exposed as ``_raw_params``.
    """
    merged: dict = {}
    if action is not None:
        value = task.get(action)
        if value is None and action in ("action", "local_action"):
            value = task.get(action)
        if isinstance(value, dict):
            merged.update(value)
        elif isinstance(value, str) and value.strip():
            merged["_raw_params"] = value
    extra = task.get("args")
    if isinstance(extra, dict):
        for key, val in extra.items():
            merged.setdefault(key, val)
    return merged


def command_text(task: dict, action: str | None) -> str:
    """The command string of a command/shell/raw task (``argv`` joined with spaces)."""
    args = module_args(task, action)
    for key in ("_raw_params", "cmd"):
        value = args.get(key)
        if isinstance(value, str):
            return value
    argv = args.get("argv")
    if isinstance(argv, list):
        return " ".join(str(item) for item in argv)
    return ""


JINJA_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)


def strip_jinja(text: str) -> str:
    return JINJA_RE.sub(" ", text)


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def where(path: Path | None, task: Any = None, location: str = "") -> str:
    """``roles/x/tasks/main.yml:12 (tasks[3].block[1])``: best-effort file:line pointer."""
    text = rel(path) if path is not None else "<memory>"
    line = getattr(task, "line", None)
    if line:
        text += f":{line}"
    if location:
        text += f" ({location})"
    return text


# ---------------------------------------------------------------------------
# Raw-text helpers (line finders)
# ---------------------------------------------------------------------------


def find_lines(path: Path, pattern: str | re.Pattern[str], flags: int = 0) -> list[tuple[int, str]]:
    """``[(lineno, line), ...]`` for every line of *path* matching *pattern*."""
    regex = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
    return [
        (number, line)
        for number, line in enumerate(read_text(path).splitlines(), start=1)
        if regex.search(line)
    ]


def find_line(path: Path, pattern: str | re.Pattern[str], flags: int = 0) -> int | None:
    hits = find_lines(path, pattern, flags)
    return hits[0][0] if hits else None


def strip_yaml_comment(line: str) -> str:
    """Remove a trailing ``# comment`` that is outside single/double quotes."""
    quote: str | None = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index].rstrip()
    return line


def format_problems(title: str, problems: list[str], limit: int = 25) -> str:
    """Multi-line assertion message: a headline plus up to *limit* bullet lines."""
    shown = problems[:limit]
    more = len(problems) - len(shown)
    lines = [f"{title} ({len(problems)} problem{'s' if len(problems) != 1 else ''}):"]
    lines += [f"  - {item}" for item in shown]
    if more > 0:
        lines.append(f"  ... and {more} more")
    return "\n".join(lines)


def ids_for(paths: tuple[Path, ...] | list[Path]) -> list[str]:
    return [rel(p) for p in paths]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(name="tracked_text_files", scope="session")
def _fixture_tracked_text_files() -> tuple[Path, ...]:
    return tracked_text_files()


@pytest.fixture(name="yaml_files", scope="session")
def _fixture_yaml_files() -> tuple[Path, ...]:
    return yaml_files()


@pytest.fixture(name="role_dirs", scope="session")
def _fixture_role_dirs() -> tuple[Path, ...]:
    return role_dirs()


@pytest.fixture(name="playbook_files", scope="session")
def _fixture_playbook_files() -> tuple[Path, ...]:
    return playbook_files()
