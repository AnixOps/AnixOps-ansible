# Grafana Server Role | Grafana 角色

Installs Grafana from `apt.grafana.com` on Debian/Ubuntu (deb822 source with a
`Signed-By` keyring), renders `grafana.ini`, provisions the Prometheus and Loki
datasources and the dashboards from `observability/grafana/dashboards/`, and
verifies `/api/health` with rollback on failure.

## Behaviour | 行为

| Step | File | What happens |
|------|------|--------------|
| preflight | `tasks/preflight.yml` | Asserts `grafana_admin_password` is set, non-empty and not `admin` (`no_log`), and that the target is Debian based. Nothing is installed when this fails. |
| install | `tasks/install.yml` | `ca-certificates` + `python3-debian` (needed by `deb822_repository`), downloads the ASCII-armored key to `/etc/apt/keyrings/grafana.asc` (`get_url`, retries), removes the legacy `grafana.list` / `/usr/share/keyrings/grafana.gpg`, writes `/etc/apt/sources.list.d/grafana.sources` with `ansible.builtin.deb822_repository`, installs `grafana_package` (apt retries; the cache is force-refreshed when the repository definition changed). |
| configure | `tasks/configure.yml` | `grafana.ini` (`no_log`, `backup`), datasource files `provisioning/datasources/prometheus.yml` + `loki.yml` (uids `prometheus` / `loki`), the dashboard file provider `provisioning/dashboards/anixops.yml`, copies `*.json` dashboards to `/var/lib/grafana/dashboards/` and prunes stale ones. |
| service | `tasks/service.yml` | `meta: flush_handlers`, enable + start `grafana-server`, optional one-off `grafana-cli admin reset-admin-password`. |
| verify | `tasks/verify.yml` | Polls `/api/health` until `database: ok` (12 x 5s). On failure: journal tail, restore of the `grafana.ini` backup and of `datasources/prometheus.yml`, `datasources/loki.yml` and `dashboards/anixops.yml` when they changed in the failed run (files created for the first time stay), restart, `fail`. |

Handler: `Restart grafana` (`grafana-server`, with daemon-reload).

### Admin password | 管理员密码

`[security] admin_password` in `grafana.ini` is applied by Grafana **only when
the admin user is first created**. Changing the variable later does not change
an existing password; run once with `-e grafana_reset_admin_password=true` to
force it through `grafana-cli` (not idempotent by design, hence opt-in).

The value is written triple-quoted (`admin_password = """..."""`) so Grafana's INI parser keeps
it literal; unquoted, it was cut at the first `#` or `;` (a password starting with one silently
fell back to `admin`). The first run after this change rewrites `grafana.ini` once per host and
restarts Grafana once; existing admin credentials are unaffected. An admin created with a
truncated password keeps it until a run with `-e grafana_reset_admin_password=true`. Grafana still
expands `${VAR}`, `$__env{...}` and `$__file{...}` inside the password.

The variable can come from group_vars/vault, `-e`, or the
`GRAFANA_ADMIN_PASSWORD` environment variable (GitHub Actions secret); the same
applies to `GRAFANA_ADMIN_USER`, `GRAFANA_DOMAIN` and `OBSERVABILITY_SSL_ENABLED`.

### Dashboards | 仪表盘

Dashboards are plain Grafana JSON models (not API wrappers) with a
`DS_PROMETHEUS` (and `DS_LOKI`) datasource template variable, so they resolve
the provisioned datasources without import-time substitution. The provider
rescans the directory every `grafana_dashboards_update_interval` seconds
(60), so dashboard updates need no restart. UI edits are disabled
(`allowUiUpdates: false`); change the JSON in the repository instead.

## Variables | 变量

| Variable | Default | Description |
|----------|---------|-------------|
| `grafana_version` | `""` | Empty installs the current release and never upgrades it; set e.g. `11.2.0` to pin (`grafana_package` becomes `grafana=11.2.0`). |
| `grafana_apt_repo_uri` / `grafana_apt_repo_suite` / `grafana_apt_repo_component` | `https://apt.grafana.com` / `stable` / `main` | Repository. |
| `grafana_apt_key_url` / `grafana_apt_keyring` | `https://apt.grafana.com/gpg.key` / `/etc/apt/keyrings/grafana.asc` | Signing key (armored). |
| `grafana_http_addr` / `grafana_http_port` | `0.0.0.0` / `3000` | Listener. |
| `grafana_domain` | `GRAFANA_DOMAIN` env or `localhost` | `[server] domain`. |
| `grafana_ssl_enabled` | `observability_ssl_enabled` / `OBSERVABILITY_SSL_ENABLED` or `false` | `root_url` becomes `https://<domain>/`, secure cookies. |
| `grafana_root_url` | derived | Override when the proxy path differs. |
| `grafana_admin_user` / `grafana_admin_password` | `GRAFANA_ADMIN_USER` or `admin` / `GRAFANA_ADMIN_PASSWORD` or `""` | Admin credentials (password required). |
| `grafana_reset_admin_password` | `false` | One-off password reset on existing installs. |
| `grafana_default_theme` / `grafana_allow_sign_up` / `grafana_anonymous_enabled` | `dark` / `false` / `false` | UI/auth. |
| `grafana_analytics_reporting` / `grafana_check_for_updates` | `false` / `false` | Telemetry. |
| `grafana_log_level` | `info` | Logging. |
| `grafana_extra_ini` | `""` | Raw extra sections appended to `grafana.ini`. |
| `grafana_prometheus_url` / `grafana_loki_url` | `http://localhost:9090` / `http://localhost:3100` | Datasource URLs. |
| `grafana_prometheus_scrape_interval` / `grafana_loki_max_lines` | `15s` / `1000` | Datasource options. |
| `grafana_dashboards_src_dir` / `grafana_dashboards_dir` / `grafana_dashboards_folder` | `observability/grafana/dashboards` / `/var/lib/grafana/dashboards` / `AnixOps` | Dashboard provisioning. |
| `grafana_dashboards_prune` | `true` | Remove dashboards no longer in the repository. |
| `grafana_verify_retries` / `grafana_verify_delay` | `12` / `5` | Health polling. |

Lifecycle contract: `grafana_service_name: grafana-server`, `grafana_port`,
`grafana_health_url` (`/api/health`), `grafana_backup_files` (`grafana.ini`,
datasource and provider files), `grafana_packages: [grafana]`,
`grafana_config_dirs` (`/etc/grafana`, `/var/lib/grafana`).

## Verification | 验证

```bash
curl -fsS http://localhost:3000/api/health
curl -fsS -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" http://localhost:3000/api/datasources | python3 -m json.tool
curl -fsS -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" 'http://localhost:3000/api/search?type=dash-db'
apt-cache policy grafana
systemctl status grafana-server --no-pager
```

A second run of the role must report `changed=0`.

## Rollback | 回滚

```bash
ansible-playbook playbooks/maintenance/rollback.yml -e "rollback_role=grafana"
# or on the host
cp /etc/grafana/grafana.ini.<timestamp>~ /etc/grafana/grafana.ini && systemctl restart grafana-server
# package downgrade
apt-get install grafana=<previous-version>   # then pin grafana_version accordingly
```
