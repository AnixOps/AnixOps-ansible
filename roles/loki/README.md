# Loki Server Role | Loki 日志服务端角色

Installs and operates Grafana Loki (single binary, filesystem storage) on the
`observability` group with compactor based retention, a hardened systemd unit
and a verify-or-rollback roll-out.

## Behaviour | 行为

| Step | File | What happens |
|------|------|--------------|
| install | `tasks/install.yml` | `loki` user/group, `/etc/loki`, `/var/lib/loki`, `unzip`. Reads `loki --version` and downloads `loki-linux-<arch>.zip` (amd64/arm64 via `_target_arch`) into a `tempfile` directory only when the binary is missing **or its version differs** from `loki_version` (`get_url` retries, optional `loki_checksum`). Temp directory removed in `always`. |
| configure | `tasks/configure.yml` | Renders `/etc/loki/loki-config.yml` with `validate: loki -config.file=%s -verify-config` (parses and validates without starting modules) and `backup: true`; renders the systemd unit. |
| service | `tasks/service.yml` | `meta: flush_handlers`, then enable + start. |
| verify | `tasks/verify.yml` | Polls `/ready` 12 x 5s (Loki answers 503 for ~15s after start). On failure: journal tail, restore of the binary, configuration and unit replaced in this run (together, because a config rendered for one Loki version may not start another), restart, `fail`. An upgrade keeps the replaced binary as `/usr/local/bin/loki.<pid>.<YYYY-MM-DD@HH:MM:SS>~` only for the run; it is deleted once `/ready` succeeds or after the restore. If `-verify-config` fails in `configure` after a new binary was installed, the play fails before verify and the binary is not reverted (its backup stays in `/usr/local/bin`). |

Handlers: `Reload systemd`, `Restart loki` (Loki has no config reload).

### Storage schema and retention | 存储与保留

* Existing data uses `boltdb-shipper` / schema `v11` under `/var/lib/loki`
  (`chunks/`, `boltdb-shipper-active/`, `boltdb-shipper-cache/`, `compactor/`,
  `wal/`). The role keeps these paths, so upgrades are data compatible.
* `loki_schema_configs` is append-only. To migrate to TSDB add a period with a
  **future** `from` date (example in `defaults/main.yml`); never edit an
  existing period.
* Retention is enforced by the compactor: `compactor.retention_enabled` +
  `limits_config.retention_period` (`loki_retention_period`, default `30d`,
  minimum `24h`). Chunks are deleted `loki_retention_delete_delay` (2h) after
  being marked. Set `loki_retention_enabled: false` to keep data forever.
* The template is version aware: `compactor.shared_store` for Loki < 3.0,
  `delete_request_store` (+ `allow_structured_metadata: false` while v11/v12
  periods exist) for Loki >= 3.0.

## Variables | 变量

| Variable | Default | Description |
|----------|---------|-------------|
| `loki_version` | `loki.version` or `2.9.0` | Release to install; a different installed version triggers an upgrade. |
| `loki_arch` | `_target_arch` or mapped `ansible_architecture` | `amd64` / `arm64`. |
| `loki_checksum` | `""` | Optional `sha256:<hex>` or `sha256:<url>` for the zip. |
| `loki_port` / `loki_grpc_port` / `loki_listen_address` | `loki.port` or `3100` / `9096` / `0.0.0.0` | Listeners. |
| `loki_log_level` | `info` | Server log level. |
| `loki_schema_configs` | boltdb-shipper v11 from 2020-10-24 | Append-only schema periods. |
| `loki_retention_enabled` / `loki_retention_period` / `loki_retention_delete_delay` | `true` / `30d` / `2h` | Compactor retention. |
| `loki_compaction_interval` | `10m` | Compactor interval. |
| `loki_reject_old_samples` / `loki_reject_old_samples_max_age` | `true` / `168h` | Ingestion limits. |
| `loki_ingestion_rate_mb` / `loki_ingestion_burst_size_mb` | `8` / `16` | Per-tenant ingestion rate. |
| `loki_max_query_series` | `5000` | Query limit. |
| `loki_alertmanager_url` | `""` | Ruler Alertmanager URL (section omitted when empty). |
| `loki_extra_args` | `[]` | Extra command line flags. |
| `loki_verify_retries` / `loki_verify_delay` | `12` / `5` | Readiness polling. |

Lifecycle contract: `loki_service_name: loki`, `loki_port`, `loki_health_url`
(`/ready`), `loki_backup_files` (config, unit), `loki_packages: []`,
`loki_config_dirs` (`/etc/loki`, `/var/lib/loki`).

## systemd hardening | systemd 加固

`NoNewPrivileges`, `ProtectSystem=strict` with `ReadWritePaths=/var/lib/loki`,
`ProtectHome`, `PrivateTmp`, `PrivateDevices`, `ProtectKernel*`,
`RestrictSUIDSGID`, `Restart=on-failure`, `RestartSec=5s`,
`StartLimitIntervalSec=300` / `StartLimitBurst=5`, `After=/Wants=network-online.target`.

## Verification | 验证

```bash
curl -fsS http://localhost:3100/ready
curl -fsS http://localhost:3100/metrics | grep -E '^loki_build_info|^loki_ingester_memory_streams'
curl -fsS -G http://localhost:3100/loki/api/v1/labels
loki -config.file=/etc/loki/loki-config.yml -verify-config
journalctl -u loki -n 20 --no-pager
```

A second run of the role must report `changed=0`.

## Rollback | 回滚

```bash
ansible-playbook playbooks/maintenance/rollback.yml -e "rollback_role=loki"
# or on the host
cp /etc/loki/loki-config.yml.<timestamp>~ /etc/loki/loki-config.yml
loki -config.file=/etc/loki/loki-config.yml -verify-config && systemctl restart loki
```

Binary rollback: set `loki_version` to the previous release and re-run the
role. Schema periods must never be removed once data was written with them.
