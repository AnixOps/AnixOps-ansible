# acme_ssl

Issues TLS certificates with [acme.sh](https://github.com/acmesh-official/acme.sh) using
DNS-01 validation (Cloudflare by default), installs them where the `nginx` role expects
them and keeps them renewed from cron. | 使用 acme.sh 通过 DNS-01 签发证书，安装到 Nginx
并自动续期。

## What the role does | 功能

1. Validates its inputs (`assert`): a list of domains, an account e-mail and, for Cloudflare,
   an API token.
2. Installs `curl openssl socat tar cron|cronie` and makes sure the cron service runs.
3. Installs acme.sh **once** from a pinned release tarball (`acme_ssl_version`, optional
   `acme_ssl_checksum`) - `get_url` -> `unarchive` -> `./acme.sh --install --nocron --noprofile`
   guarded by `creates:`. No `curl | sh`.
4. Issues a certificate for every domain that has none yet in `acme_ssl_home`
   (`acme.sh --issue --dns <hook> --server <ca> --keylength <len>`). DNS credentials are
   passed through the task environment under `no_log`; acme.sh persists them in
   `account.conf` for renewals. `acme_ssl_force_renew: true` forces re-issuance.
5. Installs (re)issued certificates - or ones missing from `acme_ssl_cert_dir` - as
   `<dir>/<domain>.crt` (full chain) and `<dir>/<domain>.key` with
   `--reloadcmd "systemctl try-reload-or-restart nginx"`, and notifies `Reload nginx`.
6. Manages the renewal cron entry (`acme.sh --cron`) at a deterministic per-host minute/hour.

Run the role **after** the `nginx` role (or on a host where Nginx is already installed):
`--install-cert` executes `acme_ssl_reload_cmd`. A second run with no new domains reports
`changed=0`.

## Variables | 变量

| Variable | Default | Purpose |
|---|---|---|
| `acme_ssl_email` | `{{ acme_email \| default('') }}` | ACME account e-mail (required when domains are set). |
| `acme_ssl_domains` | `{{ acme_domains \| default([]) }}` | List of domains to issue (one certificate each). |
| `acme_ssl_ca_server` | `letsencrypt` | `letsencrypt_test`, `zerossl`, `buypass`, `google` ... |
| `acme_ssl_key_length` | `ec-256` | `ec-384`, `2048`, `4096` ... |
| `acme_ssl_force_renew` | `false` | Re-issue even if the certificate exists. |
| `acme_ssl_extra_issue_args` | `[]` | Extra `--issue` arguments. |
| `acme_ssl_dns_provider` | `{{ acme_dns_provider \| default('cloudflare') }}` | Provider name; mapped through `acme_ssl_dns_hooks` (unknown -> `dns_<provider>`). |
| `acme_ssl_cloudflare_api_token` | `{{ cloudflare_api_token \| default('') }}` | Cloudflare API token (`CF_Token`). |
| `acme_ssl_cloudflare_zone_id` | `{{ cloudflare_zone_id \| default('') }}` | Cloudflare zone id (`CF_Zone_ID`). |
| `acme_ssl_dns_env` / `acme_ssl_extra_env` | provider env / `{}` | Environment for the dnsapi hook (other providers: set `acme_ssl_extra_env`). |
| `acme_ssl_version` | `3.1.6` | acme.sh release tag. |
| `acme_ssl_download_url` | GitHub release tarball of that tag | Override for a mirror. |
| `acme_ssl_checksum` | `""` | `sha256:<hex>` to verify the download. |
| `acme_ssl_download_dir` / `acme_ssl_home` | `/usr/local/src` / `/root/.acme.sh` | |
| `acme_ssl_cert_dir` / `acme_ssl_cert_dir_mode` | `/etc/nginx/ssl` / `0700` | Where `<domain>.crt` / `<domain>.key` are installed. |
| `acme_ssl_nginx_service_name` | `nginx` | Unit reloaded by the handler and by renewals. |
| `acme_ssl_reload_cmd` | `systemctl try-reload-or-restart nginx` | Executed by acme.sh after each issue/renewal; does nothing when Nginx is stopped. |
| `acme_ssl_cron_enabled` / `acme_ssl_cron_minute` / `acme_ssl_cron_hour` | `true` / per-host random | Renewal schedule. |
| `acme_ssl_packages` | OS-aware list | Dependencies. |
| `acme_ssl_service_name`, `acme_ssl_port`, `acme_ssl_health_url`, `acme_ssl_backup_files`, `acme_ssl_config_dirs` | `cron`/`crond`, `443`, `https://127.0.0.1:443/`, `account.conf`, home + cert dir | Lifecycle contract. |
| `acme_ssl_cleanup_service_name` / `acme_ssl_cleanup_packages` | `""` / `[]` | Lifecycle cleanup never stops or disables the host-wide cron service and removes no packages (they are a shared base set). |

The unprefixed inventory keys `acme_email`, `acme_dns_provider`, `acme_domains`,
`cloudflare_api_token` and `cloudflare_zone_id` keep working as fallbacks.

Pairing with the nginx role:

```yaml
acme_domains: [app.example.com]
acme_email: ops@example.com
cloudflare_api_token: "{{ lookup('env', 'CLOUDFLARE_API_TOKEN') }}"
nginx_sites:
  - name: app-https
    listen: 443
    http2: true
    server_name: app.example.com
    ssl:
      cert: /etc/nginx/ssl/app.example.com.crt
      key: /etc/nginx/ssl/app.example.com.key
```

## Handlers | 处理器

`Reload nginx` (own copy): `service: state=reloaded`, skipped when the host has no
`nginx.service` (checked through `service_facts`); on systemd hosts an inactive unit is
started instead of failing the reload.

## Verification and rollback | 验证与回滚

```bash
/root/.acme.sh/acme.sh --list                      # issued certificates and renewal dates
openssl x509 -noout -dates -subject -in /etc/nginx/ssl/<domain>.crt
crontab -l | grep acme.sh                          # renewal entry
tail -n 50 /root/.acme.sh/acme.sh.log              # issue/renew log (credentials are not printed)
```

Issue failures are reported per domain with the acme.sh output hidden (it may carry DNS API
credentials); the log file above has the details. Certificates are never deleted by the role:
to roll back to a previous certificate restore `/etc/nginx/ssl/<domain>.{crt,key}` from the
lifecycle backup and reload Nginx, or re-run with `-e acme_ssl_force_renew=true` to obtain a
fresh one.

`lifecycle.yml --tags cleanup -e lifecycle_target_role=acme_ssl` archives the acme.sh home and
certificate directory but leaves cron running and the packages installed; it does **not** remove
the `acme.sh auto-renewal` line from root's crontab (remove it with `crontab -e`). Note that
`rollback.yml` restarts cron (the contract service) rather than reloading Nginx after restoring
certificates; reload Nginx yourself afterwards.
