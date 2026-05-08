# AnixOps Ansible Infrastructure

Ansible automation for AnixOps' multi-region server fleet. The repository covers provisioning, maintenance, observability, networking, Kubernetes support, and weekly security patching.

## Repository Layout

- `ansible.cfg`, `Makefile`, `requirements.txt`, `requirements.yml`, `VERSION`, `CHANGELOG.md`
- `inventories/` for environment inventories and inventory generation inputs
- `playbooks/` for provisioning, platform, and maintenance workflows
- `roles/` for reusable infrastructure roles
- `observability/` for dashboards and monitoring assets
- `scripts/` for helper scripts used by playbooks and CI
- `tools/` for repository utilities such as inventory generation
- `tests/` for Python and structure checks
- `docs/` for operational documentation
- `.github/workflows/` for GitHub Actions automation

## Getting Started

1. Copy the environment example and fill in your server details.

   ```bash
   cp .env.example .env
   ```

2. Install the Python and Ansible dependencies.

   ```bash
   pip install -r requirements.txt
   ansible-galaxy install -r requirements.yml
   ```

3. Generate or refresh the inventory if needed.

   ```bash
   make gen-inventory
   ```

4. Verify connectivity.

   ```bash
   ansible all -m ping
   # or
   make ping
   ```

5. Deploy the desired playbook.

   ```bash
   ansible-playbook -i inventories/production/hosts.yml playbooks/provision/site.yml
   # or
   make deploy
   ```

## Key Playbooks

| Playbook | Scope | Purpose |
|----------|-------|---------|
| `playbooks/provision/site.yml` | All servers | Full deployment for the common stack |
| `playbooks/provision/quick-setup.yml` | All servers | Fast bootstrap for base services and monitoring |
| `playbooks/provision/web-servers.yml` | `web_servers` | Nginx-only deployment |
| `playbooks/provision/selfhosted-web.yml` | `anixops_selfhosted_servers` | AnixOps self-hosted web stack with internal API and Nginx edge proxy |
| `playbooks/platform/k3s.yml` | `k8s_servers` | Production K3s cluster deployment |
| `playbooks/platform/kind.yml` | `localhost` | Local Kind cluster deployment |
| `playbooks/maintenance/health-check.yml` | All servers | Service health verification |
| `playbooks/maintenance/firewall-setup.yml` | All servers | Firewall rules and monitoring whitelist |
| `playbooks/maintenance/security-patch.yml` | All servers | Weekly Trivy scan, automatic OS patching, and issue-based notification |
| `playbooks/maintenance/rollback.yml` | All servers | Roll back configuration from backups |
| `playbooks/maintenance/ssh-config-force-apply.yml` | All servers | Force-apply SSH configuration |

## Security Patching

The weekly security patch workflow is staged and intentionally small.

- `playbooks/maintenance/security-patch.yml` orchestrates the run
- helper task files live under `playbooks/maintenance/security-patch/`
- helper scripts live under `scripts/`
- unresolved findings are reported through the GitHub Issue backlog

See [docs/SECURITY_PATCHING.md](docs/SECURITY_PATCHING.md) for the workflow details.

## Validation

Common checks:

- `make lint`
- `make syntax`
- `python -m py_compile scripts/*.py tests/*.py`

The GitHub Actions pipeline also runs inventory generation, playbook execution, helper script validation, and security patch reporting.

## Documentation

| Document | Content |
|----------|---------|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Detailed quick start guide |
| [docs/SECRETS_MANAGEMENT.md](docs/SECRETS_MANAGEMENT.md) | Secrets and credentials management |
| [docs/SSH_KEY_MANAGEMENT.md](docs/SSH_KEY_MANAGEMENT.md) | SSH key management workflows |
| [docs/OBSERVABILITY_SETUP.md](docs/OBSERVABILITY_SETUP.md) | Observability stack setup |
| [docs/SECURITY_PATCHING.md](docs/SECURITY_PATCHING.md) | Weekly security patch workflow |
| [docs/SELFHOSTED_WEB_TEMPLATE.md](docs/SELFHOSTED_WEB_TEMPLATE.md) | Self-hosted AnixOps web stack template |

## License

MIT License
