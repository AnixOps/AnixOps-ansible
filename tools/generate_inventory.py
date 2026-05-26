#!/usr/bin/env python3
"""
Inventory generator for Ansible.

Reads inventories/production/servers-config.yml and renders either:
- local inventory
- GitHub Actions inventory
"""

import argparse
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(config_file: str = "inventories/production/servers-config.yml") -> Dict[str, Any]:
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    config_path = project_root / config_file

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_local_inventory(config: Dict[str, Any]) -> Dict[str, Any]:
    inventory = {
        "all": {
            "children": {},
            "vars": {
                "ansible_user": "{{ lookup('env', 'ANSIBLE_USER') | default('root', true) }}",
                "ansible_port": "{{ lookup('env', 'ANSIBLE_PORT') | default('22', true) | int }}",
                "ansible_ssh_private_key_file": "{{ lookup('env', 'SSH_KEY_PATH') | default('~/.ssh/id_rsa', true) }}",
                **config["global_vars"],
            },
        }
    }

    groups: Dict[str, Dict[str, Any]] = {}
    for group_name, group_def in config["group_definitions"].items():
        groups[group_name] = {
            "hosts": {},
            "vars": group_def.get("vars", {}),
        }

    for server_name, server_info in config["production_servers"].items():
        host_config = {
            "ansible_host": f"{{{{ lookup('env', '{server_info['env_var']}') }}}}",
        }

        if "alias" in server_info:
            host_config["server_alias"] = server_info["alias"]
        if "location" in server_info:
            host_config["location"] = server_info["location"]
        if "server_environment" in server_info:
            host_config["server_environment"] = server_info["server_environment"]
        if "description" in server_info:
            host_config["description"] = server_info["description"]

        for group in server_info["groups"]:
            if group in groups:
                groups[group]["hosts"][server_name] = host_config

    inventory["all"]["children"] = groups
    return inventory


def generate_github_actions_inventory(config: Dict[str, Any]) -> Dict[str, Any]:
    inventory = {
        "all": {
            "children": {},
            "vars": config["global_vars"].copy(),
        }
    }

    inventory["all"]["vars"].update(
        {
            "ansible_user": "{{ lookup('env', 'ANSIBLE_USER') | default('root', true) }}",
            "ansible_port": "{{ lookup('env', 'ANSIBLE_PORT') | default('22', true) | int }}",
            "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
        }
    )

    groups: Dict[str, Dict[str, Any]] = {}
    for group_name, group_def in config["group_definitions"].items():
        groups[group_name] = {
            "hosts": {},
            "vars": group_def.get("vars", {}),
        }

    for server_name, server_info in config.get("production_servers", {}).items():
        host_config = {
            "ansible_host": f"{{{{ lookup('env', '{server_info['env_var']}') }}}}",
        }

        if "alias" in server_info:
            host_config["server_alias"] = server_info["alias"]
        if "location" in server_info:
            host_config["location"] = server_info["location"]
        if "server_environment" in server_info:
            host_config["server_environment"] = server_info["server_environment"]

        for group in server_info["groups"]:
            if group in groups:
                groups[group]["hosts"][server_name] = host_config

    for server_name, server_info in config.get("github_actions_servers", {}).items():
        host_config = {
            "ansible_host": f"{{{{ lookup('env', '{server_info['secret_name']}') }}}}",
        }

        if "alias" in server_info:
            host_config["server_alias"] = server_info["alias"]
        if "location" in server_info:
            host_config["location"] = server_info["location"]
        if "server_environment" in server_info:
            host_config["server_environment"] = server_info["server_environment"]

        for group in server_info["groups"]:
            if group in groups:
                groups[group]["hosts"][server_name] = host_config

    inventory["all"]["children"] = groups
    return inventory


def generate_inventory_yaml(inventory: Dict[str, Any]) -> str:
    class NoAliasDumper(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True

    def represent_str(dumper, data):
        if "{{" in data and "}}" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    NoAliasDumper.add_representer(str, represent_str)

    return yaml.dump(
        inventory,
        Dumper=NoAliasDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        indent=2,
    )


def render_inventory(mode: str, config: Dict[str, Any]) -> str:
    if mode == "local":
        return (
            "# Local inventory (uses environment variables)\n"
            "# Generated from servers-config.yml\n\n"
            + generate_inventory_yaml(generate_local_inventory(config))
        )

    if mode == "github-actions":
        return (
            "# GitHub Actions inventory (uses secrets as env vars)\n"
            "# Generated from servers-config.yml\n\n"
            + generate_inventory_yaml(generate_github_actions_inventory(config))
        )

    raise ValueError(f"Unknown mode: {mode}")


def write_output(output_path: str, content: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Ansible inventory")
    parser.add_argument("mode", choices=["local", "github-actions"])
    parser.add_argument("--output", "-o", help="Write the inventory to a file")
    args = parser.parse_args()

    config = load_config()
    rendered = render_inventory(args.mode, config)

    if args.output:
        write_output(args.output, rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
