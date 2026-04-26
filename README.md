# AnixOps Ansible Infrastructure

![Ansible](https://img.shields.io/badge/ansible-2.14+-EE0000?style=flat-square&logo=ansible&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

Enterprise-grade Ansible automation for multi-region server provisioning, monitoring, and network orchestration.

---

## Overview

AnixOps manages a globally distributed fleet of servers across Japan, UK, US, Singapore, Hong Kong, Poland, and France. This project automates:

- **Server hardening** — SSH, NTP, fail2ban, timezone configuration
- **Monitoring stack** — Prometheus, Grafana, Loki, Node Exporter, Promtail (PLG)
- **Network overlay** — Cloudflare Mesh for native IP routing between servers (100.96.0.0/12)
- **Web serving** — Nginx with ACME SSL certificates
- **Firewall management** — Unified UFW/firewalld rules with IP whitelisting for monitoring ports

All production playbooks operate with `serial: "30%"` and `max_fail_percentage: 25` to limit blast radius. Configuration deployments include `backup: yes` and a rollback playbook for recovery.

## Quick Start

### 1. Configure Server IPs

```bash
cp .env.example .env
vim .env  # fill in your server IPs
```

### 2. Prepare SSH Access

```bash
ssh-keygen -t rsa -b 4096 -C "ansible@anixops.com" -f ~/.ssh/id_rsa
ssh-copy-id -i ~/.ssh/id_rsa.pub root@YOUR_SERVER_IP
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Test Connectivity

```bash
ansible all -m ping
# or: make ping
```

### 5. Deploy

```bash
# Full deployment (common config + monitoring + firewall + nginx)
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/site.yml
# or: make deploy

# Quick setup (common + monitoring + firewall, no nginx)
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/quick-setup.yml
# or: make quick-setup
```

---

## Project Structure

```
AnixOps-ansible/
├── site.yml                         # Entry point: full deployment (alias)
├── quickstart.yml                   # Entry point: quick setup (alias)
├── ansible.cfg                      # Ansible global configuration
├── Makefile                         # Command shortcuts (make deploy, make lint, etc.)
├── requirements.txt                 # Python dependencies
│
├── inventories/                     # Environment inventories (single source)
│   ├── production/                  # Live servers
│   │   ├── hosts.yml                # Server + group definitions
│   │   ├── group_vars/              # Environment-level variables
│   │   │   └── all/main.yml
│   │   └── host_vars/               # Host-specific variables
│   │       └── us-w-1.yml
│   ├── staging/                     # [Reserved] Pre-production
│   └── development/                 # [Reserved] Local dev
│
├── playbooks/                       # Organized by lifecycle phase
│   ├── provision/                   # Server initialization
│   │   ├── site.yml                 # Full deployment (all roles)
│   │   ├── quick-setup.yml          # Base + monitoring + firewall
│   │   └── web-servers.yml          # Nginx deployment only
│   ├── platform/                    # Kubernetes platform deployment
│   │   ├── k3s.yml                  # Production K3s cluster
│   │   ├── kind.yml                 # Local Kind cluster
│   │   └── k3s-test.yml             # Remote K3s test environment
│   └── maintenance/                 # Operational tasks
│       ├── health-check.yml         # Service health verification
│       ├── firewall-setup.yml       # Firewall rules + whitelist
│       ├── rollback.yml             # Config rollback from backup
│       └── ssh-config-force-apply.yml
│
├── roles/                           # Infrastructure roles (by domain)
│   ├── base/
│   │   ├── common/                  # System hardening (SSH, NTP, fail2ban)
│   │   └── nginx/                   # Web server + reverse proxy
│   ├── monitoring/
│   │   ├── node_exporter/           # Host metrics exporter (port 9100)
│   │   ├── prometheus/              # Time-series monitoring (port 9090)
│   │   ├── grafana/                 # Visualization dashboards (port 3000)
│   │   ├── loki/                    # Log aggregation (port 3100)
│   │   └── promtail/                # Log shipper agent (port 9080)
│   ├── networking/
│   │   └── cloudflare_mesh/           # Cloudflare Mesh node (warp-cli headless)
│   ├── security/
│   │   ├── firewall/                # UFW/firewalld + IP whitelisting
│   │   └── acme_ssl/                # ACME.sh SSL certificate management
│   └── kubernetes/
│       ├── k8s_provision/           # K8s cluster provisioning (Kind/K3s)
│       └── k8s_dashboard_deploy/    # K8s Dashboard deployment
│
├── observability/                   # Grafana dashboards, Prometheus rules
├── scripts/                         # Utility scripts (anixops.sh, etc.)
├── tools/                           # Helper tools (inventory generator)
├── tests/                           # Test suite
├── docs/                            # Active documentation
└── .github/workflows/               # CI/CD pipelines
```

---

## Role Reference

### Base

| Role | Description | Idempotent | Rollback |
|------|-------------|------------|----------|
| `common` | SSH hardening, NTP (chrony), fail2ban, timezone | Yes (template) | `rollback_role=common` |
| `nginx` | Nginx web server, reverse proxy, SSL vhosts | Yes (template) | `rollback_role=nginx` |

### Monitoring

| Role | Description | Port | Idempotent | Rollback |
|------|-------------|------|------------|----------|
| `node_exporter` | Host metrics exporter | 9100 | Yes (template) | `rollback_role=node_exporter` |
| `prometheus` | Time-series monitoring server | 9090 | Yes (template) | `rollback_role=prometheus` |
| `grafana` | Visualization dashboards | 3000 | Yes (template) | `rollback_role=grafana` |
| `loki` | Log aggregation server | 3100 | Yes (template) | `rollback_role=loki` |
| `promtail` | Log shipper agent | 9080 | Yes (template) | `rollback_role=promtail` |

### Networking

| Role | Description | Idempotent | Rollback |
|------|-------------|------------|----------|
| `cloudflare_mesh` | Cloudflare Mesh node (native IP routing) | Yes (creates check) | Dashboard remove |

### Security

| Role | Description | Idempotent | Rollback |
|------|-------------|------------|----------|
| `firewall` | UFW/firewalld rules, IP whitelisting | Yes (UFW idempotent) | Manual (ufw reset) |
| `acme_ssl` | ACME.sh SSL cert issuance + renewal | Yes (block/rescue) | Manual cert restore |

### Kubernetes

| Role | Description | Idempotent | Rollback |
|------|-------------|------------|----------|
| `k8s_provision` | Kind/K3s cluster provisioning | Partial | Manual |
| `k8s_dashboard_deploy` | K8s Dashboard + API proxy | Yes (template) | Manual |

---

## Playbook Reference

### Provision (Server Initialization)

| Playbook | Scope | Content |
|----------|-------|---------|
| `playbooks/provision/site.yml` | All servers | Full deployment: common + node_exporter + promtail + firewall + nginx |
| `playbooks/provision/quick-setup.yml` | All servers | Quick init: common + monitoring + firewall |
| `playbooks/provision/web-servers.yml` | web_servers group | Nginx deployment only |

### Platform (Kubernetes)

| Playbook | Scope | Content |
|----------|-------|---------|
| `playbooks/platform/k3s.yml` | k8s_servers | Production K3s cluster |
| `playbooks/platform/kind.yml` | localhost | Local Kind cluster |
| `playbooks/platform/k3s-test.yml` | k8s_test | Remote K3s test environment |

### Maintenance (Operations)

| Playbook | Scope | Content |
|----------|-------|---------|
| `playbooks/maintenance/health-check.yml` | All servers | Service health verification |
| `playbooks/maintenance/firewall-setup.yml` | All servers | Firewall rules + monitoring whitelist |
| `playbooks/maintenance/rollback.yml` | All servers | Config rollback from backup |
| `playbooks/maintenance/ssh-config-force-apply.yml` | All servers | Force-apply SSH configuration |

---

## Server Inventory

| Host | Alias | Role | Environment | Provider |
|------|-------|------|-------------|----------|
| `jp-1` | Japan-1 | web_server, mesh_node | test | Oracle |
| `uk-1` | UK-1 | web_server, mesh_node | test | Oracle |
| `us-w-1` | US-West-1 | web_server, mesh_node | production | Oracle |
| `sg-1` | Singapore-1 | proxy_server, mesh_node | production | Aliyun |
| `jp-2` | Japan-2 | proxy_server, mesh_node | production | Churros |
| `hk-1` | Hong Kong-1 | proxy_server, mesh_node | production | Zouter |
| `uk-2` | UK-2 | proxy_server, mesh_node | production | Akko |
| `pl-1` | Poland-1 | observability, mesh_node, k8s | production | OVH |
| `fr-1` | France-1 | k8s_server (master) | development | OVH |

---

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make lint` | Run yamllint + ansible-lint |
| `make syntax` | Check playbook syntax |
| `make ping` | Test server connectivity |
| `make deploy` | Full deployment (site.yml) |
| `make quick-setup` | Quick initialization |
| `make firewall-setup` | Configure firewall + whitelist |
| `make health-check` | Run health checks |
| `make deploy-web` | Deploy web servers (nginx) |
| `make ssh-fix` | Force-apply SSH config (5s countdown) |
| `make deploy-dry-run` | Check mode (no changes) |
| `make list-hosts` | List configured hosts |
| `make clean` | Clean temporary files |

---

## Safety & Rollback

### Batch Safety Limits

All production playbooks enforce:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `serial` | `"30%"` or `1` | Limits parallel server operations (health checks run one-by-one) |
| `max_fail_percentage` | `25` or `0` | Stops execution if failure rate exceeds threshold |

### Rollback

Configuration files are backed up automatically during deployment (`backup: yes`). To rollback:

```bash
# List available backups (dry run)
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=nginx rollback_dry_run=yes"

# Rollback to most recent backup
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=prometheus"

# Rollback to specific timestamp
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=nginx rollback_timestamp=20260426_120000"
```

Supported rollback roles: `nginx`, `common`, `prometheus`, `loki`, `grafana`, `node_exporter`, `promtail`

### CI Checks

Every push is validated by:

1. **YAML syntax** — `yamllint` on all YAML files
2. **Ansible syntax** — `ansible-playbook --syntax-check` on all playbooks
3. **Backup coverage** — `scripts/check-backup-coverage.py` scans for missing `backup: yes`
4. **Secret scanning** — TruffleHog detects committed credentials

---

## Manual Intervention Required

The following operations require manual approval and are **not** automated:

- Database migrations or data deletion
- OS upgrades (kernel updates, major version upgrades)
- Large-scale network topology changes (Cloudflare Mesh routing)
- Troubleshooting after rollback failure
- Initial server provisioning (network, storage, permissions verification)

---

## More Documentation

| Document | Content |
|----------|---------|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Detailed 5-minute quick start guide |
| [docs/SECRETS_MANAGEMENT.md](docs/SECRETS_MANAGEMENT.md) | Secrets and credentials management |
| [docs/SSH_KEY_MANAGEMENT.md](docs/SSH_KEY_MANAGEMENT.md) | SSH key management workflows |
| [docs/OBSERVABILITY_SETUP.md](docs/OBSERVABILITY_SETUP.md) | Observability stack setup |
| [roles/README-stability.md](roles/README-stability.md) | Stability decision framework |

---

## License

MIT License
