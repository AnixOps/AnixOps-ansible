# Prometheus Server Role | Prometheus 服务端角色

Installs and operates a hardened, single-node Prometheus server on the
`observability` group: architecture/version aware binary install, alert rules
from `observability/prometheus/rules/`, inventory driven scrape targets, a
hardened systemd unit and a verify-or-rollback roll-out.

## Behaviour | 行为

| Step | File | What happens |
|------|------|--------------|
| install | `tasks/install.yml` | Creates the `prometheus` user/group and directories. Reads `prometheus --version`; downloads the release tarball for `prometheus_arch` (amd64/arm64, from `_target_arch`) into a `tempfile` directory only when the binary is missing **or its version differs** from `prometheus_version`. `get_url` has retries and an optional `prometheus_checksum`. Installs `prometheus` + `promtool` (and console templates for 2.x). The temp directory is removed in `always`. |
| configure | `tasks/configure.yml` | Copies `observability/prometheus/rules/*.yml` to `/etc/prometheus/rules/` (`validate: promtool check rules %s`), prunes stale rule files, renders `prometheus.yml` (`validate: promtool check config %s`, `backup: true`) and the systemd unit. |
| service | `tasks/service.yml` | `meta: flush_handlers` (daemon-reload / restart / reload happen *before* the health check), then enable + start. |
| verify | `tasks/verify.yml` | Polls `/-/healthy` and `/-/ready` (`prometheus_verify_retries` x `prometheus_verify_delay`, default 60s). On failure: prints the journal tail, restores the `.backup` files produced by the template tasks, restarts, and fails with a clear message. |

Handlers: `Reload systemd`, `Restart prometheus`, `Reload prometheus`
(`systemctl reload` -> `ExecReload=/bin/kill -HUP`; starts the unit if it is
not running). Configuration and rule changes only reload; binary and unit
changes restart.

### Scrape targets | 抓取目标

* `prometheus` (self), `promtail` (`prometheus_promtail_port`: the host's `promtail_port`, else
  `loki.promtail.port`, else 9080), `loki` (3100) and `grafana` (3000) on the observability host.
* `node_exporter`: one target per host of `prometheus_node_exporter_group`
  (default `all`) built from `hostvars[host].ansible_host` with labels
  `alias` (`server_alias`, falls back to the inventory name), `location`,
  `environment` (`server_environment`), `description` and `inventory_host`.
  Hosts whose `ansible_host` renders empty, hosts with
  `prometheus_scrape_enabled: false` and duplicate addresses are skipped.
* `relabel_configs` copy `__address__` to `target_ip` and set `instance` to the
  alias, so `up` and every series share the friendly `instance`.
* `speedtest` (9091) only when `prometheus_speedtest_exporter_host` is set
  (legacy global `speedtest_exporter_host` is honoured).
* `prometheus_extra_scrape_configs` is appended verbatim.

## Variables | 变量

| Variable | Default | Description |
|----------|---------|-------------|
| `prometheus_version` | `prometheus.version` or `2.45.0` | Release to install; a different installed version triggers an upgrade. |
| `prometheus_arch` | `_target_arch` or mapped `ansible_architecture` | `amd64` / `arm64`. |
| `prometheus_checksum` | `""` | Optional `sha256:<hex>` or `sha256:<url>` for the tarball. |
| `prometheus_port` / `prometheus_listen_address` | `9090` / `0.0.0.0:9090` | Web listen address. |
| `prometheus_retention_time` / `prometheus_retention_size` | `15d` / `""` | TSDB retention (size e.g. `50GB`). |
| `prometheus_external_url` | `""` | `--web.external-url` behind a reverse proxy. |
| `prometheus_web_enable_lifecycle` | `false` | Enables `/-/reload`; reloads use SIGHUP anyway. |
| `prometheus_extra_args` | `[]` | Extra command line flags. |
| `prometheus_scrape_interval` / `prometheus_scrape_timeout` / `prometheus_evaluation_interval` | `15s` / `10s` / `15s` | Global intervals. |
| `prometheus_external_labels` | `{cluster: anixops}` | `global.external_labels`. |
| `prometheus_alertmanager_targets` | `[]` | e.g. `["localhost:9093"]`; empty omits `alerting`. |
| `prometheus_node_exporter_group` / `prometheus_node_exporter_port` | `all` / `prometheus.node_exporter.port` or `9100` | node_exporter target generation. A target's own `node_exporter_port` (host_vars, group_vars or `-e`) wins for that target. |
| `prometheus_scrape_promtail` / `prometheus_scrape_loki` / `prometheus_scrape_grafana` | `true` | Self-monitoring jobs (ports `prometheus_promtail_port`, `prometheus_loki_port`, `prometheus_grafana_port`). |
| `prometheus_speedtest_exporter_host` | `speedtest_exporter_host` or `""` | Speedtest exporter; job rendered only when non-empty (`prometheus_speedtest_scrape_interval: 60s`, timeout `30s`). |
| `prometheus_extra_scrape_configs` | `[]` | Raw `scrape_configs` entries. |
| `prometheus_rules_src_dir` / `prometheus_rules_prune` | `observability/prometheus/rules` / `true` | Rule file source and pruning of stale files. |
| `prometheus_verify_retries` / `prometheus_verify_delay` | `12` / `5` | Health check polling. |
| `prometheus_health_host` / `prometheus_health_port` | `127.0.0.1` for a wildcard bind, else the host of `prometheus_listen_address` / its port | Address the probes use. |
| `prometheus_health_route_prefix` | `--web.route-prefix=<p>` from `prometheus_extra_args`, else the path of `prometheus_external_url` | Route prefix of the probes. A prefix passed as two list items (`--web.route-prefix`, `<p>`) is not detected: override the URLs. |
| `prometheus_health_base_url` / `prometheus_health_url` / `prometheus_ready_url` | `http://127.0.0.1:9090` / `<base>/-/healthy` / `<base>/-/ready` | Probe URLs used by `verify.yml`, the lifecycle hooks and `rollback.yml`. |

Lifecycle contract (consumed by `roles/lifecycle` and `rollback.yml`):
`prometheus_service_name: prometheus`, `prometheus_port`,
`prometheus_health_url` (`<base>/-/healthy`, see above), `prometheus_backup_files`
(`prometheus.yml`, unit), `prometheus_packages: []`, `prometheus_config_dirs`
(`/etc/prometheus`, `/var/lib/prometheus`).

## systemd hardening | systemd 加固

`NoNewPrivileges`, `ProtectSystem=strict` with `ReadWritePaths=/var/lib/prometheus`,
`ProtectHome`, `PrivateTmp`, `PrivateDevices`, `ProtectKernel*`,
`RestrictSUIDSGID`, `Restart=on-failure`, `RestartSec=5s`,
`StartLimitIntervalSec=300` / `StartLimitBurst=5`, `After=/Wants=network-online.target`.

## Verification | 验证

```bash
curl -fsS http://127.0.0.1:9090/-/healthy && curl -fsS http://127.0.0.1:9090/-/ready
curl -fsS http://localhost:9090/api/v1/targets | python3 -m json.tool | grep -E '"health"|"instance"'
curl -fsS http://localhost:9090/api/v1/rules | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["data"]["groups"]), "rule groups")'
promtool check config /etc/prometheus/prometheus.yml
systemctl status prometheus --no-pager
```

A second run of the role must report `changed=0`.

## Rollback | 回滚

Every template/copy task writes a timestamped `*.backup.*` next to the file.
The role rolls back automatically when the health check fails. Manual rollback:

```bash
ansible-playbook playbooks/maintenance/rollback.yml -e "rollback_role=prometheus"
# or on the host
cp /etc/prometheus/prometheus.yml.<timestamp>~ /etc/prometheus/prometheus.yml
promtool check config /etc/prometheus/prometheus.yml && systemctl reload prometheus
```

To roll the binary back, set `prometheus_version` to the previous release and
re-run the role (the version check reinstalls when the installed version
differs).
