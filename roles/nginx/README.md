# nginx

Nginx web server / reverse proxy with **validated, zero-downtime, self-healing**
configuration roll-outs. | 具备配置校验、零停机发布和失败自动回滚能力的 Nginx 角色。

## What the role does | 功能

1. Installs Nginx (`apt` / `package`, retried).
2. Optionally stops *other* services that hold ports 80/443
   (`nginx_stop_conflicting_services`, default `false`). Nginx itself is never stopped,
   disabled or killed and no process is ever signalled; the listed services are stopped
   through systemd and only when `service_facts` shows the unit exists.
3. Snapshots the current state: which managed files already exist and which symlinks
   are present in `sites-enabled` (with their targets).
4. Templates every configuration file with `backup: true`, in this order:
   `proxy_params`, `conf.d/security-headers.conf`, custom `conf.d` snippets, the default
   site, one `sites-available/<name>.conf` per entry of
   `nginx_sites + nginx_group_sites + nginx_host_sites` (enable/disable symlinks, optional
   pruning of unmanaged symlinks), an optional host-specific raw file
   (`templates/hosts/<inventory_hostname>.conf.j2`), **then** `nginx.conf` (validated with
   `nginx -t -c %s` before it is written - includes use absolute paths, so the temporary file
   validates the whole tree) and `/etc/logrotate.d/nginx`.
5. Validates the complete configuration with `nginx -t`.
6. **Rollback** - if anything in steps 4-5 fails: every backup taken in this run is copied
   back, files that did not exist before are removed, `sites-enabled` is restored to the
   snapshot, `nginx -t` is run again and the host fails with the captured error. The running
   Nginx keeps serving the previous configuration the whole time.
7. Ensures the service is started and enabled. If that fails, `systemctl status`, the last
   80 journal lines and `ss -Hltnp` for `nginx_diagnostic_ports` are printed before failing.
8. `meta: flush_handlers` -> `Reload nginx`: a graceful reload, workers finish in-flight
   requests. No restart, no port release, no downtime.
9. Probes `nginx_health_url` with retries. If it never answers with one of
   `nginx_health_status_codes`, the configuration is rolled back as in step 6, reloaded and
   the host fails (`nginx_rollback_on_health_failure`).

A second run with unchanged variables reports `changed=0`.

### Why vhosts are written before nginx.conf | 为什么先写站点再写 nginx.conf

`validate: nginx -t -c %s` always checks the *whole* tree the temporary `nginx.conf`
includes. Writing the vhosts and snippets first means a broken pre-existing vhost (for
example a certificate that disappeared) is repaired by the same run instead of blocking it,
and a directive removed from `nginx.conf` can no longer be referenced by a stale vhost. Any
mistake in the new files is still caught by the final `nginx -t` and rolled back.

## Handlers | 处理器

| Handler | Effect |
|---|---|
| `Reload nginx` | `service: state=reloaded`. Flushed inside the role only after `nginx -t` passed. Safe when Nginx is not running yet: the role starts the service before the flush, and on systemd hosts the service module starts an inactive unit instead of failing a reload. |
| `Restart nginx` | `service: state=restarted` - never notified by the role itself; available for operators. |

## Variables | 变量

Role defaults live in `defaults/main.yml`; everything is prefixed `nginx_`.

### Packages, service, lifecycle contract

| Variable | Default | Purpose |
|---|---|---|
| `nginx_packages` | `[nginx]` | Packages to install. |
| `nginx_package_state` | `present` | `present` or a pinned version policy; never `latest` by default. |
| `nginx_service_name` | `nginx` | systemd unit. |
| `nginx_user` / `nginx_group` | `www-data` (Debian) / `nginx` (RedHat) | Worker user, web root owner. |
| `nginx_port` | `80` | Port of the default site and the health probe. |
| `nginx_health_url` | `http://127.0.0.1:80/health` (`/` when the default site is disabled) | Probed after every deploy. |
| `nginx_health_status_codes` | `[200, 204, 301, 302, 307, 308, 401, 403, 404]` | Accepted answers; 5xx is never accepted. |
| `nginx_health_retries` / `nginx_health_delay` | `5` / `5` | Probe retries. |
| `nginx_health_validate_certs` | `false` | For `https://` health URLs. |
| `nginx_rollback_on_health_failure` | `true` | Roll back + reload when the probe keeps failing. |
| `nginx_backup_files` | `nginx.conf`, `proxy_params`, `sites-available/default` | Files the lifecycle/rollback playbooks snapshot. |
| `nginx_config_dirs` | `[/etc/nginx]` | Lifecycle cleanup contract. |

### Conflicting services and diagnostics

| Variable | Default | Purpose |
|---|---|---|
| `nginx_stop_conflicting_services` | `false` | Stop + disable `nginx_conflicting_services` via systemd when they exist. |
| `nginx_conflicting_services` | `[apache2, httpd, caddy, traefik]` | Never contains nginx; nginx is filtered out even if added. |
| `nginx_diagnostic_ports` | `[80, 443]` | Ports listed by `ss -Hltnp` when the service fails to start. |

### Core tuning (fall back to the legacy `nginx:` dictionary)

`nginx_worker_processes` (`auto`), `nginx_worker_connections` (`1024`),
`nginx_keepalive_timeout` (`65`), `nginx_client_max_body_size` (`16M`),
`nginx_log_format`, `nginx_extra_http_configs` (`""`), `nginx_types_hash_max_size` (`2048`),
`nginx_server_names_hash_bucket_size` (`64`), `nginx_server_tokens` (`off`),
`nginx_error_log_level` (`warn`), `nginx_gzip_enabled` (`true`), `nginx_pid_file`
(`/run/nginx.pid`), `nginx_modules_include` (Debian `modules-enabled/*.conf`, RedHat
`/usr/share/nginx/modules/*.conf`, `""` disables), `nginx_log_dir` (`/var/log/nginx`).

The inventory may still define the historical dictionary - its keys are read as fallbacks:

```yaml
nginx:
  worker_processes: auto
  worker_connections: 1024
  keepalive_timeout: 65
  client_max_body_size: 10M
```

### TLS defaults (http context, overridable per site)

`nginx_ssl_protocols` (`TLSv1.2 TLSv1.3`), `nginx_ssl_prefer_server_ciphers` (`on`),
`nginx_ssl_ciphers`, `nginx_ssl_session_cache` (`shared:SSL:10m`),
`nginx_ssl_session_timeout` (`1d`), `nginx_ssl_session_tickets` (`off`).

### Security headers (`conf.d/security-headers.conf`)

| Variable | Default |
|---|---|
| `nginx_security_headers_enabled` | `true` |
| `nginx_security_headers` | `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()` |
| `nginx_hsts_enabled` / `nginx_hsts_header` | `false` / `max-age=31536000; includeSubDomains` |

HSTS is off on purpose: enable it only once every HTTPS name on the host has a valid
certificate. Remember that nginx does not inherit `add_header` into a `server`/`location`
block that defines its own `add_header`.

### Sites

| Variable | Default | Purpose |
|---|---|---|
| `nginx_sites` / `nginx_group_sites` / `nginx_host_sites` | `[]` | Merged into `nginx_all_sites`; put group-wide sites in group_vars and per-host sites in host_vars. |
| `nginx_default_site_enabled` | `true` | Catch-all site on `nginx_port` with `/`, `/health` (200) and `/nginx_status` (loopback). |
| `nginx_default_site_ipv6` | `true` | Add `listen [::]:<port>` to the default site. |
| `nginx_prune_unmanaged_sites` | `false` | Remove `sites-enabled` symlinks the role does not manage. Off so hand-made vhosts survive; turn on for fully declarative hosts. |
| `nginx_proxy_timeout` | `300` | Timeouts in `/etc/nginx/proxy_params`. |
| `nginx_custom_configs` | `[]` | `[{name, content}]` written to `conf.d/<name>.conf`. |
| `nginx_web_root` / `nginx_deploy_index` | `/var/www/html` / `true` | Landing page. |
| `nginx_logrotate_managed` / `nginx_log_rotate_days` | `true` / `14` | `/etc/logrotate.d/nginx`. |

Keys of a site entry:

| Key | Default | Notes |
|---|---|---|
| `name` | required | File name `sites-available/<name>.conf`. |
| `enabled` | `true` | `false` removes the symlink (string booleans such as `"{{ some_flag }}"` work). |
| `listen` | `80` | Port. |
| `listen_ipv6` | `false` | Adds `listen [::]:<port>`. |
| `extra_listen` | `[]` | Raw extra `listen` arguments, e.g. `["127.0.0.1:8080", "[::1]:8443 ssl"]`. |
| `http2` | `false` | Appends `http2` to the listen lines. |
| `default_server` | `false` | Appends `default_server`. |
| `server_name` | `_` | |
| `root`, `index`, `client_max_body_size` | - | Server-level directives. |
| `ssl` | - | `{cert, key, protocols, ciphers}`; `cert`/`key` required when set. |
| `custom_head`, `custom_tail` | - | Raw directives at the top / bottom of the `server` block (empty strings are ignored). |
| `locations` | `[]` | `[{path, root, alias, try_files, proxy_pass, return, custom_content}]`; `proxy_pass` includes `proxy_params`. |
| `access_log`, `error_log` | `/var/log/nginx/<name>.{access,error}.log` | |

Example (HTTP + HTTPS reverse proxy, as used by the node platform group):

```yaml
nginx_default_site_enabled: false
nginx_sites:
  - name: app
    listen: 80
    listen_ipv6: true
    server_name: app.example.com
    locations:
      - path: /
        proxy_pass: http://127.0.0.1:3000
        custom_content: |
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection "upgrade";
  - name: app-https
    enabled: "{{ app_ssl_enabled }}"
    listen: 443
    listen_ipv6: true
    http2: true
    server_name: app.example.com
    client_max_body_size: 64M
    ssl:
      cert: /etc/nginx/ssl/app.example.com.crt
      key: /etc/nginx/ssl/app.example.com.key
      protocols: TLSv1.2 TLSv1.3
    locations:
      - path: /
        proxy_pass: http://127.0.0.1:3000
```

Host-specific raw configuration: if `roles/nginx/templates/hosts/<inventory_hostname>.conf.j2`
exists it is rendered to `sites-available/<inventory_hostname>_custom.conf` and enabled.

## Zero-downtime and rollback | 零停机与回滚

* Nothing is ever restarted by the role; configuration changes are applied by a graceful
  reload after `nginx -t` accepted the full tree.
* Every configuration file is written with `backup: true`. Ansible names backups
  `<file>.<pid>.<timestamp>~` next to the original (for example
  `/etc/nginx/nginx.conf.12345.2026-01-01@10:00:00~`).
* Automatic rollback uses exactly those backups: files changed in this run are restored
  from them, files created in this run are deleted, symlinks added in this run are removed
  and symlinks removed in this run are re-created, then `nginx -t` runs again. The failure
  message states what was restored and whether the restored tree validates.
* `playbooks/maintenance/rollback.yml -e rollback_role=nginx` restores the lifecycle
  snapshot taken before a deploy for a manual rollback.

## Verification | 验证

```bash
nginx -t                                   # configuration is valid
systemctl status nginx                     # active (running), enabled
curl -fsS http://127.0.0.1/health          # "healthy" from the default site
curl -sI http://127.0.0.1/ | grep -i x-frame-options
ls -l /etc/nginx/sites-enabled/            # only managed symlinks (plus hand-made ones unless pruned)
ls /etc/nginx/*~ /etc/nginx/sites-available/*~ 2>/dev/null   # backups of the last runs
```

When a deploy fails the host output contains the `nginx -t` error, the list of restored
files and, for start failures, `systemctl status`, the journal tail and the `ss` listener
table for ports 80/443.

## Notes | 说明

* `templates/k8s/*.j2` and `templates/observability/*.j2` are standalone reference templates
  for a Kubernetes / observability edge. The role does not render them; copy one to
  `templates/hosts/<inventory_hostname>.conf.j2` or express it through `nginx_host_sites`.
* Behaviour changes compared with earlier versions: the port-release logic that stopped
  Nginx and killed every PID on 80/443 is gone; handlers are `Reload nginx` / `Restart nginx`
  (capitalised); `nginx -t` runs after templating, so a broken existing configuration can be
  repaired by a run instead of blocking it.
