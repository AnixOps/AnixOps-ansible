# Engineering Conventions | 工程规范

Every file in this repository must satisfy the rules below. They are enforced by
`ansible-lint` (production profile, empty skip list), `yamllint`, the repository tests under
`tests/` (about 4,200 parametrised checks that run in a few seconds) and the CI gates in
`.github/workflows/`. Run `make check` before every commit (plus `make encoding-check` and
`make backup-coverage` when you touch text encodings or `/etc` templates). Operational procedures
(deploy, verify, rollback, incidents) live in [RUNBOOK.md](RUNBOOK.md).

本仓库的所有文件都必须满足以下规范。规范由 `ansible-lint`（production 档、空 skip 列表）、
`yamllint`、`tests/` 下的仓库测试以及 CI 门禁强制执行。提交前请运行 `make check`。

## 1. Files and encoding | 文件与编码

- Plain UTF-8 **without BOM**, LF line endings, exactly one trailing newline, no tabs in YAML,
  no trailing whitespace outside Markdown.
- No mojibake. Comments are English first, with an optional Chinese part after ` | `
  (`Deploy Nginx | 部署 Nginx`). Never leave `?` replacement characters behind.
- Shell scripts start with `#!/usr/bin/env bash`, are executable, use `set -Eeuo pipefail` and
  pass `shellcheck -x -S warning`.

## 2. Ansible tasks | Ansible 任务

- Fully qualified collection names for every module (`ansible.builtin.*`, `ansible.posix.*`,
  `community.general.*`, `community.docker.*`, `kubernetes.core.*`).
- Booleans are `true`/`false` only. File modes are quoted octal strings (`mode: "0644"`).
- Every task is named, starts with an uppercase letter and does not start with Jinja.
- `command`/`shell` always declare `changed_when` (or `creates`/`removes`); prefer the `argv:`
  form; shell pipelines use `set -o pipefail` with `executable: /bin/bash`.
- **No `ignore_errors`**. Use `failed_when: false` for read-only probes and `block`/`rescue`/`always`
  for recoverable failures. `|| true` is forbidden in command modules.
- Every network operation (`get_url`, `uri`, `apt`, `dnf`, `package`, `apt_repository`,
  `deb822_repository`, `pip`, `docker_image`, `git`) carries `retries`, `delay` and `until`.
  Release-binary downloads support an optional `<role>_checksum` variable.
- Secrets (`*password*`, `*token*`, `*secret*`, `*api_key*`, `*private_key*`) are handled with
  `no_log: true` and never printed by `debug`.
- Loops over dictionaries use `loop_control: label:`.

## 3. Configuration files and services | 配置文件与服务

- Every file written under `/etc` has `backup: true`, explicit `owner`, `group` and `mode`, and
  `validate:` whenever the service offers a syntax checker (`sshd -t -f %s`, `nginx -t -c %s`,
  `promtool check config %s`, `loki -verify-config`). Deliberate exceptions live in
  `scripts/backup-coverage-allowlist.txt` with a documented reason.
- Roll-out pattern for a service role: template configuration → `meta: flush_handlers` → verify
  health (`uri`/`wait_for` with retries) → on failure the `rescue` restores the backup produced in
  this run (`<register>.backup_file`), restarts the service and fails with a clear message.
- systemd units written by a role: `After=`/`Wants=network-online.target`, `Restart=on-failure`,
  `RestartSec=`, `StartLimitIntervalSec`/`StartLimitBurst`, `NoNewPrivileges=true`,
  `PrivateTmp=true`, `ProtectSystem=` with explicit `ReadWritePaths`, `ProtectHome=true`.
  Unit writes notify `Reload systemd`.
- Handler names: `Restart <service>`, `Reload <service>`, `Reload systemd`.
- Ansible's native backup files are named `<file>.<pid>.<YYYY-MM-DD@HH:MM:SS>~`;
  `playbooks/maintenance/rollback.yml` understands that format and the legacy `<file>.backup.*`.

## 4. Variables | 变量

- Inside a role, every variable in `defaults/`/`vars/`, every `register:` and every `set_fact`
  key is prefixed with `<role_name>_`.
- Operator-facing global knobs stay in `inventories/production/group_vars/all/main.yml`
  (`timezone`, `locale`, `ssh_port`, `ssh_allow_root`, `ssh_password_authentication`,
  `ntp_servers`, `common_packages`, `admin_users`, `security`, `sysctl_config`,
  `firewall_enabled`, `firewall_public_ports`, `firewall_restricted_ports`,
  `monitoring_whitelist`, `proxy_additional_ports`, `firewall_default_incoming_policy`,
  `prometheus`/`loki`/`grafana` dictionaries). Roles consume them through prefixed defaults with
  fallbacks, e.g. `common_timezone: "{{ timezone | default('Asia/Shanghai') }}"`.
- Host metadata emitted by the inventory generator for every host: `server_alias`, `location`,
  `server_environment`, `description`. Consumers read them via `hostvars[host].server_alias | default(host)`.

## 5. Lifecycle contract | 生命周期契约

Every service role defines these defaults so `roles/lifecycle` and `playbooks/maintenance/rollback.yml`
can manage it generically:

| Variable | Meaning |
|---|---|
| `<role>_service_name` | systemd unit (`""` = no unit, e.g. speedtest) |
| `<role>_port` | main TCP port (`0` = none) |
| `<role>_health_url` | HTTP health endpoint (`""` = none; relative paths are prefixed with `http://localhost:<port>`) |
| `<role>_backup_files` | configuration files written with `backup: true` |
| `<role>_config_dirs` | directories archived or removed on cleanup |
| `<role>_packages` | packages the role installs |
| `<role>_cleanup_packages` | packages cleanup may remove (defaults to `<role>_packages`; `common` is never cleaned up) |

## 6. Playbooks | Playbook

- Every play has `name`, `hosts`, `become`, `gather_facts`, `serial`, `max_fail_percentage`,
  `any_errors_fatal: false` and `tags`.
- Batch safety: production plays use `serial: "30%"` and `max_fail_percentage: 25`; SSH, rollback,
  lifecycle and Kubernetes plays use `serial: 1` and `max_fail_percentage: 0`.
- `playbooks/provision/site.yml` play tags: `common`, `node_exporter`, `promtail`, `firewall`,
  `nginx`, `prometheus`, `loki`, `grafana`, `postgresql`, `v2board`, `v2bx`, `speedtest`, `health`.
- `playbooks/maintenance/health-check.yml` is the single health playbook; `site.yml` and
  `quick-setup.yml` import it.
- The inventory is generated: edit `inventories/production/servers-config.yml`, run
  `make gen-inventory`, and keep `python3 tools/generate_inventory.py local --check` green.

## 7. Change approval levels | 变更审批级别

| Level | Scope | Requirement |
|---|---|---|
| LOW | single host, local test, read-only | run directly |
| MEDIUM | fewer than five hosts, reversible configuration | `serial: "30%"`, `backup: true`, health check |
| HIGH | whole fleet or core services (SSH, firewall, databases) | MEDIUM plus `max_fail_percentage: 25`, a rollback plan (`rollback.yml` / `lifecycle.yml --tags rollback`) and a dry run (`--check --diff`) first |

Fleet-wide rollback or cleanup refuses to run on more than one host unless
`rollback_confirm_all=true` / `lifecycle_confirm_all=true` is passed explicitly.

## 8. CI gates | CI 门禁

`ansible-ci.yml` runs on every pull request: yamllint, ansible-lint, backup coverage, encoding guard,
unit tests, inventory drift, syntax check of every playbook and (when present) the localhost
integration converge/verify/idempotency run. `security-scan.yml` adds secret scanning, dependency
audit and the `ignore_errors` policy check. Deploy-type workflows share a concurrency group per
environment so two deployments never overlap.

## 9. Known pitfalls | 已知陷阱

Lessons from the hardening programme that are easy to get wrong again.

- **Stale facts.** `ansible.cfg` uses `gathering = smart` with a JSON fact cache that lives for one
  hour (`fact_caching_timeout = 3600`), so `ansible_date_time` can be up to an hour old. Anything that
  needs a fresh timestamp (backup names, version labels) uses the controller clock, `now()`, pinned
  once with `set_fact` (see `roles/lifecycle/tasks/main.yml` and `playbooks/maintenance/rollback.yml`).
  Names keyed on `ansible_date_time.epoch` collide for the same reason. `make clean` drops the cache.
- **systemd status probes.** `ansible.builtin.systemd` / `systemd_service` with only `name:` fails
  (`required_one_of`). Read service state with `ansible.builtin.service_facts` or
  `systemctl show` / `systemctl is-active` (`roles/lifecycle/tasks/probe_service.yml`); use the
  systemd modules only for state changes.
- **ansible-lint `kinds` order.** Entries in `.ansible-lint` `kinds` are matched in order, so task-file
  globs (`playbooks/maintenance/security-patch/*.yml`, `roles/*/tasks/**/*.yml`) must come before the
  `playbooks/**/*.yml` playbook glob, otherwise task files are linted as playbooks.
- **Escapes in heredocs.** A `\uXXXX` sequence typed inside a Bash heredoc is written as the literal
  character, and the repository tests then flag it as mojibake or an invisible character. Write such
  files with an editor, or build the character in Python with `chr()` (as `tests/test_repo_hygiene.py`
  does).
- **Backup file names.** Ansible's native `backup: true` files are named
  `<file>.<pid>.<YYYY-MM-DD@HH:MM:SS>~`, not `<file>.backup.*`. `playbooks/maintenance/rollback.yml`
  understands both formats; anything else that searches for backups must as well.
- **Empty environment lookups.** `lookup('env', 'X') | default('y')` returns `''` when `X` is unset,
  because the lookup result is defined. Use `lookup('env', 'X') or 'y'` or `default('y', true)`.
