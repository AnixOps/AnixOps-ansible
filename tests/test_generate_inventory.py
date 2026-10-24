#!/usr/bin/env python3
"""Unit tests for tools/generate_inventory.py.

Covers schema v2 parsing, host metadata / host_vars propagation, legacy (v1)
compatibility, validation errors, rendering and the CLI (--output, --check).

Run:
    python3 -m pytest -q tests/test_generate_inventory.py
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from generate_inventory import (  # noqa: E402  (path manipulation above)
    CONNECTION_VARS,
    HEADER,
    InventoryConfigError,
    generate_github_actions_inventory,
    generate_inventory_yaml,
    generate_local_inventory,
    load_config,
    main,
    parse_config,
    render_inventory,
)

SCRIPT = ROOT / "tools" / "generate_inventory.py"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def make_config(**overrides):
    """Minimal schema v2 configuration."""
    config = {
        "schema_version": 2,
        "global_vars": {"ansible_python_interpreter": "/usr/bin/python3"},
        "group_definitions": {
            "web_servers": {"description": "Web", "vars": {"server_role": "web"}},
            "observability": {"description": "PLG", "vars": {"server_role": "observability"}},
            "k8s_servers": {"description": "intentionally empty", "vars": {"server_role": "kubernetes"}},
            "prod": {"description": "label group without vars"},
        },
        "servers": {
            "jp-1": {
                "env_var": "JP_1_V4_SSH",
                "alias": "日本-1 | Japan-1",
                "location": "Japan",
                "description": "Japan web server",
                "server_environment": "test",
                "groups": ["web_servers"],
            },
            "pl-1": {
                "env_var": "PL_1_V4_SSH",
                "alias": "波兰-1 | Poland-1",
                "location": "Poland",
                "description": "Poland observability server",
                "server_environment": "production",
                "groups": ["web_servers", "observability"],
                "host_vars": {"k8s_role": "master", "k3s_version": "v1.27.3+k3s1"},
            },
        },
    }
    config.update(overrides)
    return config


def make_legacy_config(**overrides):
    """Schema v1 configuration (production_servers / github_actions_servers)."""
    config = {
        "global_vars": {"ansible_python_interpreter": "/usr/bin/python3"},
        "group_definitions": {
            "all_servers": {"vars": {}},
            "web_servers": {"vars": {"server_role": "web"}},
        },
        "production_servers": {
            "jp-server": {
                "env_var": "JP_V4_IP",
                "alias": "jp-1",
                "location": "Tokyo",
                "roles": ["web"],
                "groups": ["all_servers", "web_servers"],
            },
        },
        "github_actions_servers": {},
    }
    config.update(overrides)
    return config


def with_server(config, name, **fields):
    config = copy.deepcopy(config)
    config["servers"][name] = fields
    return config


def write_config(tmp_path: Path, config, name="servers-config.yml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Structure of the generated inventory
# ---------------------------------------------------------------------------
def test_local_inventory_round_trips_through_yaml():
    inventory = generate_local_inventory(make_config())
    parsed = yaml.safe_load(generate_inventory_yaml(inventory))

    assert parsed == inventory
    assert set(parsed["all"]) == {"hosts", "children", "vars"}


def test_hosts_are_defined_once_and_referenced_by_groups():
    inventory = generate_local_inventory(make_config())
    all_hosts = inventory["all"]["hosts"]
    children = inventory["all"]["children"]

    assert list(all_hosts) == ["jp-1", "pl-1"]
    assert children["web_servers"]["hosts"] == {"jp-1": {}, "pl-1": {}}
    assert children["observability"]["hosts"] == {"pl-1": {}}
    assert children["k8s_servers"]["hosts"] == {}
    # Group order follows group_definitions.
    assert list(children) == ["web_servers", "observability", "k8s_servers", "prod"]


def test_ansible_host_uses_env_lookup():
    inventory = generate_local_inventory(make_config())

    assert inventory["all"]["hosts"]["jp-1"]["ansible_host"] == "{{ lookup('env', 'JP_1_V4_SSH') }}"
    assert inventory["all"]["hosts"]["pl-1"]["ansible_host"] == "{{ lookup('env', 'PL_1_V4_SSH') }}"


def test_metadata_vars_emitted_for_every_host():
    inventory = generate_local_inventory(make_config())
    jp = inventory["all"]["hosts"]["jp-1"]

    assert jp["server_alias"] == "日本-1 | Japan-1"
    assert jp["location"] == "Japan"
    assert jp["server_environment"] == "test"
    assert jp["description"] == "Japan web server"
    # Stable key order: address first, then metadata.
    assert list(jp) == ["ansible_host", "server_alias", "location", "server_environment", "description"]


def test_metadata_omitted_when_not_configured():
    config = make_config()
    config["servers"]["bare"] = {"env_var": "BARE_V4_SSH", "groups": ["prod"]}
    inventory = generate_local_inventory(config)

    assert inventory["all"]["hosts"]["bare"] == {"ansible_host": "{{ lookup('env', 'BARE_V4_SSH') }}"}


def test_host_vars_propagated_after_metadata():
    inventory = generate_local_inventory(make_config())
    pl = inventory["all"]["hosts"]["pl-1"]

    assert pl["k8s_role"] == "master"
    assert pl["k3s_version"] == "v1.27.3+k3s1"
    assert list(pl)[-2:] == ["k8s_role", "k3s_version"]


def test_group_vars_propagated_and_omitted_when_empty():
    children = generate_local_inventory(make_config())["all"]["children"]

    assert children["web_servers"]["vars"] == {"server_role": "web"}
    assert children["k8s_servers"]["vars"] == {"server_role": "kubernetes"}
    assert "vars" not in children["prod"]


@pytest.mark.parametrize("generate", [generate_local_inventory, generate_github_actions_inventory])
def test_connection_and_global_vars_in_all_vars_for_both_modes(generate):
    all_vars = generate(make_config())["all"]["vars"]

    assert all_vars["ansible_user"] == "{{ lookup('env', 'ANSIBLE_USER') | default('root', true) }}"
    assert all_vars["ansible_port"] == "{{ lookup('env', 'ANSIBLE_PORT') | default('22', true) | int }}"
    assert (
        all_vars["ansible_ssh_private_key_file"]
        == "{{ lookup('env', 'SSH_KEY_PATH') | default('~/.ssh/id_rsa', true) }}"
    )
    assert all_vars["ansible_python_interpreter"] == "/usr/bin/python3"
    assert list(all_vars)[:3] == list(CONNECTION_VARS)


def test_global_vars_can_override_connection_defaults():
    config = make_config(global_vars={"ansible_user": "deploy"})
    all_vars = generate_local_inventory(config)["all"]["vars"]

    assert all_vars["ansible_user"] == "deploy"


def test_modes_render_identically_except_header():
    config = make_config()
    local = render_inventory("local", config)
    actions = render_inventory("github-actions", config)

    assert local != actions
    local_body = [line for line in local.splitlines() if not line.startswith("#")]
    actions_body = [line for line in actions.splitlines() if not line.startswith("#")]
    assert local_body == actions_body
    assert "# Mode: local" in local
    assert "# Mode: github-actions" in actions


def test_rendered_output_has_header_and_document_start():
    rendered = render_inventory("local", make_config())
    lines = rendered.splitlines()

    assert lines[0] == HEADER
    assert HEADER == "# GENERATED FILE — edit servers-config.yml and run `make gen-inventory`"
    assert "schema v2" in lines[1]
    assert "---" in lines[:6]
    assert rendered.endswith("\n")


def test_jinja_templates_are_double_quoted():
    rendered = render_inventory("local", make_config())

    assert "ansible_host: \"{{ lookup('env', 'JP_1_V4_SSH') }}\"" in rendered
    assert "ansible_port: \"{{ lookup('env', 'ANSIBLE_PORT') | default('22', true) | int }}\"" in rendered


def test_output_is_deterministic():
    config = make_config()

    assert render_inventory("local", config) == render_inventory("local", copy.deepcopy(config))


def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match="Unknown mode"):
        render_inventory("staging", make_config())


def test_schema_version_inferred_from_servers_key():
    config = make_config()
    del config["schema_version"]

    assert parse_config(config).schema_version == 2


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------
def _no_env_var(config):
    del config["servers"]["jp-1"]["env_var"]


def _empty_env_var(config):
    config["servers"]["jp-1"]["env_var"] = ""


def _lowercase_env_var(config):
    config["servers"]["jp-1"]["env_var"] = "jp_1_v4_ssh"


def _unknown_group(config):
    config["servers"]["jp-1"]["groups"] = ["web_servers", "nginx_test"]


def _empty_groups(config):
    config["servers"]["jp-1"]["groups"] = []


def _groups_not_a_list(config):
    config["servers"]["jp-1"]["groups"] = "web_servers"


def _repeated_group(config):
    config["servers"]["jp-1"]["groups"] = ["web_servers", "web_servers"]


def _host_vars_not_mapping(config):
    config["servers"]["pl-1"]["host_vars"] = ["k8s_role=master"]


def _host_vars_override_generated(config):
    config["servers"]["pl-1"]["host_vars"] = {"ansible_host": "1.2.3.4"}


def _unknown_server_key(config):
    config["servers"]["jp-1"]["roles"] = ["web"]


def _alias_not_string(config):
    config["servers"]["jp-1"]["alias"] = ["jp"]


def _duplicate_env_var(config):
    config["servers"]["pl-test-1"] = {"env_var": "PL_1_V4_SSH", "groups": ["prod"]}


def _invalid_hostname(config):
    config["servers"]["bad host!"] = {"env_var": "BAD_V4_SSH", "groups": ["prod"]}


def _empty_server(config):
    config["servers"]["empty"] = None


def _unsupported_schema(config):
    config["schema_version"] = 3


def _schema_not_int(config):
    config["schema_version"] = "2"


def _missing_servers(config):
    del config["servers"]


def _legacy_keys_in_v2(config):
    config["production_servers"] = {}


def _unknown_top_level(config):
    config["servers_extra"] = {}


def _group_definitions_not_mapping(config):
    config["group_definitions"] = ["web_servers"]


def _group_unknown_key(config):
    config["group_definitions"]["web_servers"]["hosts"] = {}


def _group_vars_not_mapping(config):
    config["group_definitions"]["web_servers"]["vars"] = ["server_role=web"]


def _invalid_group_name(config):
    config["group_definitions"]["web-servers"] = {}


def _global_vars_not_mapping(config):
    config["global_vars"] = ["x"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_no_env_var, "missing `env_var`"),
        (_empty_env_var, "missing `env_var`"),
        (_lowercase_env_var, "UPPER_SNAKE_CASE"),
        (_unknown_group, "unknown group"),
        (_empty_groups, "non-empty list"),
        (_groups_not_a_list, "non-empty list"),
        (_repeated_group, "more than once"),
        (_host_vars_not_mapping, "must be a mapping"),
        (_host_vars_override_generated, "may not override"),
        (_unknown_server_key, "unknown key"),
        (_alias_not_string, "must be a string"),
        (_duplicate_env_var, "used by both"),
        (_invalid_hostname, "invalid hostname"),
        (_empty_server, "definition is empty"),
        (_unsupported_schema, "unsupported schema_version"),
        (_schema_not_int, "must be an integer"),
        (_missing_servers, "missing `servers`"),
        (_legacy_keys_in_v2, "schema v2 replaces"),
        (_unknown_top_level, "unknown top-level key"),
        (_group_definitions_not_mapping, "must be a mapping"),
        (_group_unknown_key, "unknown key"),
        (_group_vars_not_mapping, "must be a mapping"),
        (_invalid_group_name, "invalid group name"),
        (_global_vars_not_mapping, "must be a mapping"),
    ],
    ids=lambda value: value.__name__ if callable(value) else value,
)
def test_validation_errors_are_explicit(mutate, message):
    config = make_config()
    mutate(config)

    with pytest.raises(InventoryConfigError, match=message):
        parse_config(config)


def test_error_message_names_the_offending_server():
    config = make_config()
    config["servers"]["jp-1"]["groups"] = ["missing_group"]

    with pytest.raises(InventoryConfigError, match=r"server 'jp-1': unknown group\(s\) \['missing_group'\]"):
        generate_local_inventory(config)


def test_top_level_must_be_mapping():
    with pytest.raises(InventoryConfigError, match="must be a mapping"):
        parse_config(["not", "a", "mapping"])


def test_duplicate_host_in_yaml_is_rejected(tmp_path):
    path = tmp_path / "dup.yml"
    path.write_text(
        "schema_version: 2\n"
        "group_definitions:\n  web_servers: {}\n"
        "servers:\n"
        "  jp-1:\n    env_var: JP_1_V4_SSH\n    groups: [web_servers]\n"
        "  jp-1:\n    env_var: JP_2_V4_SSH\n    groups: [web_servers]\n",
        encoding="utf-8",
    )

    with pytest.raises(InventoryConfigError, match="duplicate key 'jp-1'"):
        load_config(path)


def test_load_config_missing_file(tmp_path):
    with pytest.raises(InventoryConfigError, match="not found"):
        load_config(tmp_path / "nope.yml")


def test_load_config_invalid_yaml(tmp_path):
    path = tmp_path / "broken.yml"
    path.write_text("servers: [unclosed\n", encoding="utf-8")

    with pytest.raises(InventoryConfigError, match="invalid YAML"):
        load_config(path)


def test_load_config_rejects_non_mapping_document(tmp_path):
    path = tmp_path / "list.yml"
    path.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(InventoryConfigError, match="top level must be a mapping"):
        load_config(path)


def test_load_config_reads_repository_config():
    config = load_config()

    assert config["schema_version"] == 2
    assert "pl-1" in config["servers"]


# ---------------------------------------------------------------------------
# Legacy schema (v1) compatibility
# ---------------------------------------------------------------------------
def test_legacy_production_servers_supported():
    inventory = generate_local_inventory(make_legacy_config())
    host = inventory["all"]["hosts"]["jp-server"]

    assert host["ansible_host"] == "{{ lookup('env', 'JP_V4_IP') }}"
    assert host["server_alias"] == "jp-1"
    assert host["location"] == "Tokyo"
    assert inventory["all"]["children"]["web_servers"]["hosts"] == {"jp-server": {}}
    assert inventory["all"]["children"]["all_servers"]["hosts"] == {"jp-server": {}}
    assert parse_config(make_legacy_config()).schema_version == 1


def test_legacy_github_actions_servers_only_rendered_in_ci_mode():
    config = make_legacy_config(
        github_actions_servers={
            "test-server": {
                "secret_name": "TEST_SERVER_IP",
                "alias": "test-1",
                "location": "Test",
                "groups": ["all_servers"],
            },
        }
    )

    local = generate_local_inventory(config)
    assert "test-server" not in local["all"]["hosts"]

    actions = generate_github_actions_inventory(config)
    host = actions["all"]["hosts"]["test-server"]
    assert host["ansible_host"] == "{{ lookup('env', 'TEST_SERVER_IP') }}"
    assert host["server_alias"] == "test-1"
    assert actions["all"]["children"]["all_servers"]["hosts"] == {"jp-server": {}, "test-server": {}}


def test_legacy_duplicate_host_across_sections_rejected():
    config = make_legacy_config(
        github_actions_servers={"jp-server": {"secret_name": "OTHER", "groups": ["all_servers"]}}
    )

    with pytest.raises(InventoryConfigError, match="duplicate host 'jp-server'"):
        parse_config(config)


def test_legacy_empty_sections_handled():
    inventory = generate_local_inventory(make_legacy_config(production_servers={}))

    assert inventory["all"]["hosts"] == {}
    assert inventory["all"]["children"]["all_servers"]["hosts"] == {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_cli_requires_mode(monkeypatch):
    """argparse exits with status 2 when the positional mode is missing."""
    monkeypatch.setattr(sys, "argv", ["generate_inventory.py"])

    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 2


def test_cli_rejects_unknown_mode():
    with pytest.raises(SystemExit) as excinfo:
        main(["staging"])
    assert excinfo.value.code == 2


def test_cli_prints_rendered_inventory_to_stdout(tmp_path, capsys):
    config_path = write_config(tmp_path, make_config())

    assert main(["local", "--config", str(config_path)]) == 0
    assert capsys.readouterr().out == render_inventory("local", make_config())


def test_cli_writes_output_file(tmp_path):
    config_path = write_config(tmp_path, make_config())
    output = tmp_path / "out" / "hosts.yml"

    assert main(["github-actions", "--config", str(config_path), "--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == render_inventory("github-actions", make_config())


def test_cli_check_passes_when_up_to_date(tmp_path, capsys):
    config_path = write_config(tmp_path, make_config())
    output = tmp_path / "hosts.yml"
    output.write_text(render_inventory("local", make_config()), encoding="utf-8")

    assert main(["local", "--config", str(config_path), "--output", str(output), "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_cli_check_reports_drift_with_unified_diff(tmp_path, capsys):
    config_path = write_config(tmp_path, make_config())
    output = tmp_path / "hosts.yml"
    stale = render_inventory("local", make_config()).replace("Japan", "Nippon")
    output.write_text(stale, encoding="utf-8")

    assert main(["local", "--config", str(config_path), "--output", str(output), "--check"]) == 1
    captured = capsys.readouterr()
    assert "--- " in captured.out and "+++ " in captured.out
    assert re.search(r"^-\s+location: Nippon$", captured.out, re.MULTILINE)
    assert re.search(r"^\+\s+location: Japan$", captured.out, re.MULTILINE)
    assert "out of date" in captured.err
    # --check never writes.
    assert output.read_text(encoding="utf-8") == stale


def test_cli_check_fails_when_target_missing(tmp_path, capsys):
    config_path = write_config(tmp_path, make_config())

    assert main(["local", "--config", str(config_path), "--output", str(tmp_path / "missing.yml"), "--check"]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_cli_configuration_error_exits_2(tmp_path, capsys):
    config = make_config()
    del config["servers"]["jp-1"]["env_var"]
    config_path = write_config(tmp_path, config)

    assert main(["local", "--config", str(config_path)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "jp-1" in err and "missing `env_var`" in err


def test_cli_missing_config_exits_2(tmp_path, capsys):
    assert main(["local", "--config", str(tmp_path / "nope.yml")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_exit_codes_via_subprocess(tmp_path):
    no_args = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert no_args.returncode == 2

    config_path = write_config(tmp_path, make_config())
    stale = tmp_path / "hosts.yml"
    stale.write_text("stale\n", encoding="utf-8")
    drift = subprocess.run(
        [sys.executable, str(SCRIPT), "local", "--config", str(config_path), "--output", str(stale), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert drift.returncode == 1
    assert "+++ " in drift.stdout

    ok = subprocess.run(
        [sys.executable, str(SCRIPT), "local", "--config", str(config_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0
    assert ok.stdout == render_inventory("local", make_config())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
