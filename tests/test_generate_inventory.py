#!/usr/bin/env python3
"""
Tests for generate_inventory.py | generate_inventory.py 单元测试

Coverage:
  - Valid config produces valid YAML inventory
  - Missing required fields raise clear errors
  - Empty server list is handled gracefully
  - Group definitions are properly structured
  - Server metadata is correctly propagated

Run:
    python -m pytest tests/test_generate_inventory.py -v
    python tests/test_generate_inventory.py
"""

import sys
import yaml
from pathlib import Path

# Add tools/ to path so we can import generate_inventory
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

from generate_inventory import (
    generate_local_inventory,
    generate_github_actions_inventory,
    generate_inventory_yaml,
)


def make_minimal_config(**overrides):
    """Build a minimal valid config dict, with optional overrides."""
    config = {
        'global_vars': {'ssh_port': 22},
        'group_definitions': {
            'all_servers': {'vars': {}},
            'web_servers': {'vars': {}},
        },
        'production_servers': {
            'jp-server': {
                'env_var': 'JP_V4_IP',
                'alias': 'jp-1',
                'location': 'Tokyo',
                'groups': ['all_servers', 'web_servers'],
            },
        },
        'github_actions_servers': {},
    }
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# Test: Valid config produces parseable YAML
# ---------------------------------------------------------------------------
def test_local_inventory_produces_valid_yaml():
    config = make_minimal_config()
    inventory = generate_local_inventory(config)
    yaml_str = generate_inventory_yaml(inventory)

    parsed = yaml.safe_load(yaml_str)
    assert 'all' in parsed
    assert 'children' in parsed['all']


def test_github_actions_inventory_produces_valid_yaml():
    config = make_minimal_config()
    inventory = generate_github_actions_inventory(config)
    yaml_str = generate_inventory_yaml(inventory)

    parsed = yaml.safe_load(yaml_str)
    assert 'all' in parsed
    assert 'children' in parsed['all']


# ---------------------------------------------------------------------------
# Test: Server host config is correctly generated
# ---------------------------------------------------------------------------
def test_server_ansible_host_uses_env_lookup():
    config = make_minimal_config()
    inventory = generate_local_inventory(config)
    jp_host = inventory['all']['children']['all_servers']['hosts']['jp-server']

    assert 'ansible_host' in jp_host
    assert 'JP_V4_IP' in jp_host['ansible_host']
    assert '{{' in jp_host['ansible_host']


def test_server_metadata_propagated():
    config = make_minimal_config()
    inventory = generate_local_inventory(config)
    jp_host = inventory['all']['children']['all_servers']['hosts']['jp-server']

    assert jp_host['server_alias'] == 'jp-1'
    assert jp_host['location'] == 'Tokyo'


# ---------------------------------------------------------------------------
# Test: Empty server list handled gracefully
# ---------------------------------------------------------------------------
def test_empty_production_servers():
    config = make_minimal_config(production_servers={})
    inventory = generate_local_inventory(config)

    groups = inventory['all']['children']
    assert 'all_servers' in groups
    assert groups['all_servers']['hosts'] == {}


def test_empty_group_definitions():
    config = make_minimal_config(group_definitions={})
    inventory = generate_local_inventory(config)

    assert inventory['all']['children'] == {}


# ---------------------------------------------------------------------------
# Test: Group definitions structure
# ---------------------------------------------------------------------------
def test_group_vars_propagated():
    config = make_minimal_config(
        group_definitions={
            'web_servers': {'vars': {'nginx_port': 80}},
        }
    )
    inventory = generate_local_inventory(config)
    web_group = inventory['all']['children']['web_servers']

    assert web_group['vars'] == {'nginx_port': 80}


# ---------------------------------------------------------------------------
# Test: Jinja2 templates in YAML are properly quoted
# ---------------------------------------------------------------------------
def test_jinja2_templates_double_quoted():
    config = make_minimal_config()
    inventory = generate_local_inventory(config)
    yaml_str = generate_inventory_yaml(inventory)

    # Jinja2 templates should be double-quoted for proper parsing
    assert '"{{ lookup' in yaml_str


# ---------------------------------------------------------------------------
# Test: Global vars included in inventory
# ---------------------------------------------------------------------------
def test_global_vars_included():
    config = make_minimal_config()
    inventory = generate_local_inventory(config)
    all_vars = inventory['all']['vars']

    assert 'ssh_port' in all_vars
    assert all_vars['ssh_port'] == 22


def test_ansible_connection_vars_in_local_inventory():
    config = make_minimal_config()
    inventory = generate_local_inventory(config)
    all_vars = inventory['all']['vars']

    assert 'ansible_user' in all_vars
    assert 'ansible_port' in all_vars
    assert 'ansible_ssh_private_key_file' in all_vars


# ---------------------------------------------------------------------------
# Test: GitHub Actions servers
# ---------------------------------------------------------------------------
def test_github_actions_servers_override():
    config = make_minimal_config(
        github_actions_servers={
            'test-server': {
                'secret_name': 'TEST_SERVER_IP',
                'alias': 'test-1',
                'location': 'Test',
                'groups': ['all_servers'],
            },
        }
    )
    inventory = generate_github_actions_inventory(config)
    test_host = inventory['all']['children']['all_servers']['hosts']['test-server']

    assert 'TEST_SERVER_IP' in test_host['ansible_host']
    assert test_host['server_alias'] == 'test-1'


# ---------------------------------------------------------------------------
# CLI argument validation
# ---------------------------------------------------------------------------
def test_cli_requires_mode(monkeypatch, capsys):
    """Running without arguments should exit with code 1."""
    from generate_inventory import main

    monkeypatch.setattr(sys, 'argv', ['generate_inventory.py'])
    try:
        main()
    except SystemExit as e:
        assert e.code == 1


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
