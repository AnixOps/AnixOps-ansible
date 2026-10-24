#!/usr/bin/env python3
"""Backup coverage gate | 备份覆盖率检查

Every ``template`` / ``copy`` task that writes a configuration file under
``/etc`` must set ``backup: true``; the ``*.backup.<timestamp>`` files this
produces are what ``playbooks/maintenance/rollback.yml`` restores when a
roll-out goes wrong.

How it works
------------
* Task files are parsed with PyYAML (no regex heuristics). ``block`` /
  ``rescue`` / ``always`` sections are walked recursively; playbooks are
  walked through ``pre_tasks`` / ``tasks`` / ``post_tasks`` / ``handlers``.
* Both the dictionary form (``dest: /etc/x``) and the free-form string form
  (``template: src=a dest=/etc/x``) are understood, as is a task-level
  ``args:`` block.
* A ``dest`` that starts with ``{{ some_var }}`` is resolved against the
  role's ``defaults/main.yml`` and ``vars/main.yml`` when that variable is a
  plain string (e.g. ``v2board_config_dir: /etc/v2board``).
* Static content (HTML, CSS, images, fonts) and backup copies
  (``*.backup.*``, ``*.bak``, ``*.orig``) are not configuration and are skipped.
* Rescue tasks that restore a previous backup (``copy`` with ``remote_src: true``
  and a ``src`` of ``{{ result.backup_file }}`` or ``*.backup.*``) are the
  rollback itself and are not gated.

Opt-out
-------
Add ``<repo-relative path>:<task name>`` to
``scripts/backup-coverage-allowlist.txt`` (glob patterns allowed, see the
header of that file). Unused allowlist entries are reported as warnings so the
list cannot rot silently.

Usage
-----
    python3 scripts/check-backup-coverage.py
    python3 scripts/check-backup-coverage.py --format github
    python3 scripts/check-backup-coverage.py --roles-dir roles --playbooks-dir playbooks

Exit codes
----------
    0  no findings
    1  findings (missing backup, explicit ``backup: false``, YAML parse error)
    2  usage error
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard requirement
    sys.stderr.write("PyYAML is required: pip install -r requirements.txt\n")
    sys.exit(2)

# --- Configuration -----------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALLOWLIST = REPO_ROOT / "scripts" / "backup-coverage-allowlist.txt"

#: Modules that write files and support ``backup``.
MODULES = frozenset(
    {
        "template",
        "copy",
        "ansible.builtin.template",
        "ansible.builtin.copy",
        "ansible.legacy.template",
        "ansible.legacy.copy",
    }
)

#: Destination prefixes that are considered configuration.
PROTECTED_PREFIXES: Tuple[str, ...] = ("/etc/",)

#: Static content: never configuration, no backup needed.
CONTENT_EXTENSIONS = re.compile(
    r"\.(html?|css|js|map|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|eot|otf|pdf)$",
    re.IGNORECASE,
)

#: Destinations that are themselves backup copies.
BACKUP_COPY = re.compile(r"(\.backup(\.|$)|\.bak$|\.orig$|~$)", re.IGNORECASE)

SKIP_DIRS = {".git", ".tox", "__pycache__", "venv", ".venv", "node_modules", "molecule"}
TASK_LIST_KEYS = ("pre_tasks", "tasks", "post_tasks", "handlers")
NESTED_KEYS = ("block", "rescue", "always")
PLAY_KEYS = ("hosts", "import_playbook", "ansible.builtin.import_playbook")
JINJA_PREFIX = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
TRUE_WORDS = {"true", "yes", "on", "1"}
FALSE_WORDS = {"false", "no", "off", "0"}

KIND_MISSING = "missing-backup"
KIND_DISABLED = "backup-disabled"
KIND_YAML = "yaml-error"


# --- YAML loading with line numbers ------------------------------------------
class LineDict(dict):
    """A dict that remembers the line its mapping started on."""

    __slots__ = ("line",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.line = 0


class _LineLoader(yaml.SafeLoader):
    """SafeLoader that records line numbers and tolerates Ansible tags."""


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.Node) -> Iterator[LineDict]:
    data = LineDict()
    data.line = node.start_mark.line + 1
    yield data
    data.update(loader.construct_mapping(node))


def _construct_tagged(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> Any:
    # !vault / !unsafe and friends: keep the payload, drop the tag.
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_LineLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)
_LineLoader.add_multi_constructor("!", _construct_tagged)


def load_yaml_documents(path: Path) -> List[Any]:
    """Load every YAML document in *path* (mappings carry ``.line``)."""
    with path.open("r", encoding="utf-8") as handle:
        return list(yaml.load_all(handle, Loader=_LineLoader))  # noqa: S506 - SafeLoader subclass


# --- Data model --------------------------------------------------------------
@dataclass
class Finding:
    path: str
    line: int
    task: str
    dest: str
    kind: str
    message: str

    def key(self) -> Tuple[str, str]:
        return (self.path, self.task)


@dataclass
class AllowlistEntry:
    path_pattern: str
    task_pattern: str
    source_line: int

    def matches(self, finding: Finding) -> bool:
        return fnmatch.fnmatchcase(finding.path, self.path_pattern) and fnmatch.fnmatchcase(
            finding.task, self.task_pattern
        )


@dataclass
class Report:
    findings: List[Finding] = field(default_factory=list)
    allowlisted: List[Finding] = field(default_factory=list)
    unused_allowlist: List[AllowlistEntry] = field(default_factory=list)
    files_scanned: int = 0
    tasks_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings


# --- Helpers -----------------------------------------------------------------
def find_yaml_files(directory: Path) -> List[Path]:
    """All ``*.yml`` / ``*.yaml`` files below *directory*, sorted."""
    if not directory.is_dir():
        return []
    files: List[Path] = []
    for root, dirs, names in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in names:
            if name.endswith((".yml", ".yaml")):
                files.append(Path(root) / name)
    return sorted(files)


def is_role_task_file(path: Path, roles_dir: Path) -> bool:
    """Only tasks/ and handlers/ of a role contain tasks (not defaults, vars, meta...)."""
    try:
        rel = path.relative_to(roles_dir)
    except ValueError:
        return False
    return len(rel.parts) >= 3 and rel.parts[1] in ("tasks", "handlers")


def role_dir_for(path: Path, roles_dir: Path) -> Optional[Path]:
    try:
        rel = path.relative_to(roles_dir)
    except ValueError:
        return None
    return roles_dir / rel.parts[0] if rel.parts else None


_ROLE_VARS_CACHE: Dict[Path, Dict[str, str]] = {}


def load_role_vars(role_dir: Optional[Path]) -> Dict[str, str]:
    """String-valued variables from ``defaults/main.yml`` + ``vars/main.yml`` (vars win)."""
    if role_dir is None:
        return {}
    if role_dir in _ROLE_VARS_CACHE:
        return _ROLE_VARS_CACHE[role_dir]
    variables: Dict[str, str] = {}
    for sub in ("defaults", "vars"):
        for candidate in (role_dir / sub / "main.yml", role_dir / sub / "main.yaml"):
            if not candidate.is_file():
                continue
            try:
                docs = load_yaml_documents(candidate)
            except yaml.YAMLError:
                continue
            for doc in docs:
                if isinstance(doc, dict):
                    for key, value in doc.items():
                        if isinstance(key, str) and isinstance(value, str):
                            variables[key] = value
    _ROLE_VARS_CACHE[role_dir] = variables
    return variables


def resolve_dest(dest: str, variables: Dict[str, str], depth: int = 0) -> str:
    """Expand a leading ``{{ var }}`` when *var* is a plain string in *variables*."""
    match = JINJA_PREFIX.match(dest)
    if not match or depth > 4:
        return dest
    value = variables.get(match.group(1))
    if not isinstance(value, str):
        return dest
    return resolve_dest(value + dest[match.end():], variables, depth + 1)


def iter_tasks(items: Any) -> Iterator[dict]:
    """Yield every task dict in *items*, descending into block/rescue/always."""
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        yield item
        for key in NESTED_KEYS:
            nested = item.get(key)
            if isinstance(nested, list):
                yield from iter_tasks(nested)


def iter_document_tasks(document: Any) -> Iterator[dict]:
    """Tasks from a playbook (list of plays) or a task file (list of tasks)."""
    if not isinstance(document, list):
        return
    for item in document:
        if not isinstance(item, dict):
            continue
        if any(key in item for key in PLAY_KEYS):
            for key in TASK_LIST_KEYS:
                yield from iter_tasks(item.get(key))
        else:
            yield from iter_tasks([item])


def module_of(task: dict) -> Optional[str]:
    for key in task:
        if isinstance(key, str) and key in MODULES:
            return key
    return None


def module_args(task: dict, module: str) -> Dict[str, Any]:
    """Merge dict / free-form module arguments with a task-level ``args:`` block."""
    raw = task.get(module)
    args: Dict[str, Any] = {}
    if isinstance(raw, dict):
        args.update(raw)
    elif isinstance(raw, str):
        try:
            tokens = shlex.split(raw)
        except ValueError:
            tokens = raw.split()
        for token in tokens:
            if "=" in token:
                key, value = token.split("=", 1)
                args[key] = value
    extra = task.get("args")
    if isinstance(extra, dict):
        for key, value in extra.items():
            args.setdefault(key, value)
    return args


def backup_state(value: Any) -> str:
    """Classify a ``backup`` value as ``on``, ``off`` or ``missing``."""
    if value is None:
        return "missing"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, float)):
        return "on" if value else "off"
    if isinstance(value, str):
        text = value.strip().lower()
        if text in TRUE_WORDS:
            return "on"
        if text in FALSE_WORDS:
            return "off"
        if "{{" in text:
            # Evaluated at runtime; trust the operator's variable.
            return "on"
        return "off"
    return "off"


def is_restore_from_backup(args: Dict[str, Any]) -> bool:
    """True for rescue tasks that copy a previous backup back into place.

    The roll-out pattern of this repository is: template (``backup: true``) ->
    flush handlers -> verify -> on failure copy ``<register>.backup_file`` back
    with ``remote_src: true``. That restore *is* the rollback; it must not be
    gated on producing yet another backup of the broken file.
    """
    src = args.get("src")
    if not isinstance(src, str):
        return False
    if backup_state(args.get("remote_src")) != "on":
        return False
    return "backup_file" in src or bool(BACKUP_COPY.search(src.strip()))


def is_protected_config(dest: str) -> bool:
    """True when *dest* is a configuration file under a protected prefix."""
    candidate = dest.strip()
    if not candidate.startswith(PROTECTED_PREFIXES):
        return False
    basename = candidate.rstrip("/").rsplit("/", 1)[-1]
    if CONTENT_EXTENSIONS.search(basename) or BACKUP_COPY.search(basename):
        return False
    return True


def task_name(task: dict) -> str:
    name = task.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "<unnamed>"


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path, root).replace(os.sep, "/")


# --- Allowlist ---------------------------------------------------------------
def load_allowlist(path: Optional[Path]) -> List[AllowlistEntry]:
    """Parse ``path:task name`` lines; ``#`` comments and blank lines are ignored."""
    entries: List[AllowlistEntry] = []
    if path is None or not path.is_file():
        return entries
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}:{lineno}: expected '<path>:<task name>', got {raw!r}")
        path_pattern, task_pattern = line.split(":", 1)
        path_pattern = path_pattern.strip().replace(os.sep, "/")
        task_pattern = task_pattern.strip()
        if not path_pattern or not task_pattern:
            raise ValueError(f"{path}:{lineno}: path and task name must both be non-empty")
        entries.append(AllowlistEntry(path_pattern, task_pattern, lineno))
    return entries


# --- Scanning ----------------------------------------------------------------
def check_file(path: Path, root: Path, roles_dir: Optional[Path]) -> Tuple[List[Finding], int]:
    """Return (findings, tasks_checked) for one YAML file."""
    rel = relative_posix(path, root)
    try:
        documents = load_yaml_documents(path)
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        line = 0
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
        return [Finding(rel, line, "<file>", "", KIND_YAML, f"YAML parse error: {exc}".splitlines()[0])], 0

    variables = load_role_vars(role_dir_for(path, roles_dir)) if roles_dir else {}
    findings: List[Finding] = []
    checked = 0
    for document in documents:
        for task in iter_document_tasks(document):
            module = module_of(task)
            if module is None:
                continue
            checked += 1
            args = module_args(task, module)
            dest = args.get("dest", args.get("path"))
            if not isinstance(dest, str):
                continue
            dest = resolve_dest(dest.strip(), variables)
            if not is_protected_config(dest):
                continue
            if is_restore_from_backup(args):
                continue
            state = backup_state(args.get("backup"))
            if state == "on":
                continue
            line = getattr(task, "line", 0)
            name = task_name(task)
            if state == "missing":
                findings.append(
                    Finding(
                        rel,
                        line,
                        name,
                        dest,
                        KIND_MISSING,
                        f"{module} writes {dest} without 'backup: true'",
                    )
                )
            else:
                findings.append(
                    Finding(
                        rel,
                        line,
                        name,
                        dest,
                        KIND_DISABLED,
                        f"{module} writes {dest} with backup disabled; "
                        "set 'backup: true' or add the task to the allowlist with a reason",
                    )
                )
    return findings, checked


def scan(
    root: Path,
    roles_dir: Optional[Path],
    playbooks_dirs: Sequence[Path],
    allowlist: Iterable[AllowlistEntry] = (),
) -> Report:
    """Scan role task files and playbooks; apply the allowlist."""
    report = Report()
    entries = list(allowlist)
    used = set()

    files: List[Path] = []
    if roles_dir is not None:
        files.extend(p for p in find_yaml_files(roles_dir) if is_role_task_file(p, roles_dir))
    for directory in playbooks_dirs:
        files.extend(find_yaml_files(directory))

    seen = set()
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        report.files_scanned += 1
        findings, checked = check_file(path, root, roles_dir)
        report.tasks_checked += checked
        for finding in findings:
            matching = [e for e in entries if finding.kind != KIND_YAML and e.matches(finding)]
            if matching:
                used.update(id(e) for e in matching)
                report.allowlisted.append(finding)
            else:
                report.findings.append(finding)

    report.unused_allowlist = [e for e in entries if id(e) not in used]
    return report


# --- Output ------------------------------------------------------------------
def render_text(report: Report, allowlist_path: Optional[Path]) -> str:
    lines: List[str] = []
    lines.append("Backup coverage report | 备份覆盖率报告")
    lines.append(f"  files scanned : {report.files_scanned}")
    lines.append(f"  tasks checked : {report.tasks_checked} (template/copy)")
    lines.append(f"  findings      : {len(report.findings)}")
    lines.append(f"  allowlisted   : {len(report.allowlisted)}")
    if report.findings:
        lines.append("")
        current = None
        for finding in sorted(report.findings, key=lambda f: (f.path, f.line)):
            if finding.path != current:
                current = finding.path
                lines.append(f"{finding.path}")
            location = f"{finding.line}" if finding.line else "-"
            lines.append(f"  :{location}  [{finding.kind}] {finding.task}")
            lines.append(f"         {finding.message}")
    if report.unused_allowlist:
        lines.append("")
        lines.append("Unused allowlist entries (remove them):")
        for entry in report.unused_allowlist:
            where = f"{allowlist_path}:{entry.source_line}" if allowlist_path else f"line {entry.source_line}"
            lines.append(f"  {where}: {entry.path_pattern}:{entry.task_pattern}")
    lines.append("")
    if report.findings:
        lines.append("FAIL: configuration files above are written without backup: true.")
        lines.append("Fix the task, or document an exception in scripts/backup-coverage-allowlist.txt.")
    else:
        lines.append("OK: every configuration write under /etc keeps a backup.")
    return "\n".join(lines)


def render_github(report: Report, allowlist_path: Optional[Path]) -> str:
    lines: List[str] = []
    for finding in sorted(report.findings, key=lambda f: (f.path, f.line)):
        title = "Missing backup" if finding.kind == KIND_MISSING else finding.kind
        location = f"file={finding.path}"
        if finding.line:
            location += f",line={finding.line}"
        lines.append(f"::error {location},title={title}::{finding.task}: {finding.message}")
    for entry in report.unused_allowlist:
        location = f"file={allowlist_path},line={entry.source_line}" if allowlist_path else ""
        lines.append(
            f"::warning {location},title=Unused allowlist entry::"
            f"{entry.path_pattern}:{entry.task_pattern} matches no task"
        )
    lines.append(
        f"Backup coverage: {len(report.findings)} finding(s), {len(report.allowlisted)} allowlisted, "
        f"{report.tasks_checked} task(s) in {report.files_scanned} file(s)"
    )
    return "\n".join(lines)


# --- CLI ---------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check-backup-coverage.py",
        description="Fail when template/copy tasks write configuration under /etc without backup: true.",
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (paths are reported relative to it)")
    parser.add_argument("--roles-dir", type=Path, default=None, help="roles directory (default: <root>/roles)")
    parser.add_argument(
        "--playbooks-dir",
        type=Path,
        action="append",
        default=None,
        help="playbooks directory, repeatable (default: <root>/playbooks)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help=f"allowlist file (default: {DEFAULT_ALLOWLIST.relative_to(REPO_ROOT)})",
    )
    parser.add_argument("--format", choices=("text", "github"), default="text", help="output format")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root
    roles_dir: Path = args.roles_dir if args.roles_dir is not None else root / "roles"
    playbooks_dirs: List[Path] = args.playbooks_dir if args.playbooks_dir else [root / "playbooks"]
    allowlist_path: Optional[Path] = args.allowlist
    if allowlist_path is None:
        default = root / "scripts" / "backup-coverage-allowlist.txt"
        allowlist_path = default if default.is_file() else None

    if not roles_dir.is_dir() and not any(p.is_dir() for p in playbooks_dirs):
        sys.stderr.write(f"error: neither {roles_dir} nor {playbooks_dirs} exist\n")
        return 2
    try:
        allowlist = load_allowlist(allowlist_path)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    report = scan(root, roles_dir if roles_dir.is_dir() else None, playbooks_dirs, allowlist)
    shown_allowlist = None
    if allowlist_path is not None:
        shown_allowlist = Path(relative_posix(allowlist_path, root))
    if args.format == "github":
        print(render_github(report, shown_allowlist))
    else:
        print(render_text(report, shown_allowlist))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
