#!/usr/bin/env python3
"""Structure checks for the AnixOps self-hosted web template."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


def test_selfhosted_playbook_uses_a_dedicated_edge_chain():
    playbook = yaml.safe_load((ROOT / "playbooks/provision/selfhosted-web.yml").read_text(encoding="utf-8"))
    play = playbook[0]

    assert play["hosts"] == "anixops_selfhosted_servers"
    assert [role for role in play["roles"]] == ["anixops_selfhosted", "nginx"]


def test_selfhosted_group_vars_proxy_only_frontend():
    group_vars = yaml.safe_load(
        (ROOT / "inventories/production/group_vars/anixops_selfhosted_servers/main.yml").read_text(encoding="utf-8")
    )
    site = group_vars["nginx_sites"][0]
    location = site["locations"][0]

    assert group_vars["nginx_default_site_enabled"] is False
    assert site["server_name"] == "{{ anixops_server_name }}"
    assert location["proxy_pass"] == "http://127.0.0.1:{{ anixops_frontend_port }}"
    assert "proxy_http_version 1.1;" in location["custom_content"]
    assert "proxy_set_header Upgrade $http_upgrade;" in location["custom_content"]


def test_selfhosted_templates_keep_api_internal():
    compose_text = (ROOT / "roles/anixops_selfhosted/templates/docker-compose.selfhosted.yml.j2").read_text(
        encoding="utf-8"
    )
    env_text = (ROOT / "roles/anixops_selfhosted/templates/env.selfhosted.j2").read_text(encoding="utf-8")

    assert compose_text.count("ports:") == 1
    assert "{{ anixops_frontend_bind_address }}:{{ anixops_frontend_port }}:30000" in compose_text
    assert "8787:8787" not in compose_text
    assert "3001:3001" not in compose_text
    assert "API_URL=http://api:{{ anixops_api_port }}" in compose_text
    assert "PROVISION_SERVER_URL=http://provision:{{ anixops_provision_port }}" in compose_text
    assert "FRONTEND_URL={{ anixops_frontend_url }}" in env_text
    assert "ALLOWED_ORIGINS={{ anixops_allowed_origins }}" in env_text
    assert "PROBE_SERVICE_URL={{ anixops_probe_service_url }}" in env_text


def test_inventory_example_mentions_the_new_group():
    example_text = (ROOT / "inventories/production/selfhosted-web.example.yml").read_text(encoding="utf-8")

    assert "anixops_selfhosted_servers" in example_text
