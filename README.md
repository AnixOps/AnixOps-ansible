# AnixOps Ansible Infrastructure | AnixOps Ansible 基础设施

Ansible automation for the AnixOps multi-region server fleet: provisioning, the PLG
observability stack (Prometheus, Loki, Grafana), the V2board panel and V2bX nodes, the node
platform web stack, local and remote Kubernetes labs, lifecycle management with rollback, and a
weekly security patch run. Current release: see [VERSION](VERSION) and [CHANGELOG.md](CHANGELOG.md).

Every file follows [docs/CONVENTIONS.md](docs/CONVENTIONS.md); day-to-day operations are in
[docs/RUNBOOK.md](docs/RUNBOOK.md).

## Repository layout | 仓库结构

| Path | Content |
|---|---|
| `ansible.cfg`, `Makefile`, `requirements*.txt`, `requirements.yml` | control-node configuration and dependencies |
| `inventories/production/servers-config.yml` | single source of truth for hosts and groups |
| `inventories/production/hosts.yml` | generated inventory (never edit by hand) |
| `inventories/production/group_vars/` | operator-facing global knobs (`all/main.yml`) |
| `inventories/development/hosts.yml` | local `k8s_local` group for the kind lab |
| `playbooks/provision/`, `playbooks/platform/`, `playbooks/maintenance/` | playbooks (table below) |
| `roles/` | one role per service, each with a `README.md` and the lifecycle contract |
| `observability/` | Grafana dashboards and Prometheus alert rules provisioned by the roles |
| `scripts/anixops.sh` | the CLI behind every `make` target |
| `tools/` | inventory generator and operator helpers (see `tools/README.md`) |
| `tests/` | repository tests (pytest) and the localhost integration suite |
| `.github/workflows/`, `.github/actions/` | CI gates and deployment workflows |
| `docs/` | operational documentation |

## Getting started | 快速开始

```bash
git clone https://github.com/AnixOps/AnixOps-ansible.git && cd AnixOps-ansible
scripts/anixops.sh setup --dev        # ./venv + requirements + Galaxy collections
. venv/bin/activate
cp .env.example .env                  # host addresses (<HOST>_V4_SSH), ANSIBLE_USER, secrets
make doctor                           # tools, .env, inventory parsing and drift, collections
make ping
make deploy-dry-run                   # site.yml with --check --diff
make deploy                           # asks for confirmation
```

The step-by-step version, including SSH keys and adding a server, is in
[docs/QUICKSTART.md](docs/QUICKSTART.md).

## Inventory | 主机清单

`inventories/production/servers-config.yml` defines every host, its groups and the environment
variable that holds its SSH address. `make gen-inventory` renders `hosts.yml` from it, and
`python3 tools/generate_inventory.py local --check` (part of `make check` and CI) fails when the two
drift apart. Addresses are never committed: each host gets
`ansible_host: "{{ lookup('env', '<HOST>_V4_SSH') }}"`, filled from `.env` locally and from a
repository secret of the same name in GitHub Actions.

| Host | Address variable | Groups |
|---|---|---|
| `jp-1` | `JP_1_V4_SSH` | `web_servers` |
| `uk-1` | `UK_1_V4_SSH` | `web_servers`, `v2bx_servers` |
| `us-w-1` | `US_W_1_V4_SSH` | `web_servers`, `v2board_servers` |
| `sg-1` | `SG_1_V4_SSH` | `proxy_servers` |
| `hk-1` | `HK_1_V4_SSH` | `proxy_servers` |
| `uk-2` | `UK_2_V4_SSH` | `proxy_servers`, `v2bx_servers` |
| `fr-1` | `FR_1_V4_SSH` | `dev_servers`, `dev` |
| `pl-1` | `PL_1_V4_SSH` | `observability`, `v2board_servers`, `postgres_servers`, `k8s_control_plane`, `k8s_test` |

`k8s_servers` (production k3s) is intentionally empty. The node platform host lives in its own
inventory, `inventories/production/node-platform.actions.yml` (`ANIXOPS_NODE_PLATFORM_1_V4_SSH`).

## Playbooks | Playbook 一览

| Playbook | Hosts | Tags | Purpose |
|---|---|---|---|
| `playbooks/provision/site.yml` | per play (all, `web_servers`, `observability`, `postgres_servers`, `v2board_servers`, `v2bx_servers`) | `common`, `node_exporter`, `promtail`, `firewall`, `nginx`, `prometheus`, `loki`, `grafana`, `postgresql`, `v2board`, `v2bx`, `speedtest`, `health` | full deployment; one play and one tag per service, health check at the end |
| `playbooks/provision/quick-setup.yml` | all | `common`, `node_exporter`, `promtail`, `firewall`, `health` | bootstrap new servers with the base stack |
| `playbooks/provision/web-servers.yml` | `web_servers` | `nginx` | Nginx only, verifies `/health` |
| `playbooks/provision/node-platform.yml` | `anixops_node_platform_servers` | `node_platform` | node platform compose stack behind the Nginx edge |
| `playbooks/platform/k3s.yml` | `k8s_servers` | `k3s`, `k3s_preflight`, `k3s_provision`, `k3s_verify` | production k3s cluster |
| `playbooks/platform/k3s-test.yml` | `k8s_test` | `k3s_test`, `k3s_test_provision`, `k3s_test_kubeconfig` | remote k3s test cluster on pl-1 |
| `playbooks/platform/kind.yml` | `k8s_local` (`inventories/development/hosts.yml`) | `kind` | local kind cluster |
| `playbooks/maintenance/health-check.yml` | all | `health` | read-only health verification (the single health playbook) |
| `playbooks/maintenance/firewall-setup.yml` | all | `firewall` | lockout-proof firewall and monitoring whitelist |
| `playbooks/maintenance/security-patch.yml` | `all:!localhost`, then `localhost` | `security_patch`, `report` | Trivy scan, OS patching, report for the backlog issue |
| `playbooks/maintenance/rollback.yml` | `rollback_hosts` (default all; one host unless `rollback_confirm_all=true`) | `rollback` | restore configuration files from native backups |
| `playbooks/maintenance/lifecycle.yml` | `lifecycle_target_hosts` (default all) | `lifecycle` plus one action: `status`, `deploy`, `rollback`, `cleanup` | versioned deploy, rollback, status and cleanup of one role |
| `playbooks/maintenance/ssh-config-force-apply.yml` | all | `ssh` | re-apply sshd configuration and restart sshd, one host at a time |
| `playbooks/maintenance/fix-docker.yml` | all (Debian family) | `docker` | repair conflicting Docker apt sources |
| `playbooks/maintenance/emergency-cleanup.yml` | all | `legacy_cleanup` | legacy: stop retired network agents |
| `tests/integration/localhost-converge.yml` | `localhost` | `integration` | CI integration converge (common, node_exporter, promtail, nginx, firewall) |
| `tests/integration/localhost-verify.yml` | `localhost` | `integration` | CI integration verification of services and endpoints |

Production plays run `serial: "30%"` with `max_fail_percentage: 25`; SSH, rollback, lifecycle and
Kubernetes plays run `serial: 1` with `max_fail_percentage: 0`.

## Commands | 命令速查

`make` targets delegate to `scripts/anixops.sh`, so both behave the same. Production-changing
commands ask for confirmation unless `--yes` (`ANIXOPS_FLAGS=--yes`) is given. Make variables:
`INVENTORY`, `ANSIBLE_ARGS` (appended to `ansible-playbook`), `ANIXOPS_FLAGS` (CLI options such as
`--limit`, `--yes`, `-vv`), `ROLE`, `VERSION`.

| `make` target | CLI command | What it does |
|---|---|---|
| `make help` | `scripts/anixops.sh --help` | list targets / commands |
| `make doctor` | `doctor` | check tools, `.env`, inventory parsing and drift, collections |
| `make install` / `make install-dev` | `setup` / `setup --dev` | install requirements and collections (`setup` also creates `./venv`; `install-dev` also installs the pre-commit hooks) |
| `make lint` | `lint` | yamllint + ansible-lint (offline, production profile) |
| `make syntax` | `syntax` | `--syntax-check` of every playbook |
| `make test` | `test` | `python3 -m pytest -q tests` |
| `make check-inventory` | - | inventory drift check and parse |
| `make check` | - | lint + syntax + test + check-inventory |
| `make encoding-check` | - | fail on UTF-8 BOMs or GBK mojibake |
| `make backup-coverage` | - | `/etc` templates must use `backup: true` |
| `make pre-commit` | - | every pre-commit hook on the whole repository |
| `make ping` | `ping` | `ansible.builtin.ping` all hosts (or `--limit`) |
| `make list-hosts` | `list-hosts` | inventory graph |
| `make deploy` | `deploy` | `provision/site.yml` |
| `make deploy-dry-run` | `deploy --dry-run` | `site.yml` with `--check --diff` |
| `make quick-setup` | `quick-setup` | `provision/quick-setup.yml` |
| `make deploy-web` | `deploy-web` | `provision/web-servers.yml` |
| `make health-check` | `health-check` | `maintenance/health-check.yml` |
| `make firewall-setup` | `firewall` | `maintenance/firewall-setup.yml` |
| `make security-patch` | `security-patch` | `maintenance/security-patch.yml` |
| `make security-scan-only` | `security-patch --scan-only` | scan and report, no updates |
| `make rollback ROLE=<role> [VERSION=<ver>]` | `rollback <role> [ver]` | `lifecycle.yml --tags rollback` |
| `make status ROLE=<role>` | `status <role>` | `lifecycle.yml --tags status` |
| `make gen-inventory` | `gen-inventory` | regenerate `hosts.yml` (shows a diff, asks first) |
| `make clean` | - | remove caches, logs and the fact cache |

CLI-only commands: `version`, `facts <host>`, `deploy-node-platform` (pass
`-i inventories/production/node-platform.actions.yml`), `fix-docker`,
`ssh-force-apply` (double confirmation), `rollback-files <role>` (`rollback.yml`,
`--timestamp`, `--dry-run`), `cleanup-role <role>` (`--keep-backups N`, typed confirmation),
`deploy-local` (kind), `deploy-remote-test` (`k3s-test.yml`), `deploy-production-k3s` (`k3s.yml`,
typed confirmation), `cleanup-local`, `status-local`. Common options: `-i/--inventory`,
`-l/--limit`, `-t/--tags`, `--skip-tags`, `-n/--dry-run`, `-e/--extra-vars`, `-v`, `-y/--yes`,
`--vault-password-file`, `--ask-vault-pass`, `--env-file`, `--no-env`, `--log-dir`; everything after
`--` goes to `ansible-playbook` unchanged. Logs are written to `.ansible/logs/`.

```bash
scripts/anixops.sh deploy --dry-run --tags nginx --limit web_servers
scripts/anixops.sh security-patch --scan-only --limit jp-1
scripts/anixops.sh rollback-files nginx --timestamp 2026-10-24@14 --dry-run --limit jp-1
make deploy ANSIBLE_ARGS="--tags prometheus,loki,grafana --limit observability"
```

## GitHub Actions | 工作流

| Workflow | Trigger | Purpose |
|---|---|---|
| `ansible-ci.yml` (Ansible CI) | pull request and push to `main`, manual | lint, unit tests, shellcheck, inventory drift, syntax check, localhost integration converge/verify/idempotency |
| `security-scan.yml` | pull request (`main`, `staging`), push to `main`, weekly, manual | TruffleHog, pip-audit, tracked-key check, `ignore_errors` policy |
| `deploy.yml` (Deploy) | manual, tag push `v*` | run a playbook against a group; release deploy |
| `lifecycle.yml` (Lifecycle Management) | manual | `status`, `deploy`, `rollback`, `cleanup` of one role |
| `weekly-security-patch.yml` | Monday 04:00 UTC, manual | security patch run and backlog issue |
| `node-platform-deploy.yml` (Deploy AnixOps Node Platform) | manual | node platform stack |
| `reusable-lint.yml` | called by CI and the tag deploy | yamllint, ansible-lint, backup coverage, encoding guard |

**Deploy workflow inputs:** `playbook`, `target_group`, `limit_hosts` (comma-separated hosts that
must belong to `target_group`), `tags` (comma-separated play tags), `dry_run`, `verbosity`
(`v`, `vv`, `vvv`) and `confirm` (type `deploy` to confirm a real deploy to `target_group=all`).
A health check runs on the same limit after every real deploy.

**Tag-push deploy matrix:** pushing a `v*` tag runs the lint gate, then `site.yml` once per play
tag in this order, one job at a time (`max-parallel: 1`, `fail-fast: false`): `common`,
`node_exporter`, `promtail`, `firewall`, `nginx`, `prometheus`, `loki`, `grafana`, `postgresql`,
`v2board`, `v2bx`, `speedtest`; a fleet-wide health check job follows.

**Weekly security patch inputs:** `target_group`, `apply_updates`, `allow_reboot`
(`inventory` keeps the per-host/group `security_patch_allow_reboot`, `true`/`false` override it).
**Lifecycle inputs:** `action`, `role`, `version` (`prev`, `initial`, `vYYYYMMDDTHHMMSS`),
`target_group` (group or single host), `force` (required for rollback/cleanup on more than one host),
`keep_backups`.

Secrets and environments are described in [docs/GITHUB_ACTIONS_SETUP.md](docs/GITHUB_ACTIONS_SETUP.md)
and [docs/GITHUB_SECRETS_REFERENCE.md](docs/GITHUB_SECRETS_REFERENCE.md).

## Validation | 校验

```bash
make check             # lint + syntax + pytest + inventory drift
make encoding-check
make backup-coverage
sudo -E env "PATH=$PATH" "HOME=$HOME" \
  ansible-playbook -i localhost, -c local tests/integration/localhost-converge.yml   # disposable host only
```

## Documentation | 文档

| Document | Content |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | first deployment step by step |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | deploy, verify, rollback, incident response, approval levels |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | engineering rules and known pitfalls |
| [docs/GITHUB_ACTIONS_SETUP.md](docs/GITHUB_ACTIONS_SETUP.md) | workflows, environments, how CI reaches the fleet |
| [docs/GITHUB_SECRETS_REFERENCE.md](docs/GITHUB_SECRETS_REFERENCE.md) | every secret / environment variable |
| [docs/SECRETS_MANAGEMENT.md](docs/SECRETS_MANAGEMENT.md) | handling secrets locally and in CI |
| [docs/SSH_KEY_MANAGEMENT.md](docs/SSH_KEY_MANAGEMENT.md) | SSH key options for operators and CI |
| [docs/OBSERVABILITY_SETUP.md](docs/OBSERVABILITY_SETUP.md) | Prometheus, Loki, Grafana |
| [docs/SECURITY_PATCHING.md](docs/SECURITY_PATCHING.md) | weekly security patch workflow |
| [docs/ANIXOPS_NODE_PLATFORM.md](docs/ANIXOPS_NODE_PLATFORM.md) | node platform stack |
| [CONTRIBUTING.md](CONTRIBUTING.md) | how to contribute |
| [CHANGELOG.md](CHANGELOG.md) | release notes |

## License

MIT License
