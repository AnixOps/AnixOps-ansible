# Observability Setup | 可观测性部署指南

The PLG stack: **Prometheus** (metrics), **Loki** (logs) and **Grafana** (dashboards) run on the
`observability` group (pl-1 today); **node_exporter** and **Promtail** run on every host. All five
are roles deployed by `playbooks/provision/site.yml`, and every one of them is verified by
`playbooks/maintenance/health-check.yml`.

## 1. Components | 组件

| Component | Hosts | Version source | Port | Config (validated before it is written) | Unit |
|---|---|---|---|---|---|
| node_exporter | all | `prometheus.node_exporter.version` (1.7.0) | 9100 | systemd unit only | `node_exporter` |
| Promtail | all | `loki.promtail.version` (2.9.3) | 9080 | `/etc/promtail/config.yml` (validated when the binary supports it) | `promtail` |
| Prometheus | `observability` | `prometheus.version` (2.45.0) | 9090 | `/etc/prometheus/prometheus.yml` (`promtool check config`), rules in `/etc/prometheus/rules/` (`promtool check rules`) | `prometheus` |
| Loki | `observability` | `loki.version` (2.9.0) | 3100 (gRPC 9096) | `/etc/loki/loki-config.yml` (`loki -verify-config`) | `loki` |
| Grafana | `observability` | apt.grafana.com, unpinned unless `grafana_version` is set | 3000 | `/etc/grafana/grafana.ini`, provisioning under `/etc/grafana/provisioning/` | `grafana-server` |

The versions live in the `prometheus` / `loki` dictionaries of
`inventories/production/group_vars/all/main.yml`; each role's `README.md` lists every variable.

## 2. Before you deploy | 部署前准备

Set in `.env` (locally) or as secrets (GitHub Actions):

| Variable | Why |
|---|---|
| `GRAFANA_ADMIN_PASSWORD` | **Mandatory.** The `grafana` role's preflight fails when it is empty or `admin`, before anything is installed. |
| `GRAFANA_ADMIN_USER` | optional, default `admin` |
| `LOKI_URL` | Loki address Promtail pushes to, e.g. `http://<pl-1 address>:3100`. The default `http://localhost:3100` only works on the Loki host itself. |
| `GLOBAL_WHITELIST_IPS` | extra addresses allowed to reach the restricted ports (see section 5) |

Promtail on the other hosts pushes to port 3100 on the Loki host, which is a restricted port: add
the sending hosts' addresses to `GLOBAL_WHITELIST_IPS` (or `monitoring_allowed_ips` in
`group_vars/all/main.yml`) before deploying the firewall on the Loki host.

## 3. Deploy | 部署

```bash
# Agents on every host
make deploy ANSIBLE_ARGS="--tags node_exporter,promtail"

# Server side on the observability group
make deploy ANSIBLE_ARGS="--tags prometheus,loki,grafana --limit observability"

# Dry run first
make deploy-dry-run ANSIBLE_ARGS="--tags prometheus,loki,grafana --limit observability"
```

In GitHub Actions use the **Deploy** workflow with `playbook=provision/site.yml`,
`target_group=observability`, `tags=prometheus,loki,grafana`. Each role follows the same roll-out:
template the configuration with `backup: true` and validation, flush handlers, verify health with
retries, and restore this run's backup and fail if the service does not come back.

## 4. What gets configured | 配置内容

### Prometheus

- Scrapes `node_exporter` on every host of `prometheus_node_exporter_group` (default `all`) at
  `<ansible_host>:9100`, labelled with `alias` (`server_alias`), `location`, `environment`,
  `description` and `inventory_host`. Hosts whose address variable is empty, or that set
  `prometheus_scrape_enabled: false`, are skipped.
- Self-monitoring jobs for Prometheus, Promtail, Loki and Grafana on the observability host.
- The `speedtest` job is rendered **only** when `prometheus_speedtest_exporter_host` (or the legacy
  `speedtest_exporter_host`) is set; it is disabled by default.
- Alert rules: every `observability/prometheus/rules/*.yml` (`host-alerts.yml`, `nginx-alerts.yml`,
  `observability-alerts.yml`) is copied and validated; rule files that are no longer in the
  repository are removed (`prometheus_rules_prune: true`). Alerts are only sent when
  `prometheus_alertmanager_targets` is set (empty by default).
- Retention: `prometheus_retention_time: 15d`; `prometheus_retention_size` is empty (no size limit).
- Extra jobs: `prometheus_extra_scrape_configs` (list of raw scrape configs).

### Loki

- Single binary, filesystem storage in `/var/lib/loki`, existing schema `boltdb-shipper` / `v11`
  (`loki_schema_configs`; add a new period with a future `from` date to move to TSDB, never edit an
  existing one).
- **Retention is on by default:** the compactor deletes data older than `loki_retention_period`
  (`30d`), `loki_retention_delete_delay` (`2h`) after marking it (`loki_retention_enabled: true`,
  `loki_compaction_interval: 10m`). Set `loki_retention_enabled: false` or `loki_retention_period: 0s`
  to keep logs forever.
- Ingestion limits: `loki_ingestion_rate_mb` (8), `loki_ingestion_burst_size_mb` (16), samples older
  than 168h are rejected.
- `/ready` answers 503 for roughly 15 seconds after a start; the role and the health check retry.

### Grafana

- Installed from `apt.grafana.com` (deb822 source, armored key in `/etc/apt/keyrings/grafana.asc`);
  sign-up, anonymous access, analytics reporting and update checks are disabled.
- **Admin password:** mandatory and must not be `admin` (see above). Grafana applies
  `[security] admin_password` only when the admin user is first created; to change the password of an
  existing installation run once with `-e grafana_reset_admin_password=true`.
- **Datasources** are provisioned: Prometheus at `http://localhost:9090` and Loki at
  `http://localhost:3100` (`grafana_prometheus_url`, `grafana_loki_url`).
- **Dashboards are provisioned from the repository:** every `observability/grafana/dashboards/*.json`
  (`node-exporter.json`, `observability-health.json`) is copied to `/var/lib/grafana/dashboards` and
  loaded by the file provider `/etc/grafana/provisioning/dashboards/anixops.yml` into the folder
  `AnixOps` (`grafana_dashboards_folder`), re-read every 60 seconds. Dashboards removed from the
  repository are removed from the host (`grafana_dashboards_prune: true`). To change a dashboard,
  export its JSON from Grafana, commit it under `observability/grafana/dashboards/` and redeploy
  `--tags grafana`; edits made only in the UI are overwritten by the provisioned file.

### Agents

- `node_exporter` listens on 9100 (`/metrics`).
- Promtail listens on 9080 (`/ready`) and pushes to `promtail_loki_url`
  (`loki_server_url` if set, else `LOKI_URL`, else `http://localhost:3100`; `/loki/api/v1/push` is
  appended).

## 5. Access | 访问

Ports 9100, 9080, 9090, 3100, 3000 and 5432 are restricted ports (`firewall_restricted_ports`):
reachable only from `monitoring_whitelist`, which is pl-1's address (`PL_1_V4_SSH`) plus
`GLOBAL_WHITELIST_IPS`. From anywhere else use an SSH tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 root@<pl-1 address>
# then open http://localhost:3000 (Grafana) and http://localhost:9090/targets (Prometheus)
```

### HTTPS | HTTPS 访问

`OBSERVABILITY_SSL_ENABLED=true` with `GRAFANA_DOMAIN=grafana.example.com` switches Grafana's
`root_url` to `https://grafana.example.com/`. TLS itself must be terminated by a reverse proxy; that is
not part of `site.yml` for the observability group (pl-1 is not in `web_servers`). To add it:

1. obtain a certificate, either with the `acme_ssl` role (Let's Encrypt via Cloudflare DNS-01,
   installed as `/etc/nginx/ssl/<domain>.crt` / `.key`) or from your own CA;
2. define an `nginx_host_sites` entry for pl-1 with `ssl.cert` / `ssl.key` and a `proxy_pass` to
   `http://127.0.0.1:3000` (see `roles/nginx/README.md`);
3. deploy the nginx role to pl-1, e.g.
   `ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx --tags deploy --limit pl-1`.

The files under `roles/nginx/templates/observability/` are reference templates; no task renders them.

### DNS with Cloudflare | Cloudflare DNS

`tools/cloudflare_manager.py` manages records (`CLOUDFLARE_API_TOKEN`, optionally `CLOUDFLARE_ZONE_ID`):

```bash
python3 tools/cloudflare_manager.py zones
python3 tools/cloudflare_manager.py list -z "$CLOUDFLARE_ZONE_ID"
python3 tools/cloudflare_manager.py upsert -z "$CLOUDFLARE_ZONE_ID" -n grafana.example.com -c 203.0.113.20
python3 tools/cloudflare_manager.py proxy-on -z "$CLOUDFLARE_ZONE_ID" -n grafana.example.com
python3 tools/cloudflare_manager.py proxy-off -z "$CLOUDFLARE_ZONE_ID" -n grafana.example.com
```

`from-env` still looks for the retired `*_V4` server variables, so it finds no servers with the current
`<HOST>_V4_SSH` names; create records with `upsert` instead.

## 6. Verify | 验证

```bash
make health-check ANSIBLE_ARGS="--limit observability"   # units + endpoints on pl-1
make health-check                                         # agents on every host
```

On the observability host:

```bash
curl -fsS http://127.0.0.1:9090/-/healthy
curl -fsS http://127.0.0.1:3100/ready
curl -fsS http://127.0.0.1:3000/api/health
curl -fsS 'http://127.0.0.1:9090/api/v1/query?query=up' | head -c 600
```

In Grafana, the `AnixOps` folder must contain the provisioned dashboards and both datasources must
test green.

## 7. Troubleshooting | 排错

| Symptom | Check |
|---|---|
| `grafana` play fails immediately | `GRAFANA_ADMIN_PASSWORD` is empty or `admin` |
| Login fails after changing `GRAFANA_ADMIN_PASSWORD` | the password is only applied on first start; redeploy once with `-e grafana_reset_admin_password=true` |
| No logs from a host | `LOKI_URL` on that host's run, the host's address in the whitelist of the Loki host, `journalctl -u promtail` |
| A host is missing from Prometheus targets | its `<HOST>_V4_SSH` was empty when Prometheus was deployed, or `prometheus_scrape_enabled: false`; redeploy `--tags prometheus` |
| Prometheus target down | firewall on the target (pl-1 must be whitelisted; it is by default), `systemctl status node_exporter` |
| Loki not ready | it answers 503 for about 15 s after a restart; otherwise `journalctl -u loki` and `loki -config.file=/etc/loki/loki-config.yml -verify-config` |
| Disk usage grows | Loki keeps 30 days and Prometheus 15 days by default; lower `loki_retention_period` / `prometheus_retention_time` (or set `prometheus_retention_size`) and redeploy |
| A dashboard disappeared | it is not in `observability/grafana/dashboards/` and was pruned; commit its JSON |

Rollback of any of these roles: [RUNBOOK.md](RUNBOOK.md) section 5
(`ansible-playbook playbooks/maintenance/rollback.yml -e rollback_role=grafana --limit pl-1`).
