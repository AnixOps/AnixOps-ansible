#!/usr/bin/env python3
"""Structure checks for the AnixOps node platform web template."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


def test_node_platform_playbook_uses_a_dedicated_edge_chain():
    playbook = yaml.safe_load((ROOT / "playbooks/provision/node-platform.yml").read_text(encoding="utf-8"))
    play = playbook[0]

    assert play["hosts"] == "anixops_node_platform_servers"
    assert [role for role in play["roles"]] == ["anixops_node_platform", "nginx"]


def test_node_platform_group_vars_proxy_only_frontend():
    group_vars_path = ROOT / "inventories/production/group_vars/anixops_node_platform_servers/main.yml"
    group_vars_text = group_vars_path.read_text(encoding="utf-8")
    group_vars = yaml.safe_load(group_vars_text)
    http_site = group_vars["nginx_sites"][0]
    https_site = group_vars["nginx_sites"][1]
    location = http_site["locations"][0]
    https_location = https_site["locations"][0]

    assert group_vars["nginx_default_site_enabled"] is False
    assert "ANIXOPS_NODE_PLATFORM_SERVER_NAME" in group_vars_text
    assert "ANIXOPS_NODE_PLATFORM_DOMAIN" in group_vars_text
    assert "x.anixops.com" in group_vars_text
    assert "ANIXOPS_NODE_PLATFORM_PUBLIC_URL" in group_vars_text
    assert "anixops_node_platform_public_scheme ~ '://' ~ anixops_node_platform_server_name" in group_vars_text
    assert group_vars["anixops_node_platform_ssl_enabled"]
    assert group_vars["anixops_node_platform_ssl_self_signed_fallback"]
    assert http_site["name"] == "anixops-node-platform"
    assert http_site["server_name"] == "{{ anixops_node_platform_server_name }}"
    assert https_site["server_name"] == "{{ anixops_node_platform_server_name }}"
    assert https_site["listen"] == 443
    assert https_site["ssl"]["cert"] == "{{ anixops_node_platform_ssl_cert }}"
    assert https_site["ssl"]["key"] == "{{ anixops_node_platform_ssl_key }}"
    assert location["proxy_pass"] == "http://127.0.0.1:{{ anixops_node_platform_frontend_port }}"
    assert https_location["proxy_pass"] == "http://127.0.0.1:{{ anixops_node_platform_frontend_port }}"
    assert "proxy_http_version 1.1;" in location["custom_content"]
    assert "proxy_set_header Upgrade $http_upgrade;" in location["custom_content"]


def test_node_platform_templates_expose_app_ports_for_host_edge():
    compose_text = (ROOT / "roles/anixops_node_platform/templates/docker-compose.node-platform.yml.j2").read_text(
        encoding="utf-8"
    )
    env_text = (ROOT / "roles/anixops_node_platform/templates/env.node-platform.j2").read_text(encoding="utf-8")

    assert compose_text.count("ports:") == 2
    assert "host_ip: {{ anixops_node_platform_frontend_bind_address }}" in compose_text
    assert "published: {{ anixops_node_platform_frontend_port }}" in compose_text
    assert "host_ip: {{ anixops_node_platform_api_bind_address }}" in compose_text
    assert "published: {{ anixops_node_platform_api_port }}" in compose_text
    assert "0.0.0.0:{{ anixops_node_platform_api_port }}" not in compose_text
    assert "3001:3001" not in compose_text
    assert "API_URL=http://api:{{ anixops_node_platform_api_port }}" in compose_text
    assert "PROVISION_SERVER_URL=http://provision:{{ anixops_node_platform_provision_port }}" in compose_text
    assert "scheduler:" in compose_text
    assert "container_name: {{ anixops_node_platform_scheduler_container_name }}" in compose_text
    assert "ANIXOPS_API_URL=http://api:{{ anixops_node_platform_api_port }}" in compose_text
    assert "FRONTEND_URL={{ anixops_node_platform_frontend_url }}" in env_text
    assert "ALLOWED_ORIGINS={{ anixops_node_platform_allowed_origins }}" in env_text
    assert "CHAIN_ENVIRONMENT={{ anixops_node_platform_chain_environment }}" in env_text
    assert "CRYPTO_TOPUP_CHAIN={{ anixops_node_platform_crypto_topup_chain }}" in env_text
    assert "AUDIT_ANCHOR_CHAIN={{ anixops_node_platform_audit_anchor_chain }}" in env_text
    assert "PROBE_SERVICE_URL={{ anixops_node_platform_probe_service_url }}" in env_text


def test_node_platform_role_blocks_direct_app_port_ingress():
    defaults_text = (ROOT / "roles/anixops_node_platform/defaults/main.yml").read_text(encoding="utf-8")
    main_text = (ROOT / "roles/anixops_node_platform/tasks/main.yml").read_text(encoding="utf-8")
    configure_text = (ROOT / "roles/anixops_node_platform/tasks/configure.yml").read_text(encoding="utf-8")
    firewall_text = (ROOT / "roles/anixops_node_platform/tasks/firewall.yml").read_text(encoding="utf-8")
    tls_text = (ROOT / "roles/anixops_node_platform/tasks/tls.yml").read_text(encoding="utf-8")

    assert "anixops_node_platform_block_direct_public_ports:" in defaults_text
    assert "anixops_node_platform_api_bind_address: \"127.0.0.1\"" in defaults_text
    assert "anixops_node_platform_ssl_self_signed_fallback" in defaults_text
    assert "anixops_node_platform_ssl_certificate_pem" in defaults_text
    assert "anixops_node_platform_ssl_certificate_key_pem" in defaults_text
    assert "anixops-selfhosted" in defaults_text
    assert "anixops-audit-api" in defaults_text
    assert "label=com.docker.compose.project={{ item }}" in configure_text
    assert "Remove legacy self-hosted compose project containers" in configure_text
    assert "Stop legacy self-hosted containers that can hold application ports" in configure_text
    assert "{{ anixops_node_platform_frontend_port }}" in defaults_text
    assert "{{ anixops_node_platform_api_port }}" in defaults_text
    assert "include_tasks: firewall.yml" in main_text
    assert "include_tasks: tls.yml" in main_text
    assert "Create self-signed node platform TLS certificate when missing" in tls_text
    assert "| b64decode" in tls_text
    assert "Deny direct inbound access to node platform application ports" in firewall_text
    assert "AnixOps edge only" in firewall_text
    assert "80" in firewall_text
    assert "443" in firewall_text
    assert "ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN" in main_text
    assert "ANIXOPS_NODE_PLATFORM_NEXT_PUBLIC_RELEASE_PROFILE" in defaults_text


def test_node_platform_templates_pass_provision_and_release_settings():
    compose_text = (ROOT / "roles/anixops_node_platform/templates/docker-compose.node-platform.yml.j2").read_text(
        encoding="utf-8"
    )
    env_text = (ROOT / "roles/anixops_node_platform/templates/env.node-platform.j2").read_text(encoding="utf-8")

    assert "INSTALL_MODE={{ anixops_node_platform_install_mode }}" in env_text
    assert "DISGUISE_DOMAINS={{ anixops_node_platform_disguise_domains }}" in env_text
    assert "DO_API_TOKEN={{ anixops_node_platform_do_api_token }}" in env_text
    assert "NEXT_PUBLIC_RELEASE_PROFILE={{ anixops_node_platform_next_public_release_profile }}" in env_text
    assert "BILLING_TICK_CRON={{ anixops_node_platform_billing_tick_cron }}" in env_text
    assert "SCHEDULER_ENABLE_CRYPTO_TOPUPS={{ anixops_node_platform_scheduler_enable_crypto_topups }}" in env_text
    assert "INSTALL_MODE=${INSTALL_MODE}" in compose_text
    assert "DISGUISE_DOMAINS=${DISGUISE_DOMAINS}" in compose_text
    assert "DO_API_TOKEN=${DO_API_TOKEN}" in compose_text
    assert "NEXT_PUBLIC_RELEASE_PROFILE: ${NEXT_PUBLIC_RELEASE_PROFILE}" in compose_text


def test_node_platform_verify_checks_scheduler_health():
    verify_text = (ROOT / "roles/anixops_node_platform/tasks/verify.yml").read_text(encoding="utf-8")

    assert "Wait for the scheduler container to become healthy" in verify_text
    assert "{{ anixops_node_platform_scheduler_container_name }}" in verify_text


def test_inventory_example_mentions_the_new_group():
    example_text = (ROOT / "inventories/production/node-platform.example.yml").read_text(encoding="utf-8")

    assert "anixops_node_platform_servers" in example_text


def test_node_platform_has_dedicated_github_actions_entry():
    workflow = yaml.safe_load((ROOT / ".github/workflows/node-platform-deploy.yml").read_text(encoding="utf-8"))
    inventory = yaml.safe_load((ROOT / "inventories/production/node-platform.actions.yml").read_text(encoding="utf-8"))
    docs_text = (ROOT / "docs/ANIXOPS_NODE_PLATFORM.md").read_text(encoding="utf-8")
    env = workflow["jobs"]["deploy"]["env"]

    assert workflow["name"] == "Deploy AnixOps Node Platform"
    assert workflow["jobs"]["deploy"]["environment"] == "node-platform"
    assert "domain" in workflow[True]["workflow_dispatch"]["inputs"]
    assert "ANIXOPS_NODE_PLATFORM_1_V4_SSH" in env
    assert "ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN" in env
    assert "ANIXOPS_NODE_PLATFORM_SSL_ENABLED" in env
    assert env["ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_PEM"] == "${{ secrets.SSL_CERTIFICATE_PEM }}"
    assert env["ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_KEY_PEM"] == "${{ secrets.SSL_CERTIFICATE_KEY_PEM }}"
    assert env["ANIXOPS_NODE_PLATFORM_VULTR_API_KEY"] == "${{ secrets.VULTR_API_KEY }}"
    assert env["ANIXOPS_NODE_PLATFORM_SMTP_HOST"] == "${{ secrets.SMTP_HOST }}"
    assert "anixops_node_platform_servers" in inventory["all"]["children"]
    assert "Deploy AnixOps Node Platform" in docs_text
    assert "GitHub Environment named `node-platform`" in docs_text
    assert "ANIXOPS_NODE_PLATFORM_1_V4_SSH" in docs_text
    assert "ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_PEM" in docs_text


def test_nginx_dynamic_site_template_supports_ssl_vhosts():
    site_template = (ROOT / "roles/nginx/templates/site.conf.j2").read_text(encoding="utf-8")
    nginx_tasks = (ROOT / "roles/nginx/tasks/main.yml").read_text(encoding="utf-8")

    assert "{% if item.ssl is defined %} ssl{% endif %}" in site_template
    assert "{% if item.http2 | default(false) %} http2{% endif %}" in site_template
    assert "ssl_certificate {{ item.ssl.cert }};" in site_template
    assert "item.enabled | default(true) | bool" in nginx_tasks
