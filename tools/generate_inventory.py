#!/usr/bin/env python3
"""Render the Ansible inventory from ``inventories/production/servers-config.yml``.

``servers-config.yml`` is the single source of truth for the fleet; the
committed ``inventories/production/hosts.yml`` is a generated artifact.

Usage::

    python3 tools/generate_inventory.py local                       # print to stdout
    python3 tools/generate_inventory.py local --output PATH         # write PATH
    python3 tools/generate_inventory.py local --check               # drift gate: exit 1 on diff
    python3 tools/generate_inventory.py github-actions --output "$RUNNER_TEMP/hosts.yml"
    python3 tools/generate_inventory.py local --config other.yml    # alternative config file

Both modes render the same hosts, groups and ``all.vars``; only the header
comment differs. ``github-actions`` is kept as a mode name so existing
workflows keep working. Host addresses are never written to the output: every
host gets ``ansible_host: "{{ lookup('env', '<ENV_VAR>') }}"`` so one file works
locally (``.env``) and in CI (repository secrets exported as environment
variables). Connection defaults read ``ANSIBLE_USER``, ``ANSIBLE_PORT`` and
``SSH_KEY_PATH`` (default ``~/.ssh/id_rsa``).

Configuration schema (v2)::

    schema_version: 2
    global_vars: {ansible_python_interpreter: /usr/bin/python3}
    group_definitions:
      <group>: {description: "...", vars: {...}}
    servers:
      <hostname>:
        env_var: UPPER_SNAKE_CASE            # required
        alias: "..."                         # -> server_alias
        location: "..."                      # -> location
        description: "..."                   # -> description
        server_environment: production       # -> server_environment
        groups: [group, ...]                 # required, must exist in group_definitions
        host_vars: {key: value, ...}         # optional

The legacy schema (no ``schema_version``; ``production_servers`` /
``github_actions_servers`` with ``env_var`` / ``secret_name``) is still
accepted. Legacy ``github_actions_servers`` entries are only rendered in
``github-actions`` mode, as before.

Exit codes: 0 success or up to date, 1 drift detected (``--check``),
2 configuration or usage error.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import yaml

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH: Path = PROJECT_ROOT / "inventories" / "production" / "servers-config.yml"
DEFAULT_INVENTORY_PATH: Path = PROJECT_ROOT / "inventories" / "production" / "hosts.yml"

MODES: Tuple[str, ...] = ("local", "github-actions")
SUPPORTED_SCHEMA_VERSIONS: Tuple[int, ...] = (1, 2)
LATEST_SCHEMA_VERSION: int = 2

HEADER: str = "# GENERATED FILE — edit servers-config.yml and run `make gen-inventory`"
MODE_HEADERS: Dict[str, str] = {
    "local": "# Mode: local — host addresses come from environment variables (.env, see .env.example)",
    "github-actions": (
        "# Mode: github-actions — host addresses come from repository secrets exported as environment variables"
    ),
}
VERIFY_HEADER: str = "# Verify: python3 tools/generate_inventory.py local --check"

# Connection defaults rendered into all.vars in every mode.
CONNECTION_VARS: Dict[str, str] = {
    "ansible_user": "{{ lookup('env', 'ANSIBLE_USER') | default('root', true) }}",
    "ansible_port": "{{ lookup('env', 'ANSIBLE_PORT') | default('22', true) | int }}",
    "ansible_ssh_private_key_file": "{{ lookup('env', 'SSH_KEY_PATH') | default('~/.ssh/id_rsa', true) }}",
}

# (key in servers-config.yml, host variable emitted in the inventory)
METADATA_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("alias", "server_alias"),
    ("location", "location"),
    ("server_environment", "server_environment"),
    ("description", "description"),
)
RESERVED_HOST_VARS = frozenset({"ansible_host"} | {target for _, target in METADATA_FIELDS})

SERVER_KEYS_V2 = frozenset(
    {"env_var", "alias", "location", "description", "server_environment", "groups", "host_vars"}
)
SERVER_KEYS_V1 = SERVER_KEYS_V2 | frozenset({"secret_name", "roles"})
GROUP_KEYS = frozenset({"description", "vars"})
TOP_LEVEL_KEYS_V2 = frozenset({"schema_version", "global_vars", "group_definitions", "servers"})
TOP_LEVEL_KEYS_V1 = frozenset(
    {"schema_version", "global_vars", "group_definitions", "production_servers", "github_actions_servers"}
)
LEGACY_SERVER_SECTIONS = ("production_servers", "github_actions_servers")

HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
GROUP_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class InventoryConfigError(ValueError):
    """Raised when servers-config.yml is missing, unreadable or malformed."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GroupSpec:
    """One entry of ``group_definitions``."""

    name: str
    description: str = ""
    vars: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ServerSpec:
    """One entry of ``servers`` (or a legacy server section)."""

    name: str
    env_var: str
    groups: List[str]
    alias: Optional[str] = None
    location: Optional[str] = None
    server_environment: Optional[str] = None
    description: Optional[str] = None
    host_vars: Dict[str, Any] = field(default_factory=dict)
    ci_only: bool = False  # legacy github_actions_servers entry


@dataclass(frozen=True)
class InventorySpec:
    """A fully validated configuration."""

    schema_version: int
    global_vars: Dict[str, Any]
    groups: List[GroupSpec]
    servers: List[ServerSpec]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys.

    PyYAML silently keeps the last duplicate, which would hide a host that is
    defined twice. Duplicate keys are a configuration error here.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> Dict[Any, Any]:
        seen: Set[Any] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise InventoryConfigError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _resolve_config_path(config_file: "str | Path") -> Path:
    path = Path(config_file).expanduser()
    if path.exists():
        return path
    candidate = PROJECT_ROOT / path
    if not path.is_absolute() and candidate.exists():
        return candidate
    raise InventoryConfigError(f"configuration file not found: {config_file}")


def load_config(config_file: "str | Path" = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Read and parse the configuration file (duplicate keys are rejected)."""
    path = _resolve_config_path(config_file)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InventoryConfigError(f"{path}: cannot read file: {exc}") from exc
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader subclass
    except InventoryConfigError as exc:
        raise InventoryConfigError(f"{path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise InventoryConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, Mapping):
        raise InventoryConfigError(f"{path}: top level must be a mapping (YAML dictionary)")
    return dict(data)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise InventoryConfigError(f"{label} must be a mapping, got {type(value).__name__}")
    return value


def _schema_version(config: Mapping[str, Any]) -> int:
    raw = config.get("schema_version")
    if raw is None:
        # `servers` only exists in v2; anything else is the legacy layout.
        return LATEST_SCHEMA_VERSION if "servers" in config else 1
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InventoryConfigError(f"`schema_version` must be an integer, got {raw!r}")
    if raw not in SUPPORTED_SCHEMA_VERSIONS:
        raise InventoryConfigError(
            f"unsupported schema_version {raw}; supported versions: {', '.join(map(str, SUPPORTED_SCHEMA_VERSIONS))}"
        )
    return raw


def _parse_groups(raw: Any) -> List[GroupSpec]:
    entries = _as_mapping(raw, "`group_definitions`")
    groups: List[GroupSpec] = []
    for name, definition in entries.items():
        if not isinstance(name, str) or not GROUP_NAME_RE.match(name):
            raise InventoryConfigError(
                f"invalid group name {name!r} (letters, digits and '_' only; must not start with a digit)"
            )
        body = _as_mapping(definition, f"group {name!r}")
        unknown = sorted(set(body) - GROUP_KEYS)
        if unknown:
            raise InventoryConfigError(f"group {name!r}: unknown key(s) {unknown}; allowed: {sorted(GROUP_KEYS)}")
        description = body.get("description") or ""
        if not isinstance(description, str):
            raise InventoryConfigError(f"group {name!r}: `description` must be a string")
        group_vars = _as_mapping(body.get("vars"), f"`vars` of group {name!r}")
        groups.append(GroupSpec(name=name, description=description, vars=dict(group_vars)))
    return groups


def _parse_server(
    section: str,
    name: Any,
    definition: Any,
    allowed_keys: frozenset,
    known_groups: Set[str],
    ci_only: bool,
) -> ServerSpec:
    if not isinstance(name, str) or not HOSTNAME_RE.match(name):
        raise InventoryConfigError(
            f"`{section}`: invalid hostname {name!r} (letters, digits, '.', '_' and '-' only)"
        )
    body = _as_mapping(definition, f"server {name!r}")
    if not body:
        raise InventoryConfigError(f"server {name!r}: definition is empty (needs at least `env_var` and `groups`)")
    unknown = sorted(set(body) - allowed_keys)
    if unknown:
        raise InventoryConfigError(f"server {name!r}: unknown key(s) {unknown}; allowed: {sorted(allowed_keys)}")

    env_var = body.get("env_var", body.get("secret_name"))
    if env_var is None or env_var == "":
        raise InventoryConfigError(
            f"server {name!r}: missing `env_var` (name of the environment variable holding its SSH address)"
        )
    if not isinstance(env_var, str) or not ENV_VAR_RE.match(env_var):
        raise InventoryConfigError(f"server {name!r}: env_var {env_var!r} must be UPPER_SNAKE_CASE (e.g. PL_1_V4_SSH)")

    groups = body.get("groups")
    if not isinstance(groups, list) or not groups or not all(isinstance(group, str) for group in groups):
        raise InventoryConfigError(f"server {name!r}: `groups` must be a non-empty list of group names")
    repeated = sorted({group for group in groups if groups.count(group) > 1})
    if repeated:
        raise InventoryConfigError(f"server {name!r}: group(s) {repeated} listed more than once")
    missing = [group for group in groups if group not in known_groups]
    if missing:
        raise InventoryConfigError(f"server {name!r}: unknown group(s) {missing}; define them under `group_definitions`")

    metadata: Dict[str, Optional[str]] = {}
    for source, _target in METADATA_FIELDS:
        value = body.get(source)
        if value is not None and not isinstance(value, str):
            raise InventoryConfigError(f"server {name!r}: `{source}` must be a string")
        metadata[source] = value

    host_vars = _as_mapping(body.get("host_vars"), f"`host_vars` of server {name!r}")
    bad_keys = sorted(str(key) for key in host_vars if not isinstance(key, str))
    if bad_keys:
        raise InventoryConfigError(f"server {name!r}: host_vars keys must be strings, got {bad_keys}")
    clash = sorted(RESERVED_HOST_VARS & set(host_vars))
    if clash:
        raise InventoryConfigError(
            f"server {name!r}: host_vars may not override generated variable(s) {clash}; "
            "use alias/location/description/server_environment instead"
        )

    return ServerSpec(
        name=name,
        env_var=env_var,
        groups=list(groups),
        alias=metadata["alias"],
        location=metadata["location"],
        server_environment=metadata["server_environment"],
        description=metadata["description"],
        host_vars=dict(host_vars),
        ci_only=ci_only,
    )


def _parse_servers(config: Mapping[str, Any], version: int, known_groups: Set[str]) -> List[ServerSpec]:
    if version >= 2:
        if "servers" not in config:
            raise InventoryConfigError("missing `servers` section (schema v2)")
        sections = [("servers", config.get("servers"), False)]
        allowed_keys = SERVER_KEYS_V2
    else:
        if not any(section in config for section in LEGACY_SERVER_SECTIONS):
            raise InventoryConfigError(
                "missing `servers` section (schema v2) or `production_servers` section (legacy schema)"
            )
        sections = [
            ("production_servers", config.get("production_servers"), False),
            ("github_actions_servers", config.get("github_actions_servers"), True),
        ]
        allowed_keys = SERVER_KEYS_V1

    servers: List[ServerSpec] = []
    defined_in: Dict[str, str] = {}
    env_var_owner: Dict[str, str] = {}
    for section, raw, ci_only in sections:
        for name, definition in _as_mapping(raw, f"`{section}`").items():
            server = _parse_server(section, name, definition, allowed_keys, known_groups, ci_only)
            if server.name in defined_in:
                raise InventoryConfigError(
                    f"duplicate host {server.name!r}: defined in `{defined_in[server.name]}` and `{section}`"
                )
            defined_in[server.name] = section
            if not ci_only:
                owner = env_var_owner.get(server.env_var)
                if owner is not None:
                    raise InventoryConfigError(
                        f"env_var {server.env_var!r} is used by both {owner!r} and {server.name!r}; "
                        "every host needs its own address variable"
                    )
                env_var_owner[server.env_var] = server.name
            servers.append(server)
    return servers


def parse_config(config: Mapping[str, Any]) -> InventorySpec:
    """Validate a raw configuration mapping and return a typed specification."""
    if not isinstance(config, Mapping):
        raise InventoryConfigError("configuration must be a mapping (YAML dictionary)")
    version = _schema_version(config)
    if version >= 2:
        legacy = sorted(section for section in LEGACY_SERVER_SECTIONS if section in config)
        if legacy:
            raise InventoryConfigError(f"schema v2 replaces {legacy} with a single `servers` section")
    allowed_top = TOP_LEVEL_KEYS_V2 if version >= 2 else TOP_LEVEL_KEYS_V1
    unknown = sorted(set(config) - allowed_top)
    if unknown:
        raise InventoryConfigError(f"unknown top-level key(s) {unknown}; schema v{version} allows {sorted(allowed_top)}")

    global_vars = _as_mapping(config.get("global_vars"), "`global_vars`")
    groups = _parse_groups(config.get("group_definitions"))
    servers = _parse_servers(config, version, {group.name for group in groups})
    return InventorySpec(schema_version=version, global_vars=dict(global_vars), groups=groups, servers=servers)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _host_entry(server: ServerSpec) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"ansible_host": f"{{{{ lookup('env', '{server.env_var}') }}}}"}
    for source, target in METADATA_FIELDS:
        value = getattr(server, source)
        if value is not None:
            entry[target] = value
    entry.update(server.host_vars)
    return entry


def build_inventory(spec: InventorySpec, include_ci_only: bool = False) -> Dict[str, Any]:
    """Build the inventory structure (``{"all": {...}}``) from a validated spec.

    Hosts are defined once under ``all.hosts`` (address + metadata + host_vars);
    groups reference them by name. Key order follows the configuration file,
    so the output is deterministic.
    """
    hosts: Dict[str, Dict[str, Any]] = {}
    children: Dict[str, Dict[str, Any]] = {group.name: {"hosts": {}} for group in spec.groups}

    for server in spec.servers:
        if server.ci_only and not include_ci_only:
            continue
        hosts[server.name] = _host_entry(server)
        for group_name in server.groups:
            children[group_name]["hosts"][server.name] = {}

    for group in spec.groups:
        if group.vars:
            children[group.name]["vars"] = dict(group.vars)

    all_vars: Dict[str, Any] = dict(CONNECTION_VARS)
    all_vars.update(spec.global_vars)
    return {"all": {"hosts": hosts, "children": children, "vars": all_vars}}


def generate_local_inventory(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Inventory structure for ``local`` mode."""
    return build_inventory(parse_config(config), include_ci_only=False)


def generate_github_actions_inventory(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Inventory structure for ``github-actions`` mode (identical for schema v2)."""
    return build_inventory(parse_config(config), include_ci_only=True)


class _InventoryDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:  # noqa: D401 - PyYAML hook
        return True


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    style = '"' if ("{{" in data and "}}" in data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_InventoryDumper.add_representer(str, _represent_str)


def generate_inventory_yaml(inventory: Mapping[str, Any]) -> str:
    """Serialise an inventory structure to YAML (stable order, Jinja double-quoted)."""
    return yaml.dump(
        dict(inventory),
        Dumper=_InventoryDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        indent=2,
        width=1000,
    )


def render_inventory(mode: str, config: Mapping[str, Any]) -> str:
    """Return the complete inventory file (header + YAML) for ``mode``."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode: {mode!r} (expected one of: {', '.join(MODES)})")
    spec = parse_config(config)
    inventory = build_inventory(spec, include_ci_only=(mode == "github-actions"))
    header = "\n".join(
        [
            HEADER,
            f"# Source: servers-config.yml (schema v{spec.schema_version})",
            MODE_HEADERS[mode],
            VERIFY_HEADER,
            "---",
        ]
    )
    return header + "\n" + generate_inventory_yaml(inventory)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def write_output(output_path: "str | Path", content: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def check_inventory(rendered: str, inventory_path: Path = DEFAULT_INVENTORY_PATH) -> int:
    """Compare ``rendered`` with the committed inventory; print a diff and return 1 on drift."""
    shown = _display_path(inventory_path)
    if not inventory_path.exists():
        print(f"error: {shown} does not exist; run `make gen-inventory`", file=sys.stderr)
        return 1
    current = inventory_path.read_text(encoding="utf-8")
    if current == rendered:
        print(f"OK: {shown} is up to date with servers-config.yml")
        return 0
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        rendered.splitlines(keepends=True),
        fromfile=f"{shown} (committed)",
        tofile=f"{shown} (rendered from servers-config.yml)",
    )
    sys.stdout.writelines(diff)
    sys.stdout.flush()
    print(f"error: {shown} is out of date; run `make gen-inventory` and commit the result", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_inventory.py",
        description="Generate the Ansible inventory from servers-config.yml.",
        epilog="Exit codes: 0 ok, 1 drift detected (--check), 2 configuration or usage error.",
    )
    parser.add_argument("mode", choices=MODES, help="Rendering mode; both produce the same hosts and groups.")
    parser.add_argument(
        "--config",
        "-c",
        default=str(DEFAULT_CONFIG_PATH),
        metavar="PATH",
        help="Configuration file (default: inventories/production/servers-config.yml).",
    )
    parser.add_argument("--output", "-o", metavar="PATH", help="Write the inventory to PATH instead of stdout.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 with a unified diff when the committed inventory "
        "(inventories/production/hosts.yml, or --output PATH) differs from the rendered output.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except InventoryConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        rendered = render_inventory(args.mode, config)
    except InventoryConfigError as exc:
        print(f"error: {args.config}: {exc}", file=sys.stderr)
        return 2

    if args.check:
        target = Path(args.output) if args.output else DEFAULT_INVENTORY_PATH
        return check_inventory(rendered, target)

    if args.output:
        write_output(args.output, rendered)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
