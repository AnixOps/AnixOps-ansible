"""Ansible role and playbook convention gate.

Checks every role under roles/ (layout, galaxy meta, variable prefixes,
handler names, systemd unit templates) and every task in roles/, playbooks/
and tests/integration/ (names, FQCN modules, no ignore_errors, changed_when on
commands, pipefail on shell pipes, retries on network modules, backups for
/etc configs, no_log around secrets, quoted octal modes, true/false booleans).

Tests are parametrized per file or per role, aggregate every violation in that
unit into one message, and point at ``file:line`` wherever possible.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    ROLES_DIR,
    action_keys,
    as_list,
    command_text,
    find_lines,
    format_problems,
    handler_files,
    ids_for,
    is_block,
    iter_file_tasks,
    load_yaml_document,
    module_args,
    playbook_files,
    read_text,
    rel,
    role_dirs,
    role_files,
    role_name,
    role_task_files,
    safe_load_yaml,
    short_action,
    strip_jinja,
    strip_yaml_comment,
    task_action,
    task_files,
    tracked_under,
    where,
)

pytestmark = pytest.mark.structure

ROLES = role_dirs()
TASK_FILES = task_files()            # role tasks/handlers + playbooks + included task files
ROLE_TASK_FILES = role_task_files()  # roles/*/tasks/**, roles/*/handlers/**
HANDLER_FILES = handler_files()
PLAYBOOKS = playbook_files()
CONVENTION_YAML = tuple(sorted(set(
    tracked_under("roles") + tracked_under("playbooks") + tracked_under("inventories") + tracked_under("tests", "integration")
)))
UNIT_TEMPLATES = tuple(sorted(
    p for p in tracked_under("roles", suffixes=(".j2",))
    if p.name.endswith(".service.j2") and "templates" in p.relative_to(ROLES_DIR).parts
))

FQCN_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+$")
GALAXY_TAG_RE = re.compile(r"^[a-z0-9]+$")
HANDLER_NAME_RE = re.compile(r"^(?:Restart|Reload|Start|Stop|Enable|Daemon) \S")
PIPE_RE = re.compile(r"(?<!\|)\|(?!\|)")
PIPEFAIL_RE = re.compile(r"\bpipefail\b")
COMMAND_SHELL_SYNTAX_RE = re.compile(r"\s(?:\||\|\||&&|;|>|>>|2>|<)\s|\s2>\S|\$\(|`")
ERROR_HIDING_RE = re.compile(r"\|\|\s*(?:true\b|:(?!\S)|exit\s+0\b)|;\s*true\s*$", re.M)
# An identifier that IS a secret ends with one of these suffixes (optionally _hash);
# *_token_file / *_password_authentication style names are paths or switches, not secrets.
SECRET_NAME_RE = re.compile(
    r"\b[A-Za-z0-9_]*(?:password|passwd|token|secret|api_key|private_key|access_key)(?:_hash)?\b", re.I
)
SECRET_REF_RE = re.compile(r"\{\{[^}]*?" + SECRET_NAME_RE.pattern + r"[^}]*?\}\}", re.I)
BASH_EXECUTABLES = {"/bin/bash", "/usr/bin/bash", "bash"}

COMMAND_MODULES = {"command", "shell", "raw"}
NETWORK_MODULES = {
    "get_url", "uri", "apt", "package", "apt_repository", "apt_key", "deb822_repository",
    "pip", "dnf", "yum", "git", "docker_image",
}
CONFIG_WRITERS = {"template", "copy"}
CONTENT_SUFFIXES = (".html", ".htm", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
                    ".ico", ".woff", ".woff2", ".ttf", ".eot")
UNIT_DEST_RE = re.compile(r"^/etc/systemd/system/[^/]+\.(?:service|timer|socket|mount|path)$")

# Agreed handler contract per role (brief section 3). A role may add more handlers.
AGREED_HANDLERS = {
    "common": {"Restart sshd", "Reload sshd", "Restart chrony", "Restart fail2ban"},
    "nginx": {"Reload nginx", "Restart nginx"},
    "node_exporter": {"Reload systemd", "Restart node_exporter"},
    "promtail": {"Reload systemd", "Restart promtail"},
    "prometheus": {"Reload systemd", "Restart prometheus", "Reload prometheus"},
    "loki": {"Reload systemd", "Restart loki"},
    "grafana": {"Restart grafana"},
    "acme_ssl": {"Reload nginx"},
}

# Global knobs operators set in group_vars that roles may (re)declare in defaults
# without the role prefix.  Exact names plus prefixes.
GLOBAL_DEFAULT_KEYS = {
    "timezone", "locale", "ntp_servers", "common_packages", "admin_users", "security",
    "sysctl_config", "ssh_port", "ssh_allow_root", "ssh_password_authentication",
    "ssh_pubkey_authentication", "firewall_enabled", "firewall_public_ports",
    "firewall_restricted_ports", "monitoring_whitelist", "proxy_additional_ports",
    "nginx", "prometheus", "loki", "grafana", "acme_email", "acme_dns_provider",
    "acme_domains", "cloudflare_api_token", "cloudflare_zone_id", "loki_server_url",
    "speedtest_exporter_host", "grafana_admin_password", "observability_ssl_enabled",
    "state_dir", "state_file", "history_file", "backup_registry", "k8s_provider",
    "k8s_role", "cluster_name",
}
GLOBAL_DEFAULT_PREFIXES = ("hooks_", "notification_", "cleanup_", "kubeconfig_", "k3s_", "kind_")

TRUTHY_WORDS = r"(?:yes|no|Yes|No|YES|NO|on|off|On|Off|ON|OFF|True|False|TRUE|FALSE)"
TRUTHY_VALUE_RE = re.compile(
    r"^\s*(?:-\s+)?(?:\"[^\"]*\"|'[^']*'|[^\s#'\"\-][^:]*?)\s*:\s+" + TRUTHY_WORDS + r"\s*$"
)
TRUTHY_ITEM_RE = re.compile(r"^\s*-\s+" + TRUTHY_WORDS + r"\s*$")
MODE_LINE_RE = re.compile(r"^\s*(?:-\s+)?(?:mode|directory_mode|dir_mode|file_mode):\s*(\S.*?)\s*$")
MODE_OK_RE = re.compile(r"""^(?:["']0[0-7]{3,4}["']|preserve|["']?\{\{.*\}\}["']?|["']?[ugoa]*[-+=][rwxXst]*(?:,[ugoa]*[-+=][rwxXst]*)*["']?)$""")
MODE_BAD_UNQUOTED_RE = re.compile(r"^(?:0o?)?[0-7]{3,4}$")
MODE_BAD_QUOTED_RE = re.compile(r"""^["'][1-7][0-7]{2}["']$""")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _role_vars(role: str) -> dict:
    """Merged defaults/vars of a role (used to resolve one level of Jinja in dest paths)."""
    merged: dict = {}
    for sub in ("defaults", "vars"):
        for path in role_files(ROLES_DIR / role, sub):
            doc = load_yaml_document(path) if safe_load_yaml(path) is not None else None
            if isinstance(doc, dict):
                merged.update(doc)
    return merged


_ROLE_VARS_CACHE: dict[str, dict] = {}


def _resolve_path(value: Any, role: str | None) -> str | None:
    """Resolve ``{{ role_var }}/rest`` against the role's defaults (one level)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value.startswith("{{"):
        return value
    match = re.match(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\|[^}]*)?\}\}(.*)$", value)
    if not match or role is None:
        return None
    if role not in _ROLE_VARS_CACHE:
        _ROLE_VARS_CACHE[role] = _role_vars(role)
    head = _ROLE_VARS_CACHE[role].get(match.group(1))
    if isinstance(head, str) and not head.strip().startswith("{{"):
        return head.strip() + match.group(2)
    return None


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, val in value.items():
            yield from _iter_strings(key)
            yield from _iter_strings(val)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def _notified(task: dict) -> set[str]:
    return {str(item) for item in as_list(task.get("notify"))}


def _assert_clean(problems: list[str], title: str) -> None:
    assert not problems, format_problems(title, problems)


# ---------------------------------------------------------------------------
# Role layout and metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_dir", ROLES, ids=[p.name for p in ROLES])
def test_role_has_required_files(role_dir: Path) -> None:
    required = ("tasks/main.yml", "defaults/main.yml", "meta/main.yml", "README.md")
    missing = [name for name in required if not (role_dir / name).is_file()]
    assert not missing, (
        f"{rel(role_dir)}: missing {', '.join(missing)} "
        "(every role needs tasks/main.yml, defaults/main.yml, meta/main.yml and a README.md)"
    )


@pytest.mark.parametrize("role_dir", ROLES, ids=[p.name for p in ROLES])
def test_role_meta_galaxy_info(role_dir: Path) -> None:
    meta_path = role_dir / "meta" / "main.yml"
    if not meta_path.is_file():
        pytest.fail(f"{rel(meta_path)}: missing")
    if safe_load_yaml(meta_path) is None:
        pytest.fail(f"{rel(meta_path)}: does not parse (see test_repo_hygiene)")
    meta = load_yaml_document(meta_path)
    problems: list[str] = []
    loc = rel(meta_path)
    if not isinstance(meta, dict):
        pytest.fail(f"{loc}: must be a mapping with galaxy_info and dependencies")
    info = meta.get("galaxy_info")
    if not isinstance(info, dict):
        problems.append(f"{loc}: galaxy_info mapping is missing")
        info = {}
    for key in ("author", "description", "license", "min_ansible_version"):
        if not isinstance(info.get(key), (str, int, float)) or str(info.get(key)).strip() == "":
            problems.append(f"{loc}: galaxy_info.{key} is missing or empty")
    if "license" in info and info["license"] != "MIT":
        problems.append(f"{loc}: galaxy_info.license must be MIT (repo convention), got {info['license']!r}")
    if "min_ansible_version" in info and not isinstance(info["min_ansible_version"], str):
        problems.append(
            f"{loc}: galaxy_info.min_ansible_version must be a quoted string (\"2.15\"), "
            f"got {info['min_ansible_version']!r}"
        )
    platforms = info.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        problems.append(f"{loc}: galaxy_info.platforms must be a non-empty list")
    else:
        names = set()
        for entry in platforms:
            if not isinstance(entry, dict) or not entry.get("name") or not isinstance(entry.get("versions"), list):
                problems.append(f"{loc}: every platform needs name + versions list, got {entry!r}")
            else:
                names.add(str(entry["name"]))
        for required in ("Debian", "Ubuntu"):
            if required not in names:
                problems.append(f"{loc}: galaxy_info.platforms must list {required}")
    tags = info.get("galaxy_tags")
    if not isinstance(tags, list) or not tags:
        problems.append(f"{loc}: galaxy_info.galaxy_tags must be a non-empty list")
    else:
        for tag in tags:
            if not isinstance(tag, str) or not GALAXY_TAG_RE.match(tag):
                problems.append(f"{loc}: galaxy tag {tag!r} must match [a-z0-9]+")
    if "dependencies" not in meta:
        problems.append(f"{loc}: top-level 'dependencies' key is required (use [] when none)")
    elif not isinstance(meta["dependencies"], list):
        problems.append(f"{loc}: dependencies must be a list")
    _assert_clean(problems, f"{loc}: galaxy metadata")


@pytest.mark.parametrize("role_dir", ROLES, ids=[p.name for p in ROLES])
def test_role_default_and_vars_keys_are_prefixed(role_dir: Path) -> None:
    role = role_dir.name
    prefix = f"{role}_"
    problems: list[str] = []
    for path in role_files(role_dir, "defaults", "vars"):
        if safe_load_yaml(path) is None:
            continue  # reported by test_repo_hygiene
        doc = load_yaml_document(path)
        if doc is None:
            continue
        if not isinstance(doc, dict):
            problems.append(f"{rel(path)}: must be a mapping of variables")
            continue
        for key in doc:
            name = str(key)
            if name.startswith(prefix) or name in GLOBAL_DEFAULT_KEYS or name.startswith(GLOBAL_DEFAULT_PREFIXES):
                continue
            line = next((n for n, _ in find_lines(path, rf"^{re.escape(name)}\s*:")), None)
            pointer = f"{rel(path)}:{line}" if line else rel(path)
            problems.append(
                f"{pointer}: variable '{name}' must be prefixed '{prefix}' "
                f"(e.g. {prefix}{name}: \"{{{{ {name} | default(...) }}}}\")"
            )
    _assert_clean(problems, f"{rel(role_dir)}: role variables must carry the role prefix")


@pytest.mark.parametrize("path", HANDLER_FILES, ids=ids_for(HANDLER_FILES))
def test_handler_names_follow_convention(path: Path) -> None:
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        name = task.get("name")
        if not isinstance(name, str) or not HANDLER_NAME_RE.match(name):
            problems.append(
                f"{where(path, task, location)}: handler name {name!r} must look like "
                "'Restart <service>' / 'Reload <service>' / 'Reload systemd'"
            )
    _assert_clean(problems, f"{rel(path)}: handler naming")


@pytest.mark.parametrize("role", sorted(AGREED_HANDLERS), ids=sorted(AGREED_HANDLERS))
def test_agreed_handler_names_exist(role: str) -> None:
    role_dir = ROLES_DIR / role
    if role_dir not in ROLES:
        pytest.skip(f"role {role} not present")
    found: set[str] = set()
    for path in role_files(role_dir, "handlers"):
        for task, _, _ in iter_file_tasks(path):
            if isinstance(task.get("name"), str):
                found.add(task["name"])
            found.update(str(item) for item in as_list(task.get("listen")))
    missing = sorted(AGREED_HANDLERS[role] - found)
    assert not missing, (
        f"roles/{role}/handlers: agreed handler names missing: {missing} (found: {sorted(found)}); "
        "these exact names are the cross-role interface other roles/playbooks notify"
    )


# ---------------------------------------------------------------------------
# Tasks: names, FQCN, error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", TASK_FILES, ids=ids_for(TASK_FILES))
def test_tasks_are_named(path: Path) -> None:
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        pointer = where(path, task, location)
        name = task.get("name")
        if name is None:
            kind = "block" if is_block(task) else (task_action(task) or "task")
            problems.append(f"{pointer}: unnamed {kind}; every task and block needs a 'name'")
        elif not isinstance(name, str) or not name.strip():
            problems.append(f"{pointer}: name must be a non-empty string, got {name!r}")
        elif name != name.strip():
            problems.append(f"{pointer}: name has leading/trailing whitespace: {name!r}")
        elif name.startswith("{{"):
            problems.append(f"{pointer}: name must not start with Jinja: {name!r}")
        elif not re.match(r"[A-Z]", name):
            problems.append(
                f"{pointer}: name must start with an uppercase ASCII letter "
                f"(English first, optional ' | Chinese' suffix): {name!r}"
            )
    _assert_clean(problems, f"{rel(path)}: task naming")


@pytest.mark.parametrize("path", TASK_FILES, ids=ids_for(TASK_FILES))
def test_task_actions_are_fqcn(path: Path) -> None:
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        pointer = where(path, task, location)
        if "local_action" in task:
            problems.append(f"{pointer}: local_action is forbidden; use the FQCN module with delegate_to: localhost")
        if is_block(task):
            extra = action_keys(task)
            if extra:
                problems.append(f"{pointer}: block container carries non-keyword keys {extra}")
            continue
        keys = action_keys(task)
        if len(keys) > 1:
            problems.append(f"{pointer}: several candidate module keys {keys}; mis-spelled task keyword?")
            continue
        action = keys[0] if keys else task_action(task)
        if action is None:
            problems.append(f"{pointer}: no module key found on task {task.get('name')!r}")
            continue
        if not FQCN_RE.match(action):
            hint = f"ansible.builtin.{action}" if "." not in action else action
            problems.append(f"{pointer}: module '{action}' is not fully qualified (e.g. {hint})")
        elif action.startswith("ansible.legacy."):
            problems.append(f"{pointer}: use ansible.builtin.* instead of {action}")
    _assert_clean(problems, f"{rel(path)}: FQCN modules")


IGNORE_ERRORS_RE = re.compile(r"^\s*(?:-\s+)?ignore_errors\s*:")


@pytest.mark.parametrize("path", CONVENTION_YAML, ids=ids_for(CONVENTION_YAML))
def test_no_ignore_errors(path: Path) -> None:
    hits = find_lines(path, IGNORE_ERRORS_RE)
    _assert_clean(
        [
            f"{rel(path)}:{number}: {line.strip()!r} -> use failed_when: false (read-only probes), "
            "block/rescue/always, or register + conditions"
            for number, line in hits
        ],
        f"{rel(path)}: ignore_errors is banned",
    )


@pytest.mark.parametrize("path", TASK_FILES, ids=ids_for(TASK_FILES))
def test_command_tasks_declare_changed_when(path: Path) -> None:
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        action = task_action(task)
        if short_action(action) not in COMMAND_MODULES:
            continue
        args = module_args(task, action)
        if "changed_when" in task or "creates" in args or "removes" in args:
            continue
        if "async" in task and task.get("poll") == 0:
            continue
        problems.append(
            f"{where(path, task, location)}: {action} task {task.get('name')!r} needs changed_when "
            "(false for read-only commands) or creates:/removes:"
        )
    _assert_clean(problems, f"{rel(path)}: command/shell idempotency")


@pytest.mark.parametrize("path", TASK_FILES, ids=ids_for(TASK_FILES))
def test_shell_pipes_use_pipefail_and_bash(path: Path) -> None:
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        action = task_action(task)
        short = short_action(action)
        if short not in COMMAND_MODULES:
            continue
        pointer = where(path, task, location)
        raw_cmd = command_text(task, action)
        cmd = strip_jinja(raw_cmd)
        args = module_args(task, action)
        if short == "shell" and PIPE_RE.search(cmd):
            if not PIPEFAIL_RE.search(cmd):
                problems.append(f"{pointer}: shell pipeline without 'set -o pipefail' in {task.get('name')!r}")
            if str(args.get("executable", "")).strip() not in BASH_EXECUTABLES:
                problems.append(
                    f"{pointer}: pipelines with pipefail need args: executable: /bin/bash "
                    f"(dash on Debian/Ubuntu lacks pipefail) in {task.get('name')!r}"
                )
        if short == "command" and COMMAND_SHELL_SYNTAX_RE.search(cmd):
            problems.append(
                f"{pointer}: ansible.builtin.command does not run a shell, so pipes/redirects/&&/; "
                f"are passed literally in {task.get('name')!r}; use a module or ansible.builtin.shell with pipefail"
            )
        if ERROR_HIDING_RE.search(cmd):
            problems.append(
                f"{pointer}: '|| true' / '|| exit 0' hides failures in {task.get('name')!r}; "
                "use failed_when: false or handle the exit code explicitly"
            )
    _assert_clean(problems, f"{rel(path)}: shell safety")


@pytest.mark.parametrize("path", TASK_FILES, ids=ids_for(TASK_FILES))
def test_network_tasks_retry(path: Path) -> None:
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        action = task_action(task)
        short = short_action(action)
        if short not in NETWORK_MODULES:
            continue
        args = module_args(task, action)
        if str(args.get("state", "")) in ("absent", "removed"):
            continue  # removal is local
        if short == "deb822_repository" and not str(args.get("signed_by", "")).startswith(("http://", "https://")):
            continue  # only fetches when the signing key is a URL
        if short == "apt_key" and not (args.get("url") or args.get("keyserver")):
            continue  # key material supplied inline
        if short == "apt" and not any(k in args for k in ("name", "pkg", "package", "deb")):
            if args.get("update_cache") and "update_cache_retries" in args:
                continue  # cache refresh with module-native retries
        missing = [key for key in ("retries", "delay", "until") if key not in task]
        if missing:
            problems.append(
                f"{where(path, task, location)}: {action} task {task.get('name')!r} lacks {missing}; "
                "network operations need retries: 3-5, delay: 5-10, until: <result> is succeeded"
            )
    _assert_clean(problems, f"{rel(path)}: network retry policy")


@pytest.mark.parametrize("path", TASK_FILES, ids=ids_for(TASK_FILES))
def test_secret_bearing_tasks_use_no_log(path: Path) -> None:
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        action = task_action(task)
        if action is None:
            continue
        args = module_args(task, action)
        short = short_action(action)
        exposed = any(SECRET_REF_RE.search(text) for text in _iter_strings(args))
        if short == "debug" and isinstance(args.get("var"), str) and SECRET_NAME_RE.search(args["var"]):
            exposed = True
        if short == "set_fact" and any(SECRET_NAME_RE.search(str(key)) for key in args if key != "cacheable"):
            exposed = True
        if not exposed:
            continue
        no_log = task.get("no_log")
        if no_log is None or no_log is False:
            problems.append(
                f"{where(path, task, location)}: {action} task {task.get('name')!r} references a "
                "password/token/secret variable but has no 'no_log: true'"
            )
    _assert_clean(problems, f"{rel(path)}: secrets must not reach the log")


# ---------------------------------------------------------------------------
# Role tasks: /etc configs, registered variables, systemd units
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ROLE_TASK_FILES, ids=ids_for(ROLE_TASK_FILES))
def test_etc_config_writes_are_backed_up_with_explicit_permissions(path: Path) -> None:
    role = role_name(path)
    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        action = task_action(task)
        if short_action(action) not in CONFIG_WRITERS:
            continue
        args = module_args(task, action)
        dest = _resolve_path(args.get("dest"), role)
        if not dest or not dest.startswith("/etc/") or dest.lower().endswith(CONTENT_SUFFIXES):
            continue
        if dest.endswith("/"):
            continue  # directory sync (e.g. console assets), not a config file
        restoring = bool(args.get("remote_src")) and (".rescue[" in location or "backup" in str(args.get("src", "")).lower())
        if restoring:
            continue  # rescue path putting a .backup_file back: not a config roll-out
        pointer = where(path, task, location)
        missing = [key for key in ("backup", "owner", "group", "mode") if key not in args]
        if missing:
            problems.append(
                f"{pointer}: {action} -> {dest}: missing {missing} "
                "(configs under /etc need backup: true plus explicit owner/group/mode)"
            )
        if "backup" in args and args["backup"] not in (True, False):
            problems.append(f"{pointer}: backup must be a real boolean, got {args['backup']!r}")
    _assert_clean(problems, f"{rel(path)}: /etc config safety")


@pytest.mark.parametrize("path", ROLE_TASK_FILES, ids=ids_for(ROLE_TASK_FILES))
def test_registered_and_set_fact_variables_are_prefixed(path: Path) -> None:
    role = role_name(path) or ""
    prefix = f"{role}_"

    def ok(name: str) -> bool:
        bare = name.lstrip("_")
        return bare.startswith(prefix) or bare.startswith("ansible_")

    problems: list[str] = []
    for task, _, location in iter_file_tasks(path):
        pointer = where(path, task, location)
        register = task.get("register")
        if isinstance(register, str) and not ok(register):
            problems.append(f"{pointer}: register: {register} must start with '{prefix}' (var-naming[no-role-prefix])")
        action = task_action(task)
        if short_action(action) == "set_fact":
            for key in module_args(task, action):
                if key != "cacheable" and not ok(str(key)):
                    problems.append(f"{pointer}: set_fact {key} must start with '{prefix}' (var-naming[no-role-prefix])")
    _assert_clean(problems, f"{rel(path)}: role variable prefix")


@pytest.mark.parametrize("role_dir", ROLES, ids=[p.name for p in ROLES])
def test_unit_file_writes_trigger_daemon_reload(role_dir: Path) -> None:
    role = role_dir.name
    tasks = [(t, p, loc) for p in role_files(role_dir, "tasks") for t, _, loc in iter_file_tasks(p)]
    handlers = {
        t.get("name")
        for p in role_files(role_dir, "handlers")
        for t, _, _ in iter_file_tasks(p)
    } | {
        str(item)
        for p in role_files(role_dir, "handlers")
        for t, _, _ in iter_file_tasks(p)
        for item in as_list(t.get("listen"))
    }
    inline_reload = any(
        short_action(task_action(t)) in ("systemd", "systemd_service")
        and module_args(t, task_action(t)).get("daemon_reload") is True
        for t, _, _ in tasks
    )
    problems: list[str] = []
    for task, path, location in tasks:
        action = task_action(task)
        if short_action(action) not in CONFIG_WRITERS:
            continue
        dest = _resolve_path(module_args(task, action).get("dest"), role)
        if not dest or not UNIT_DEST_RE.match(dest):
            continue
        notified = _notified(task)
        if "Reload systemd" in notified:
            if "Reload systemd" not in handlers:
                problems.append(f"{where(path, task, location)}: notifies 'Reload systemd' but the role has no such handler")
            continue
        if inline_reload:
            continue
        problems.append(
            f"{where(path, task, location)}: writes {dest} without notify: Reload systemd "
            "(or an ansible.builtin.systemd daemon_reload: true task); the new unit would not be loaded"
        )
    _assert_clean(problems, f"{rel(role_dir)}: systemd unit roll-out")


@pytest.mark.parametrize("path", UNIT_TEMPLATES, ids=ids_for(UNIT_TEMPLATES))
def test_systemd_unit_templates_are_hardened(path: Path) -> None:
    text = read_text(path)
    required = (
        ("[Unit]", "[Unit] section"),
        ("[Service]", "[Service] section"),
        ("[Install]", "[Install] section (WantedBy=multi-user.target)"),
        ("Restart=", "Restart=on-failure (or always)"),
        ("RestartSec=", "RestartSec=5s"),
        ("After=network-online.target", "After=network-online.target"),
        ("Wants=network-online.target", "Wants=network-online.target"),
        ("NoNewPrivileges=true", "NoNewPrivileges=true"),
        ("PrivateTmp=true", "PrivateTmp=true"),
    )
    problems = [f"{rel(path)}: missing {label}" for needle, label in required if needle not in text]
    if "Restart=no" in text:
        problems.append(f"{rel(path)}: Restart=no disables supervision; use Restart=on-failure")
    if not re.search(r"StartLimitIntervalSec=|StartLimitBurst=", text):
        problems.append(f"{rel(path)}: missing StartLimitIntervalSec=/StartLimitBurst= (restart storm protection)")
    _assert_clean(problems, f"{rel(path)}: systemd unit hardening")


# ---------------------------------------------------------------------------
# Raw-text YAML conventions: booleans and file modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", CONVENTION_YAML, ids=ids_for(CONVENTION_YAML))
def test_yaml_booleans_are_true_or_false(path: Path) -> None:
    problems: list[str] = []
    for number, raw in enumerate(read_text(path).splitlines(), start=1):
        line = strip_yaml_comment(raw)
        if TRUTHY_VALUE_RE.match(line) or TRUTHY_ITEM_RE.match(line):
            problems.append(f"{rel(path)}:{number}: {line.strip()!r} -> use true/false (quote it if a string is meant)")
    _assert_clean(problems, f"{rel(path)}: YAML booleans must be true/false")


@pytest.mark.parametrize("path", CONVENTION_YAML, ids=ids_for(CONVENTION_YAML))
def test_file_modes_are_quoted_octal(path: Path) -> None:
    problems: list[str] = []
    for number, raw in enumerate(read_text(path).splitlines(), start=1):
        match = MODE_LINE_RE.match(strip_yaml_comment(raw))
        if not match:
            continue
        value = match.group(1)
        if MODE_OK_RE.match(value):
            continue
        if MODE_BAD_UNQUOTED_RE.match(value):
            problems.append(f"{rel(path)}:{number}: mode: {value} must be a quoted octal string, e.g. mode: \"0{value.lstrip('0o')[-3:]}\"")
        elif MODE_BAD_QUOTED_RE.match(value):
            problems.append(f"{rel(path)}:{number}: mode: {value} needs the leading zero, e.g. mode: \"0{value.strip(chr(34) + chr(39))}\"")
    _assert_clean(problems, f"{rel(path)}: file modes must be quoted octal strings")
