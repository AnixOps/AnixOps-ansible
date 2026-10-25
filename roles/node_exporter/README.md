# node_exporter role | node_exporter 角色

Installs [Prometheus node_exporter](https://github.com/prometheus/node_exporter) from the official
GitHub release, runs it as a dedicated system user under a hardened systemd unit and verifies the
`/metrics` endpoint before the play continues.

从官方 GitHub Release 安装 node_exporter，以专用系统用户运行在加固的 systemd 单元中，并在继续之前验证
`/metrics` 端点。

## Behaviour | 行为

`tasks/main.yml` imports four task files; each is tagged so a sub-step can be run on its own.

| Step | File | Tag | What happens |
|---|---|---|---|
| 1 | `install.yml` | `node_exporter_install` | `node_exporter --version` is parsed; the release tarball is downloaded only when the binary is missing or the version differs (upgrades **and** downgrades). `get_url` retries 5x/10s with a 60s timeout and honours `node_exporter_checksum`. Work happens in an `ansible.builtin.tempfile` directory that is removed in `always`. Binary is installed `root:root 0755`. |
| 2 | `configure.yml` | `node_exporter_configure` | System group/user (`nologin`, no home). Unit file rendered with `backup: true`, notifying `Reload systemd` + `Restart node_exporter`. |
| 3 | `service.yml` | `node_exporter_service` | `meta: flush_handlers` first (daemon-reload / restart), then `systemd_service: enabled + started`. |
| 4 | `verify.yml` | `node_exporter_verify` | `uri` GET on `node_exporter_health_url`, 6 attempts every 5s. On failure: `journalctl -u node_exporter -n 50` is shown, the unit backup created by this run (if any) is restored and the service restarted, then the task fails with a clear message. No `ignore_errors` anywhere. |

A second run reports `changed=0`.

### Config roll-out pattern | 配置发布模式

template (with backup) -> `meta: flush_handlers` -> health check with retries -> on failure restore
`<register>.backup_file`, restart, `fail`. The same pattern is used by the promtail role.

### systemd hardening

`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ProtectControlGroups`,
`ProtectKernelModules`, `ProtectKernelTunables`, `Restart=on-failure`, `RestartSec=5s`,
`StartLimitIntervalSec=300`, `StartLimitBurst=5`, `Wants/After=network-online.target`.
node_exporter only reads `/proc` and `/sys`, so the read-only filesystem view is safe. If you add a
collector that needs to write (none of the defaults do), extend the unit template with
`ReadWritePaths=`.

## Variables | 变量

All variables live in `defaults/main.yml` and are prefixed `node_exporter_`.

| Variable | Default | Purpose |
|---|---|---|
| `node_exporter_version` | `"1.7.0"` | Release to install. Changing it (up or down) re-installs. |
| `node_exporter_download_url` | GitHub releases URL | Base URL; the archive name is appended. |
| `node_exporter_checksum` | `""` | Optional `sha256:<hex>` passed to `get_url` when non-empty. |
| `node_exporter_arch` | `_target_arch` or derived from `ansible_architecture` | `amd64` / `arm64` archive suffix. |
| `node_exporter_install_path` | `/usr/local/bin/node_exporter` | Binary location. |
| `node_exporter_user` / `node_exporter_group` | `node_exporter` | Service account. |
| `node_exporter_port` | `prometheus.node_exporter.port`, else `9100` | Listen port (restricted in the firewall role; only monitoring hosts may reach it). The prometheus role scrapes each target on that target's own `node_exporter_port` (host_vars/group_vars/`-e`). |
| `node_exporter_listen_address` | `"0.0.0.0"` | Bind address. IPv6 literals are bracketed automatically. |
| `node_exporter_collector_args` | filesystem/netclass/netdev exclusions | Collector flags (unchanged from the original role). |
| `node_exporter_extra_args` | `[]` | Extra flags appended to `ExecStart`, e.g. `["--collector.systemd"]`. |
| `node_exporter_verify_retries` / `_delay` | `6` / `5` | Health check attempts and delay in seconds. |
| `node_exporter_service_name` | `node_exporter` | Unit name. |
| `node_exporter_health_url` | `http://127.0.0.1:9100/metrics` | Used by `verify.yml` and the lifecycle hooks. Follows `node_exporter_listen_address` when it is a specific IP. |
| `node_exporter_backup_files` | `[/etc/systemd/system/node_exporter.service]` | Lifecycle contract: files backed up before deploy / restored by rollback. |
| `node_exporter_config_dirs` | `[]` | Lifecycle contract (no config directory). |
| `node_exporter_packages` | `[]` | Lifecycle contract (binary install, nothing to purge). |

`node_exporter_port` falls back to `prometheus.node_exporter.port` from
`inventories/production/group_vars/all/main.yml`, the same value the prometheus role scrapes; the
other keys of that dict are informational (set `node_exporter_version` explicitly). A changed port
also needs `firewall_restricted_ports` updated by hand (it lists `9100` literally). `_target_arch`
from the same file is honoured for the architecture.

The `Restart node_exporter` handler daemon-reloads itself (`daemon_reload: true`): roles sharing a
play merge their same-named `Reload systemd` handlers, so handler order alone does not guarantee a
changed unit is re-read first.

## Verification | 验证

```bash
curl -s localhost:9100/metrics | head
systemctl status node_exporter --no-pager
journalctl -u node_exporter -n 50 --no-pager
ansible-playbook playbooks/provision/site.yml --tags node_exporter
```

## Rollback | 回滚

* Unit file: the template task keeps a backup next to the live file
  (`node_exporter.service.<pid>.<YYYY-MM-DD@HH:MM:SS>~`). Restore the latest one with
  `ansible-playbook playbooks/maintenance/rollback.yml -e rollback_role=node_exporter`, or use the
  lifecycle playbook (`playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=node_exporter --tags rollback`).
  `verify.yml` already performs this restore automatically when the new unit fails its health check.
* Binary: pin the previous `node_exporter_version` and re-run the role; it downgrades in place.

## Requirements | 要求

Debian bullseye/bookworm or Ubuntu jammy/noble, systemd, outbound HTTPS to GitHub (or a mirror via
`node_exporter_download_url`), `tar` on the target. Run with `become: true` and `gather_facts: true`.
