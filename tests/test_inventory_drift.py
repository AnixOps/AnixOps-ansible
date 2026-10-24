#!/usr/bin/env python3
"""Inventory drift and contract tests.

* inventories/production/hosts.yml must be byte-identical to the output of
  `python3 tools/generate_inventory.py local` (servers-config.yml is the
  single source of truth).
* Every group a playbook targets must exist in an inventory.
* Every server address variable must be documented in .env.example.

Run:
    python3 -m pytest -q tests/test_inventory_drift.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from generate_inventory import HEADER, load_config, render_inventory  # noqa: E402

CONFIG_PATH = ROOT / "inventories" / "production" / "servers-config.yml"
HOSTS_PATH = ROOT / "inventories" / "production" / "hosts.yml"
ENV_EXAMPLE = ROOT / ".env.example"
PLAYBOOK_DIR = ROOT / "playbooks"

# Inventory files (not group_vars/host_vars/servers-config) that may define groups.
INVENTORY_FILES = sorted(
    path
    for path in ROOT.glob("inventories/*/*.yml")
    if path.name != "servers-config.yml"
)

EXPECTED_HOSTS = ["jp-1", "uk-1", "us-w-1", "sg-1", "hk-1", "uk-2", "fr-1", "pl-1"]
EXPECTED_GROUPS = [
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
    "dev",
    "prod",
]
IMPLICIT_PATTERNS = {"all", "ungrouped", "localhost"}
# GBK-decoded UTF-8 artefacts (e.g. U+923A "\u923a") plus "?" followed by a non-ASCII char.
MOJIBAKE_RE = re.compile("[\u923a\u93c8\u95ae\u9428\u951b\u9286\u934f\u93b4\u6d60\u7481\u9359]|\\?[^ -~]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _collect_groups(node, found: Set[str]) -> None:
    """Recursively collect group names from a YAML inventory `children` tree."""
    if not isinstance(node, dict):
        return
    for name, body in node.items():
        found.add(name)
        if isinstance(body, dict):
            _collect_groups(body.get("children") or {}, found)


def inventory_groups() -> Set[str]:
    groups: Set[str] = set()
    for path in INVENTORY_FILES:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            _collect_groups(data, groups)
    return groups


def playbook_host_patterns() -> List[Tuple[str, str]]:
    """Return (location, pattern) for every `hosts:` line under playbooks/."""
    pattern_re = re.compile(r"^\s*-?\s*hosts:\s*(.+?)\s*$")
    found: List[Tuple[str, str]] = []
    for path in sorted(PLAYBOOK_DIR.rglob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = pattern_re.match(line)
            if not match:
                continue
            value = match.group(1).strip().strip("'\"")
            if value.startswith("#"):
                continue
            found.append((f"{path.relative_to(ROOT)}:{number}", value))
    return found


def pattern_parts(pattern: str) -> List[str]:
    """Split an Ansible host pattern into plain group/host names.

    Jinja expressions and regex patterns (~...) cannot be resolved statically
    and yield no parts; set operators (:, !, &, ,) are stripped.
    """
    if "{{" in pattern or pattern.startswith("~"):
        return []
    parts = []
    for raw in re.split(r"[:,]", pattern):
        part = raw.strip().lstrip("!&").strip()
        if part and not part.startswith("~"):
            parts.append(part)
    return parts


# ---------------------------------------------------------------------------
# Drift gate
# ---------------------------------------------------------------------------
def test_hosts_yml_matches_generator_output():
    rendered = render_inventory("local", load_config(CONFIG_PATH))
    committed = HOSTS_PATH.read_text(encoding="utf-8")

    assert committed == rendered, (
        "inventories/production/hosts.yml differs from the generator output; "
        "edit servers-config.yml and run `make gen-inventory`"
    )


def test_check_flag_passes_for_committed_inventory():
    proc = subprocess.run(
        [sys.executable, "tools/generate_inventory.py", "local", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "up to date" in proc.stdout


def test_hosts_yml_is_marked_as_generated_and_clean():
    text = HOSTS_PATH.read_text(encoding="utf-8")

    assert text.splitlines()[0] == HEADER
    assert not text.startswith("\ufeff")
    assert "\r" not in text and "\t" not in text
    assert text.endswith("\n")
    assert MOJIBAKE_RE.search(text) is None
    # Retired constructs must not come back.
    for legacy in ("server_aliases", "nginx_test", "DE_1_V4_SSH", "StrictHostKeyChecking", "pl-test-1"):
        assert legacy not in text, f"legacy construct {legacy!r} found in hosts.yml"


# ---------------------------------------------------------------------------
# servers-config.yml contract
# ---------------------------------------------------------------------------
def test_servers_config_is_clean_utf8():
    raw = CONFIG_PATH.read_bytes()
    text = raw.decode("utf-8")

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw and b"\t" not in raw
    assert MOJIBAKE_RE.search(text) is None


def test_servers_config_schema_v2_fleet():
    config = load_config(CONFIG_PATH)

    assert config["schema_version"] == 2
    assert list(config["servers"]) == EXPECTED_HOSTS
    assert list(config["group_definitions"]) == EXPECTED_GROUPS
    assert config["global_vars"] == {"ansible_python_interpreter": "/usr/bin/python3"}
    assert config["group_definitions"]["observability"]["vars"] == {"server_role": "observability"}
    for name, server in config["servers"].items():
        assert server["env_var"] == name.upper().replace("-", "_") + "_V4_SSH"
        assert server["alias"] and " | " in server["alias"]
        assert server["location"] and server["description"]
        assert server["server_environment"] in {"production", "development", "test"}


def test_pl1_k8s_membership_and_host_vars():
    config = load_config(CONFIG_PATH)
    pl1 = config["servers"]["pl-1"]

    assert {"observability", "k8s_control_plane", "k8s_test"} <= set(pl1["groups"])
    assert pl1["host_vars"] == {
        "k8s_role": "master",
        "k8s_provider": "k3s",
        "k3s_version": "v1.31.5+k3s1",
        "k3s_server_args": "--disable traefik --disable servicelb --write-kubeconfig-mode 644",
        "kubeconfig_remote_path": "/etc/rancher/k3s/k3s.yaml",
        "kubeconfig_local_path": "~/.kube/k3s-pl-1.yaml",
        "cluster_name": "k3s-test-pl1",
        "kubeconfig_path": "/etc/rancher/k3s/k3s.yaml",
    }


def test_k8s_servers_group_is_defined_but_empty():
    inventory = yaml.safe_load(HOSTS_PATH.read_text(encoding="utf-8"))
    children = inventory["all"]["children"]

    assert children["k8s_servers"]["hosts"] == {}
    assert children["k8s_test"]["hosts"] == {"pl-1": {}}
    assert children["k8s_control_plane"]["hosts"] == {"pl-1": {}}
    assert "nginx_test" not in children


def test_generated_hosts_carry_metadata_and_env_lookup():
    inventory = yaml.safe_load(HOSTS_PATH.read_text(encoding="utf-8"))
    hosts = inventory["all"]["hosts"]

    assert list(hosts) == EXPECTED_HOSTS
    for name, host in hosts.items():
        env_var = name.upper().replace("-", "_") + "_V4_SSH"
        assert host["ansible_host"] == f"{{{{ lookup('env', '{env_var}') }}}}"
        for key in ("server_alias", "location", "server_environment", "description"):
            assert host[key], f"{name} lacks {key}"
    all_vars = inventory["all"]["vars"]
    assert "ansible_ssh_common_args" not in all_vars
    assert all_vars["ansible_python_interpreter"] == "/usr/bin/python3"


# ---------------------------------------------------------------------------
# Cross-file contracts
# ---------------------------------------------------------------------------
def test_every_server_env_var_is_documented_in_env_example():
    config = load_config(CONFIG_PATH)
    documented = {
        match.group(1)
        for match in re.finditer(r"^([A-Z][A-Z0-9_]*)=", ENV_EXAMPLE.read_text(encoding="utf-8"), re.MULTILINE)
    }
    required = {server["env_var"] for server in config["servers"].values()}
    required |= {"ANSIBLE_USER", "ANSIBLE_PORT", "SSH_KEY_PATH", "GLOBAL_WHITELIST_IPS"}

    missing = sorted(required - documented)
    assert not missing, f".env.example lacks: {missing}"


def test_env_example_has_no_legacy_variable_names():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    for legacy in ("US_W_1_V4=", "_SSH_IP=", "DE_1_V4_SSH", "NETMAKER", "OBSERVABILITY_WHITELIST_IPS"):
        assert legacy not in text, f"legacy name {legacy!r} still in .env.example"
    assert not (ROOT / ".env.netmaker.example").exists()
    assert not (ROOT / "inventories" / "production" / "server_aliases.yml").exists()
    assert not (ROOT / "inventories" / "production" / "hosts.yml.example").exists()


def test_every_playbook_host_pattern_resolves_to_a_known_group():
    known = inventory_groups() | IMPLICIT_PATTERNS
    unresolved: Dict[str, List[str]] = {}
    for location, pattern in playbook_host_patterns():
        missing = [part for part in pattern_parts(pattern) if part not in known]
        if missing:
            unresolved[location] = missing

    assert not unresolved, (
        "playbooks target groups that no inventory defines "
        f"(add them to servers-config.yml group_definitions): {unresolved}"
    )


def test_development_inventory_defines_k8s_local():
    data = yaml.safe_load((ROOT / "inventories" / "development" / "hosts.yml").read_text(encoding="utf-8"))
    group = data["all"]["children"]["k8s_local"]

    assert group["hosts"]["localhost"]["ansible_connection"] == "local"
    assert group["hosts"]["localhost"]["ansible_python_interpreter"] == "{{ ansible_playbook_python }}"
    assert group["vars"] == {"k8s_provider": "kind", "kind_cluster_name": "anixops-dev"}


@pytest.mark.parametrize("path", INVENTORY_FILES, ids=lambda path: str(path.relative_to(ROOT)))
def test_inventory_files_parse_and_have_all_root(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert isinstance(data, dict) and "all" in data, f"{path} must define the `all` group"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
