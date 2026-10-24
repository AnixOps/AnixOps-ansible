# Operations Runbook | 运维手册

How to change the production fleet safely: deploy, verify, roll back and handle incidents.
Engineering rules for the code itself are in [CONVENTIONS.md](CONVENTIONS.md); the weekly
patch procedure is in [SECURITY_PATCHING.md](SECURITY_PATCHING.md).

Every command below runs from the repository root with the virtualenv active
(`. venv/bin/activate`) and a filled-in `.env` (see [QUICKSTART.md](QUICKSTART.md)).
`make <target>` is a thin wrapper around `scripts/anixops.sh <command>`; both print the exact
`ansible-playbook` command before running it and write a log to
`.ansible/logs/<YYYYMMDD-HHMMSS>-<command>[-<role>].log`.

## 1. Change approval levels | 变更审批级别

| Level | Scope | Requirement |
|---|---|---|
| LOW | single host, local test, read-only (`health-check`, `status`, `--check --diff`) | run directly |
| MEDIUM | fewer than five hosts, reversible configuration | `serial: "30%"`, `backup: true`, health check afterwards |
| HIGH | whole fleet or core services (SSH, firewall, databases) | MEDIUM plus `max_fail_percentage: 25`, a written rollback plan (`rollback.yml` / `lifecycle.yml --tags rollback`) and a dry run (`--check --diff`) first |

Fleet-wide rollback or cleanup refuses to run on more than one host unless
`-e rollback_confirm_all=true` (rollback.yml) or `-e lifecycle_confirm_all=true` (lifecycle.yml)
is passed explicitly. The CLI commands (`rollback`, `rollback-files`, `cleanup-role`) add the flag
themselves and rely on their own confirmation prompt instead (skipped with `--yes`); the Lifecycle
Management workflow passes `lifecycle_confirm_all=true` only when `force=true`.

## 2. Before any change | 变更前检查

1. The commit you deploy is green: `make check` (lint, syntax, tests, inventory drift) and the
   `Ansible CI` workflow on GitHub.
2. Tooling and inventory are sane: `make doctor`.
3. Targets answer: `make ping` (narrow with `ANIXOPS_FLAGS="--limit web_servers"`).
4. Dry run the exact change:

   ```bash
   make deploy-dry-run ANSIBLE_ARGS="--tags nginx --limit web_servers"
   # equivalent: scripts/anixops.sh deploy --dry-run --tags nginx --limit web_servers
   ```

5. For SSH or firewall changes keep a second SSH session open and know how to reach the
   provider console of every targeted host.

## 3. Deploy | 部署

### 3.1 From a workstation | 本地执行

| Goal | Command |
|---|---|
| Full deployment (`playbooks/provision/site.yml`) | `make deploy` |
| One service on one group | `make deploy ANSIBLE_ARGS="--tags nginx --limit web_servers"` |
| Bootstrap new hosts (common, node_exporter, promtail, firewall, health) | `make quick-setup ANSIBLE_ARGS="--limit <host>"` |
| Web tier only (`web-servers.yml`) | `make deploy-web` |
| Node platform (`node-platform.yml`, own inventory) | `scripts/anixops.sh deploy-node-platform -i inventories/production/node-platform.actions.yml` |
| Firewall rules and monitoring whitelist | `make firewall-setup` |
| Skip the confirmation prompt (CI-like) | append `ANIXOPS_FLAGS=--yes` |

`site.yml` has exactly one tag per service play: `common`, `node_exporter`, `promtail`,
`firewall`, `nginx`, `prometheus`, `loki`, `grafana`, `postgresql`, `v2board`, `v2bx`,
`speedtest`, `health`. Preflight assertions are tagged `always`; the post-deploy health check
is the `health` play.

**Lifecycle-tracked deploy.** A deploy through `site.yml` leaves only the native backup files
next to each templated file (see section 5.1). To record a versioned snapshot that
`lifecycle.yml --tags rollback` can return to, deploy the role through the lifecycle playbook:

```bash
ansible-playbook playbooks/maintenance/lifecycle.yml \
  -e lifecycle_target_role=nginx --tags deploy --limit jp-1
```

This runs `pre_deploy` (snapshot to `/var/backups/<role>/<YYYYMMDDTHHMMSS>/pre/`), the role, and
`post_deploy` (snapshot `post/`, health verification, state and history under
`/var/lib/anixops/state/`).

### 3.2 From GitHub Actions | 通过 GitHub Actions

**Manual deploy** (`Deploy` workflow, `.github/workflows/deploy.yml`, environment `NodeX`):

| Input | Meaning |
|---|---|
| `playbook` | `provision/site.yml`, `provision/quick-setup.yml`, `provision/web-servers.yml`, `maintenance/health-check.yml`, `maintenance/firewall-setup.yml`, `maintenance/lifecycle.yml`, `maintenance/emergency-cleanup.yml` |
| `target_group` | `all`, `web_servers`, `proxy_servers`, `observability`, `dev_servers`, `v2bx_servers`, `v2board_servers`, `postgres_servers` |
| `limit_hosts` | optional comma-separated host names; each must be a member of `target_group` |
| `tags` | optional comma-separated play tags, e.g. `nginx,firewall` |
| `dry_run` | `--check --diff`, nothing is changed |
| `verbosity` | `v`, `vv` or `vvv` |
| `confirm` | must be `deploy` for a real (non dry-run) deploy to `target_group=all` |

The job syntax-checks the playbook, pings the limit, runs the playbook and then
`maintenance/health-check.yml` on the same limit (skipped for dry runs and for the health-check
playbook itself).

**Release deploy.** Pushing a tag that matches `v*` runs the lint gate, then one job per
`site.yml` play tag in dependency order (`common`, `node_exporter`, `promtail`, `firewall`,
`nginx`, `prometheus`, `loki`, `grafana`, `postgresql`, `v2board`, `v2bx`, `speedtest`) with
`max-parallel: 1` and `fail-fast: false`, and finally a fleet-wide health check job.

`deploy.yml`, `lifecycle.yml` and `weekly-security-patch.yml` share the concurrency group
`deploy-NodeX-<target_group>`: a second run for the same target waits, and a running job is never
cancelled automatically.

## 4. Verify | 验证

```bash
make health-check                                        # every host, read-only
make health-check ANSIBLE_ARGS="--limit web_servers"     # one group
ansible-playbook playbooks/maintenance/health-check.yml -e health_check_report_path=./health-report.json
make status ROLE=nginx                                   # lifecycle version, service state, history
```

`playbooks/maintenance/health-check.yml` is the single health playbook (`site.yml` and
`quick-setup.yml` import it). Per host it checks uptime, load, root filesystem and memory usage,
the systemd units of the host's groups, and HTTP 200 from the local endpoints below. A host fails
when a unit is not running, an endpoint does not answer 200, root filesystem usage reaches
`health_disk_warn_percent` (85) or memory usage reaches `health_mem_warn_percent` (90).
`-e health_check_soft=true` reports failures without failing the play.

| Service | Unit checked | HTTP endpoint checked (on the host) | Hosts |
|---|---|---|---|
| SSH, time sync | `ssh` / `sshd`, `chrony` / `chronyd` | - | all |
| node_exporter | `node_exporter` | `http://127.0.0.1:9100/metrics` | all |
| Promtail | `promtail` | `http://127.0.0.1:9080/ready` | all |
| Nginx | `nginx` | `http://127.0.0.1:80/health` | `web_servers` |
| Prometheus | `prometheus` | `http://127.0.0.1:9090/-/healthy` | `observability` |
| Loki | `loki` | `http://127.0.0.1:3100/ready` | `observability` |
| Grafana | `grafana-server` | `http://127.0.0.1:3000/api/health` | `observability` |
| PostgreSQL | `postgresql` | - | `postgres_servers` |
| V2board | `v2board` (when the unit exists) | - | `v2board_servers` |
| V2bX | `V2bX` | - | `v2bx_servers` |

The lifecycle hooks probe the per-role contract instead (`<role>_service_name`, `<role>_port`,
`<role>_health_url`), e.g. V2board's `http://127.0.0.1:8080/api/v2/status` with the default
`V2BOARD_API_PORT`.

## 5. Roll back | 回滚

Pick the mechanism that matches what you need to undo:

| Situation | Mechanism | Entry point |
|---|---|---|
| A config file written by any role (including `site.yml` deploys) is wrong | file-level rollback from native backups | `playbooks/maintenance/rollback.yml` (`scripts/anixops.sh rollback-files`) |
| A deployment made through `lifecycle.yml --tags deploy` must be undone as a whole | version rollback from lifecycle snapshots | `playbooks/maintenance/lifecycle.yml --tags rollback` (`make rollback`) |
| Node platform application release | redeploy the previous tag/sha | `ANIXOPS_NODE_PLATFORM_REPO_VERSION`, see [ANIXOPS_NODE_PLATFORM.md](ANIXOPS_NODE_PLATFORM.md) |
| V2board container image | redeploy with the previous image tag | set `V2BOARD_DOCKER_TAG`, then `make deploy ANSIBLE_ARGS="--tags v2board --limit <host>"` |
| k3s test/production cluster | uninstall | `/usr/local/bin/k3s-uninstall.sh` on the server |
| Local kind cluster | delete | `scripts/anixops.sh cleanup-local` |

### 5.1 File-level rollback (`rollback.yml`) | 文件级回滚

Every file a role writes under `/etc` uses `backup: true`, which leaves a copy next to it:

```text
native  <file>.<pid>.<YYYY-MM-DD@HH:MM:SS>~      e.g. /etc/nginx/nginx.conf.48213.2026-10-24@14:03:11~
legacy  <file>.backup.<anything>                 (older ssh-config-force-apply.yml runs)
```

For every original file the playbook picks the newest backup by mtime, or the newest whose name
contains `rollback_timestamp` (any substring: pid, date or time). Files without a matching backup
are skipped, never restored from a different version.

```bash
# 1. See what would be restored (no changes)
scripts/anixops.sh rollback-files nginx --limit jp-1 --dry-run
ansible-playbook playbooks/maintenance/rollback.yml -e rollback_role=nginx -e rollback_dry_run=true --limit jp-1

# 2. Restore the newest backups, or those from a specific run
ansible-playbook playbooks/maintenance/rollback.yml -e rollback_role=nginx --limit jp-1
ansible-playbook playbooks/maintenance/rollback.yml -e rollback_role=nginx \
  -e rollback_timestamp=2026-10-24@14:03 --limit jp-1

# 3. More than one host needs an explicit confirmation
ansible-playbook playbooks/maintenance/rollback.yml -e rollback_role=nginx \
  --limit web_servers -e rollback_confirm_all=true
```

Roles known to the playbook: `nginx`, `common`, `prometheus`, `loki`, `grafana`,
`node_exporter`, `promtail`, `firewall`, `acme_ssl`, `postgresql`, `v2board`, `v2bx`.
Safety net: the current file is first saved as `<file>.pre-rollback.<epoch>`, the restored
configuration is validated (`nginx -t`, `sshd -t`, `promtool`, ...) and reverted from that
snapshot when validation fails; services restart only when a file actually changed, then the
role's health URL is polled. Plays run with `serial: 1` and `max_fail_percentage: 0`.

### 5.2 Version rollback (`lifecycle.yml`) | 版本回滚

Restores a whole snapshot recorded by a lifecycle deploy (section 3.1) to the original paths in its
manifest, validates, restarts the service and verifies health.

```bash
make rollback ROLE=nginx ANIXOPS_FLAGS="--limit jp-1"                 # previous version
make rollback ROLE=nginx VERSION=v20261024T140311 ANIXOPS_FLAGS="--limit jp-1"

ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx \
  -e lifecycle_version=prev --tags rollback --limit jp-1
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx \
  -e lifecycle_version=prev -e lifecycle_dry_run=true --tags rollback --limit jp-1   # plan only
```

| `lifecycle_version` | Restores |
|---|---|
| `prev` (default) | the configuration of the deployment before the current one; repeating `prev` walks further back |
| `initial` | the configuration from before the first recorded deployment |
| `v<YYYYMMDDTHHMMSS>` | the configuration right after that deployment |
| `-e lifecycle_restore_from=<dir>` | a specific snapshot directory, e.g. the `/var/backups/<role>/<ts>-pre-rollback` safety snapshot taken by the previous rollback (undo a rollback) |

More than one host in the play needs `-e lifecycle_confirm_all=true`; `scripts/anixops.sh rollback`
adds it after its confirmation prompt. In GitHub Actions use the **Lifecycle Management** workflow
(`action=rollback`, `role`, `version`, `target_group`); `force=true` is required for
`target_group=all` and for any multi-host group, and is what passes `lifecycle_confirm_all=true`.
The workflow runs the health check afterwards.

### 5.3 Removing a service | 移除服务

```bash
scripts/anixops.sh cleanup-role loki --limit jp-1 --keep-backups 5
```

Typed confirmation; stops and disables the unit, removes the role's packages, archives its
configuration directories (kept unless `-e cleanup_keep_data=false`) and keeps the newest
`--keep-backups` snapshot versions. `common` can never be cleaned up.

## 6. Incident response | 故障处理

1. **Assess.** Which hosts, which service, since when? Run
   `make health-check ANSIBLE_ARGS="--limit <host>"` and read the failed checks. Check whether a
   deploy, lifecycle or security-patch workflow ran recently (Actions tab, job summaries).
2. **Stop further change.** Cancel a running workflow from the Actions tab if it is making things
   worse (concurrency never cancels a running deploy on its own). Do not start a second deploy to
   the same target while one is running.
3. **Diagnose on the host.**

   ```bash
   systemctl status <unit> --no-pager
   journalctl -u <unit> -n 200 --no-pager
   nginx -t                                              # Nginx
   sshd -t                                               # SSH
   /usr/local/bin/promtool check config /etc/prometheus/prometheus.yml
   /usr/local/bin/loki -config.file=/etc/loki/loki-config.yml -verify-config
   df -h / && free -m
   ```

4. **Recover.** Prefer the smallest reversible step: a file-level rollback of the affected role
   (5.1), a lifecycle rollback (5.2) when the change was a lifecycle deploy, or re-running the last
   known-good commit for the affected tag only (`--tags <service> --limit <host>`).
5. **Verify.** `make health-check` for the affected hosts; for observability, open Grafana and
   check that data arrives again.
6. **Record.** Open an issue with the timeline, the commands that were run and the log files from
   `.ansible/logs/`. Fix the root cause in the repository, never only on the host: the next deploy
   would overwrite a hand edit.

### Common situations | 常见场景

| Symptom | First steps |
|---|---|
| Locked out after an SSH change | Use the provider console; `sshd -t`; restore with `rollback.yml -e rollback_role=common --limit <host>`. `ssh-config-force-apply.yml` runs `serial: 1` and stops at the first failure. |
| Locked out after a firewall change | Provider console; `ufw status numbered`, `ufw disable` (Debian) or `systemctl stop firewalld` (RedHat). The role always allows the SSH port before enabling UFW. |
| Nginx fails after a deploy | The role validates with `nginx -t`, probes `nginx_health_url` and restores the backups of the same run on failure; read the role's failure message, then `journalctl -u nginx`. |
| A service role failed health verification | Roles restore the backup produced in the same run (`<register>.backup_file`) and restart the service before failing; check the unit journal, then roll back (5.1). |
| Disk filling up on the observability host | Loki keeps 30 days (`loki_retention_period`), Prometheus 15 days (`prometheus_retention_time`); lower them in the inventory and redeploy `--tags loki` / `--tags prometheus`. |
| `apt` reports conflicting `Signed-By` for Docker | `scripts/anixops.sh fix-docker --limit <host>` (`playbooks/maintenance/fix-docker.yml`). |
| Host unreachable in GitHub Actions | Check the `<HOST>_V4_SSH` secret and `SSH_PRIVATE_KEY`; the inventory reads the address from that variable. |
| Security patch backlog issue opened | Follow the runbook in [SECURITY_PATCHING.md](SECURITY_PATCHING.md). |
| Inventory drift gate fails | Edit `inventories/production/servers-config.yml`, run `make gen-inventory`, commit both files. |
