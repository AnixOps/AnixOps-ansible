# promtail role | promtail 角色

Installs [Grafana Promtail](https://grafana.com/docs/loki/latest/send-data/promtail/) from the official
Loki GitHub release, runs it as a dedicated system user under a hardened systemd unit, ships
`/var/log` files, application logs and the systemd journal to Loki, and verifies `/ready` before the
play continues.

从官方 Loki GitHub Release 安装 Promtail，以专用系统用户运行在加固的 systemd 单元中，将 `/var/log`、应用日志
和 systemd journal 发送到 Loki，并在继续之前验证 `/ready` 端点。

## Behaviour | 行为

`tasks/main.yml` imports four task files; each is tagged so a sub-step can be run on its own.

| Step | File | Tag | What happens |
|---|---|---|---|
| 1 | `install.yml` | `promtail_install` | `promtail --version` is parsed; the release zip is downloaded only when the binary is missing or the version differs (upgrades **and** downgrades). `unzip` is installed if needed. `get_url` retries 5x/10s with a 60s timeout and honours `promtail_checksum`. Work happens in an `ansible.builtin.tempfile` directory that is removed in `always`. Binary is installed `root:root 0755`. |
| 2 | `configure.yml` | `promtail_configure` | System group/user (`nologin`, no home) in group `adm` plus `systemd-journal` when that group exists, so log files and the journal are readable. `/etc/promtail` (`root:promtail 0750`) and `/var/lib/promtail` (`promtail:promtail 0750`). Config rendered to `/etc/promtail/config.yml` (`0640`, `backup: true`) and validated with `promtail -config.file=<tmp> -check-syntax` **before** it replaces the live file (skipped automatically when the binary does not list the flag in `-help`). Unit rendered with `backup: true`. |
| 3 | `service.yml` | `promtail_service` | `meta: flush_handlers` first (daemon-reload / restart), then `systemd_service: enabled + started`. |
| 4 | `verify.yml` | `promtail_verify` | `uri` GET on `promtail_health_url` (`/ready`), 6 attempts every 5s. On failure: `journalctl -u promtail -n 50` is shown, config/unit backups created by this run (if any) are restored and the service restarted, then the task fails with a clear message. No `ignore_errors` anywhere. |

`/ready` answers `200 Ready` once at least one scrape target is active (the journal job makes this
immediate). A second run reports `changed=0`.

### Config roll-out pattern | 配置发布模式

validate -> template (with backup) -> `meta: flush_handlers` -> health check with retries -> on
failure restore `<register>.backup_file`, restart, `fail`. The same pattern is used by node_exporter.

### systemd hardening

`NoNewPrivileges`, `ProtectSystem=strict` with `ReadWritePaths=<promtail_positions_dir>`,
`ProtectHome` (toggle `promtail_unit_protect_home`), `PrivateTmp`, `ProtectControlGroups`,
`ProtectKernelModules`, `ProtectKernelTunables`, `Restart=on-failure`, `RestartSec=5s`,
`StartLimitIntervalSec=300`, `StartLimitBurst=5`, `Wants/After=network-online.target`.
If you scrape files under `/home`, set `promtail_unit_protect_home: false`.

### Resilience towards Loki | Loki 不可用时

The client block sets `batchwait: 1s` and `backoff_config` (`min_period: 500ms`, `max_period: 5m`,
`max_retries: 10`): when Loki is down promtail keeps tailing, retries with exponential back-off and
resumes from the positions file after a restart.

## Variables | 变量

All variables live in `defaults/main.yml` and are prefixed `promtail_`, except the two legacy public
knobs `loki_server_url` and `promtail_app_log_dir` which keep working.

| Variable | Default | Purpose |
|---|---|---|
| `promtail_version` | `"2.9.3"` | Release to install. Changing it (up or down) re-installs. |
| `promtail_download_url` | Loki GitHub releases URL | Base URL; the archive name is appended. |
| `promtail_checksum` | `""` | Optional `sha256:<hex>` passed to `get_url` when non-empty. |
| `promtail_arch` | `_target_arch` or derived from `ansible_architecture` | `amd64` / `arm64` archive suffix. |
| `promtail_install_path` | `/usr/local/bin/promtail` | Binary location. |
| `promtail_user` / `promtail_group` | `promtail` | Service account. |
| `promtail_log_groups` | `[adm]` | Supplementary groups for log access; `systemd-journal` is appended when present. |
| `promtail_config_dir` / `promtail_config_path` | `/etc/promtail` / `.../config.yml` | Configuration location. |
| `promtail_positions_dir` / `promtail_positions_file` | `/var/lib/promtail` / `.../positions.yaml` | Tail positions (the only writable path of the unit). |
| `promtail_config_validate` | `true` | Run `-check-syntax` before installing the config. |
| `promtail_port` | `9080` | HTTP port for `/ready`, `/metrics`, `/targets` (restricted in the firewall role). |
| `promtail_listen_address` | `"0.0.0.0"` | HTTP bind address (`http_listen_address`); empty binds all interfaces. |
| `promtail_log_level` | `info` | Promtail server log level. |
| `promtail_extra_args` | `[]` | Extra flags appended to `ExecStart`, e.g. `["-config.expand-env=true"]`. |
| `promtail_unit_protect_home` | `true` | `ProtectHome=` in the unit. |
| `promtail_loki_url` | `loki_server_url` -> env `LOKI_URL` -> `http://localhost:3100` | Loki base URL; `/loki/api/v1/push` is appended, trailing slashes stripped. |
| `promtail_loki_tenant_id` | `""` | `X-Scope-OrgID` for multi-tenant Loki. |
| `promtail_loki_basic_auth_username` / `_password` | `""` | HTTP basic auth towards Loki. The config task runs with `no_log` when a password is set. |
| `promtail_client_batchwait` / `_batchsize` / `_timeout` | `1s` / `1048576` / `10s` | Client batching. |
| `promtail_client_backoff_min_period` / `_max_period` / `_max_retries` | `500ms` / `5m` / `10` | Client back-off while Loki is unreachable. |
| `promtail_external_labels` | `host`, `alias`, `location`, `environment` | Labels on every stream: `inventory_hostname`, `server_alias`, `location`, `server_environment`. Empty values are dropped. |
| `promtail_app_log_dir` | `/var/log/apps` | Directory of the `applications` job (`*.log`). |
| `promtail_scrape_configs` | jobs `system`, `auth`, `syslog`, `applications` | File-based scrape_configs, rendered verbatim with `to_nice_yaml`. Override to replace the default jobs. |
| `promtail_extra_scrape_configs` | `[]` | Additional scrape_configs appended after the defaults (pipeline stages allowed). |
| `promtail_journal_enabled` | `true` | Adds job `journal` (systemd journal, label `unit` from `__journal__systemd_unit`). Needs a promtail build with journal support; the official release binaries have it. Set `false` for custom builds without systemd support. |
| `promtail_journal_max_age` | `12h` | How far back the journal is read on first start. |
| `promtail_verify_retries` / `_delay` | `6` / `5` | Health check attempts and delay in seconds. |
| `promtail_service_name` | `promtail` | Unit name. |
| `promtail_health_url` | `http://127.0.0.1:9080/ready` | Used by `verify.yml` and the lifecycle hooks. Follows `promtail_listen_address` when it is a specific IP. |
| `promtail_backup_files` | config + unit file | Lifecycle contract: files backed up before deploy / restored by rollback. |
| `promtail_config_dirs` | `[/etc/promtail, /var/lib/promtail]` | Lifecycle contract. |
| `promtail_packages` | `[]` | Lifecycle contract (binary install, nothing to purge). |

The global `loki.promtail.*` dict in `inventories/production/group_vars/all/main.yml` is kept for
operators but is **not** read by the role; set `promtail_version` / `promtail_port` explicitly to
override. `_target_arch` from the same file is honoured for the architecture.

Example override:

```yaml
loki_server_url: "https://loki.example.com"
promtail_loki_basic_auth_username: promtail
promtail_loki_basic_auth_password: "{{ vault_promtail_password }}"
promtail_extra_scrape_configs:
  - job_name: nginx
    static_configs:
      - targets: [localhost]
        labels:
          job: nginx
          __path__: /var/log/nginx/*.log
```

## Verification | 验证

```bash
curl -s localhost:9080/ready            # -> Ready
curl -s localhost:9080/targets | head   # active file/journal targets
curl -s localhost:9080/metrics | grep promtail_sent_entries_total
systemctl status promtail --no-pager
journalctl -u promtail -n 50 --no-pager
promtail -config.file=/etc/promtail/config.yml -check-syntax
ansible-playbook playbooks/provision/site.yml --tags promtail
```

## Rollback | 回滚

* Config / unit: the template tasks keep backups next to the live files
  (`config.yml.<pid>.<YYYY-MM-DD@HH:MM:SS>~`, same for the unit). Restore the latest ones with
  `ansible-playbook playbooks/maintenance/rollback.yml -e rollback_role=promtail`, or use the
  lifecycle playbook (`playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=promtail --tags rollback`).
  `verify.yml` already performs this restore automatically when a new config fails its health check,
  and `-check-syntax` prevents a syntactically broken config from being installed at all.
* Binary: pin the previous `promtail_version` and re-run the role; it downgrades in place. The
  positions file is kept, so no logs are re-shipped.

## Requirements | 要求

Debian bullseye/bookworm or Ubuntu jammy/noble, systemd, outbound HTTPS to GitHub (or a mirror via
`promtail_download_url`), `unzip` on the target (installed by the role when missing). Run with
`become: true` and `gather_facts: true`.
