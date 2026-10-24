#!/usr/bin/env python3
"""Structure checks for every playbook under playbooks/.

Enforced for each play:
  * name, hosts, become, gather_facts, serial, max_fail_percentage and tags are set
  * hosts is a known inventory group, localhost, or a host pattern/expression
  * no ignore_errors anywhere in the file
File hygiene: strict UTF-8 without BOM, LF endings, trailing newline, no tabs,
no mojibake (UTF-8 text that was decoded as GBK; the characters are listed as
escapes in MOJIBAKE_RE) and no "?" replacement characters in front of
non-ASCII text.
site.yml additionally must expose exactly the play tags agreed in the brief.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOKS_DIR = ROOT / "playbooks"
INVENTORIES_DIR = ROOT / "inventories"

# Task-file directories under playbooks/ that are not playbooks themselves.
TASK_FILE_DIRS = {"security-patch"}

REQUIRED_PLAY_KEYS = (
    "name",
    "hosts",
    "become",
    "gather_facts",
    "serial",
    "max_fail_percentage",
    "tags",
)

# Inventory groups agreed in the programme brief.
BRIEF_GROUPS = {
    "all",
    "web_servers",
    "proxy_servers",
    "dev_servers",
    "observability",
    "v2bx_servers",
    "v2board_servers",
    "postgres_servers",
    "k8s_control_plane",
    "k8s_servers",
    "k8s_test",
}

# One tag per play in site.yml; the preflight play is tagged `always` on top.
SITE_TAGS = {
    "common",
    "node_exporter",
    "promtail",
    "firewall",
    "nginx",
    "prometheus",
    "loki",
    "grafana",
    "postgresql",
    "v2board",
    "v2bx",
    "speedtest",
    "health",
}
CONTROL_TAGS = {"always", "never"}

IMPORT_KEYS = ("ansible.builtin.import_playbook", "import_playbook")

# Common GBK-decoded UTF-8 artefacts, U+FFFD, and a "?" replacement before non-ASCII text.
MOJIBAKE_RE = re.compile(
    "[鈺鏈閮鐨锛銆鍏鎴浠璁鍙�]"
    r"|\?[^\x09\x0a\x0d\x20-\x7e]"
)


class _PermissiveLoader(yaml.SafeLoader):
    """SafeLoader that keeps unknown tags (!vault, !unsafe) as plain values."""


def _unknown_tag(loader, _suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_PermissiveLoader.add_multi_constructor("!", _unknown_tag)


def _load_yaml(path: Path):
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_PermissiveLoader)


def _playbook_files() -> list[Path]:
    files = []
    for path in sorted(PLAYBOOKS_DIR.rglob("*.yml")):
        relative_dirs = set(path.relative_to(PLAYBOOKS_DIR).parent.parts)
        if relative_dirs & TASK_FILE_DIRS:
            continue
        files.append(path)
    return files


def _collect_children(node, groups: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "children" and isinstance(value, dict):
                groups.update(str(child) for child in value)
            _collect_children(value, groups)
    elif isinstance(node, list):
        for item in node:
            _collect_children(item, groups)


def _inventory_groups() -> set[str]:
    """Groups defined in any inventory (hosts.yml children + group_vars entries)."""
    groups: set[str] = set()
    for hosts_file in INVENTORIES_DIR.glob("*/hosts.yml"):
        try:
            data = _load_yaml(hosts_file)
        except (yaml.YAMLError, UnicodeDecodeError):
            continue
        if isinstance(data, dict):
            groups.update(str(key) for key in data)
            _collect_children(data, groups)
    for group_vars in INVENTORIES_DIR.glob("*/group_vars/*"):
        groups.add(group_vars.stem if group_vars.is_file() else group_vars.name)
    return groups


ALLOWED_HOSTS = BRIEF_GROUPS | _inventory_groups() | {"localhost"}
PLAYBOOK_FILES = _playbook_files()
PLAYBOOK_IDS = [str(path.relative_to(ROOT)) for path in PLAYBOOK_FILES]


def _is_import(entry: dict) -> bool:
    return any(key in entry for key in IMPORT_KEYS)


def _import_target(entry: dict) -> str:
    for key in IMPORT_KEYS:
        if key in entry:
            return str(entry[key])
    raise KeyError("not an import_playbook entry")


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _find_keys(node, wanted: str, trail: str = "") -> list[str]:
    hits = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else str(key)
            if key == wanted:
                hits.append(here)
            hits.extend(_find_keys(value, wanted, here))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            hits.extend(_find_keys(item, wanted, f"{trail}[{index}]"))
    return hits


def _host_patterns(hosts) -> list[str]:
    patterns = []
    for pattern in _as_list(hosts):
        pattern = str(pattern).strip()
        if "{{" in pattern:
            # Templated host selection (e.g. "{{ target | default('all') }}").
            continue
        for part in re.split(r"[:,]", pattern):
            part = part.strip().lstrip("!&")
            if not part or part.startswith("~") or "*" in part:
                continue
            patterns.append(part)
    return patterns


def test_playbooks_were_discovered():
    assert PLAYBOOK_FILES, "no playbooks found under playbooks/"
    assert ROOT / "playbooks/provision/site.yml" in PLAYBOOK_FILES


@pytest.mark.parametrize("path", PLAYBOOK_FILES, ids=PLAYBOOK_IDS)
def test_playbook_file_hygiene(path: Path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"{path.name}: UTF-8 BOM present"
    text = raw.decode("utf-8")  # strict: raises on invalid UTF-8
    assert "\r" not in text, f"{path.name}: CRLF line endings"
    assert "\t" not in text, f"{path.name}: tab characters"
    assert text.endswith("\n"), f"{path.name}: missing trailing newline"
    bad_lines = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), start=1)
        if MOJIBAKE_RE.search(line)
    ]
    assert not bad_lines, f"{path.name}: mojibake or replacement characters:\n" + "\n".join(bad_lines)


@pytest.mark.parametrize("path", PLAYBOOK_FILES, ids=PLAYBOOK_IDS)
def test_playbook_play_structure(path: Path):
    data = _load_yaml(path)
    assert isinstance(data, list) and data, f"{path.name}: a playbook must be a non-empty list of plays"

    for index, entry in enumerate(data):
        assert isinstance(entry, dict), f"{path.name}: entry {index} is not a mapping"

        if _is_import(entry):
            target = (path.parent / _import_target(entry)).resolve()
            assert target.is_file(), f"{path.name}: entry {index} imports missing playbook {target}"
            continue

        label = f"{path.name}: play {index} ({entry.get('name', '<unnamed>')})"
        missing = [key for key in REQUIRED_PLAY_KEYS if key not in entry]
        assert not missing, f"{label} is missing {missing}"
        assert isinstance(entry["name"], str) and entry["name"].strip(), f"{label} has an empty name"
        assert entry["become"] in (True, False), f"{label}: become must be a boolean"
        assert entry["gather_facts"] in (True, False), f"{label}: gather_facts must be a boolean"
        assert _as_list(entry["tags"]), f"{label} has no tags"

        unknown = [pattern for pattern in _host_patterns(entry["hosts"]) if pattern not in ALLOWED_HOSTS]
        assert not unknown, f"{label} targets unknown hosts {unknown}; known groups: {sorted(ALLOWED_HOSTS)}"


@pytest.mark.parametrize("path", PLAYBOOK_FILES, ids=PLAYBOOK_IDS)
def test_playbook_has_no_ignore_errors(path: Path):
    hits = _find_keys(_load_yaml(path), "ignore_errors")
    assert not hits, f"{path.name}: ignore_errors is forbidden, found at {hits}"


def test_site_playbook_exposes_the_agreed_tags():
    site = _load_yaml(ROOT / "playbooks/provision/site.yml")
    seen: set[str] = set()
    for entry in site:
        tags = set(_as_list(entry.get("tags")))
        assert tags, f"site.yml entry {entry.get('name')} has no tags"
        service_tags = tags - CONTROL_TAGS
        assert len(service_tags) <= 1, f"site.yml entry {entry.get('name')} has several service tags {tags}"
        seen |= service_tags
    assert seen == SITE_TAGS, f"site.yml tags {sorted(seen)} != agreed {sorted(SITE_TAGS)}"


def test_site_and_quick_setup_import_the_shared_health_check():
    for name in ("site.yml", "quick-setup.yml"):
        entries = _load_yaml(ROOT / "playbooks/provision" / name)
        imports = [_import_target(entry) for entry in entries if _is_import(entry)]
        assert imports == ["../maintenance/health-check.yml"], f"{name} must import the shared health check once"
        assert set(_as_list(entries[-1].get("tags"))) == {"health"}, f"{name}: health import must be tagged health"
