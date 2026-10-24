# GitHub Secrets Reference | GitHub Secrets 参考

Every secret and environment variable the playbooks, roles and workflows read. Locally the same
names live in `.env` (copy `.env.example`); in GitHub Actions they are secrets of the same name.
How the workflows use them is described in [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md).

## How secrets reach Ansible | 机密如何传递给 Ansible

- `SSH_PRIVATE_KEY` is handed to the `setup-ansible` composite action, which writes it to
  `$RUNNER_TEMP/ssh/id_ansible` (mode 0600), exports `SSH_KEY_PATH` and
  `ANSIBLE_PRIVATE_KEY_FILE`, and every job shreds the directory in an `if: always()` step.
- Everything else goes through the `export-secrets` composite action: it receives
  `toJSON(secrets)` and exports only the names that match its allow-list into `GITHUB_ENV`
  (values are never printed, only the exported names). The default allow-list is:

  ```text
  ^[A-Z0-9_]+_V4_SSH$  ^ANSIBLE_(USER|PORT)$  ^V2BX_  ^V2BOARD_  ^PROMETHEUS_URL$  ^LOKI_URL$
  ^GRAFANA_  ^OBSERVABILITY_  ^SSL_CERTIFICATE_  ^ACME_  ^CLOUDFLARE_  ^FIREWALL_
  ^GLOBAL_WHITELIST_IPS$  ^NOTIFICATION_WEBHOOK_URL$  ^SLACK_WEBHOOK_URL$  ^ANIXOPS_NODE_PLATFORM_
  ^SMTP_  ^VULTR_API_KEY$
  ```

  A secret whose name does not match is not visible to Ansible in CI.
- Secrets can be defined at repository level or in the GitHub Environment the job uses:
  `NodeX` for `deploy.yml`, `lifecycle.yml` and `weekly-security-patch.yml`, `node-platform`
  for `node-platform-deploy.yml`.

## Connection | 连接

| Name | Required | Default | Used by |
|---|---|---|---|
| `SSH_PRIVATE_KEY` | yes (CI) | - | private key for the fleet; the matching public key must be in `authorized_keys` on every host |
| `ANSIBLE_USER` | recommended | `root` | `ansible_user` in the generated inventory |
| `ANSIBLE_PORT` | recommended | `22` | `ansible_port` in the generated inventory |
| `SSH_KEY_PATH` | local only | `~/.ssh/id_rsa` | `ansible_ssh_private_key_file`; CI sets it itself |

## Host addresses | 主机地址

One variable per host, named by `env_var` in `inventories/production/servers-config.yml`. The value
is a plain IPv4 address or a resolvable hostname, without a CIDR suffix. The generated inventory sets
`ansible_host: "{{ lookup('env', '<NAME>') }}"`, so a host whose variable is empty cannot be reached.

| Name | Host | Groups |
|---|---|---|
| `JP_1_V4_SSH` | `jp-1` | `web_servers` |
| `UK_1_V4_SSH` | `uk-1` | `web_servers`, `v2bx_servers` |
| `US_W_1_V4_SSH` | `us-w-1` | `web_servers`, `v2board_servers` |
| `SG_1_V4_SSH` | `sg-1` | `proxy_servers` |
| `HK_1_V4_SSH` | `hk-1` | `proxy_servers` |
| `UK_2_V4_SSH` | `uk-2` | `proxy_servers`, `v2bx_servers` |
| `FR_1_V4_SSH` | `fr-1` | `dev_servers`, `dev` |
| `PL_1_V4_SSH` | `pl-1` | `observability`, `v2board_servers`, `postgres_servers`, `k8s_control_plane`, `k8s_test`; also always on the monitoring whitelist |
| `ANIXOPS_NODE_PLATFORM_1_V4_SSH` | node platform host | `anixops_node_platform_servers` (`inventories/production/node-platform.actions.yml`, `node-platform` environment) |

Adding a host means adding its `env_var` to `servers-config.yml`, running `make gen-inventory`
and creating the secret; any `<NAME>_V4_SSH` is exported automatically.

## Firewall | 防火墙

| Name | Required | Default | Used by |
|---|---|---|---|
| `GLOBAL_WHITELIST_IPS` | no | empty | comma-separated IPs/CIDRs added to `monitoring_whitelist` (`group_vars/all/main.yml`); only these addresses and pl-1 reach the restricted ports 9100, 9080, 9090, 3100, 3000 and 5432 |

## Observability | 可观测性

| Name | Required | Default | Used by |
|---|---|---|---|
| `GRAFANA_ADMIN_PASSWORD` | yes, for the `grafana` play | - | `roles/grafana`; the preflight fails when it is empty or `admin` |
| `GRAFANA_ADMIN_USER` | no | `admin` | `roles/grafana` |
| `GRAFANA_DOMAIN` | no | `localhost` | `roles/grafana` (`root_url`), `tools/cloudflare_manager.py` |
| `OBSERVABILITY_SSL_ENABLED` | no | `false` | `roles/grafana`: `true` makes `root_url` `https://<GRAFANA_DOMAIN>/` (TLS terminated by a reverse proxy) |
| `LOKI_URL` | yes, for hosts other than the Loki host | `http://localhost:3100` | `roles/promtail` push target (`/loki/api/v1/push` is appended) |
| `PROMETHEUS_URL` | no | `http://localhost:9090` | exposed as `prometheus.server_url` in `group_vars/all/main.yml` |
| `GRAFANA_URL` | no | `http://localhost:3000` | exposed as `grafana.url` in `group_vars/all/main.yml` |
| `PROMETHEUS_DOMAIN`, `LOKI_DOMAIN` | no | empty | `tools/cloudflare_manager.py from-env` |

## TLS and Cloudflare | TLS 与 Cloudflare

| Name | Required | Used by |
|---|---|---|
| `SSL_CERTIFICATE_PEM`, `SSL_CERTIFICATE_KEY_PEM` | no | base64-encoded PEM (`tools/encode_ssl_cert.sh cert.pem key.pem [--write]`); `node-platform-deploy.yml` maps them to `ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_PEM` / `_KEY_PEM` |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID` | no | `tools/cloudflare_manager.py` (preferred: scoped token with Zone DNS Edit) |
| `CLOUDFLARE_EMAIL`, `CLOUDFLARE_API_KEY` | no | `tools/cloudflare_manager.py` (Global API key alternative) |
| `CLOUDFLARE_BASE_DOMAIN` | no | `tools/cloudflare_manager.py` |
| `CLOUDFLARE_MESH_TOKEN` | no | `roles/cloudflare_mesh` (not part of any playbook since the mesh was removed from the deployment paths) |

The `acme_ssl` role takes its account e-mail and Cloudflare credentials from inventory variables
(`acme_email` / `acme_ssl_email`, `cloudflare_api_token`, `cloudflare_zone_id`), not from the
environment.

## V2board and V2bX | V2board 与 V2bX

| Name | Required | Default | Used by |
|---|---|---|---|
| `V2BOARD_PG_PASSWORD` | yes | - | `roles/postgresql` (application role password), `roles/v2board` |
| `V2BOARD_JWT_SECRET` | yes | - | `roles/v2board` |
| `V2BOARD_API_TOKEN` | yes | - | `roles/v2board`; `roles/v2bx` uses it to generate node AuthKeys |
| `V2BOARD_ADMIN_EMAIL`, `V2BOARD_ADMIN_PASSWORD` | yes | - | `roles/v2board` |
| `V2BOARD_PG_USER`, `V2BOARD_PG_DATABASE` | no | `v2board` | `roles/postgresql`, `roles/v2board` |
| `V2BOARD_PG_HOST`, `V2BOARD_REDIS_HOST` | no | `localhost` | `roles/v2board` |
| `V2BOARD_REDIS_PASSWORD` | no | empty | `roles/v2board` |
| `V2BOARD_DEPLOY_METHOD` | no | `docker` | `roles/v2board` (`docker` or `binary`) |
| `V2BOARD_DOCKER_TAG` | no | `latest` | `roles/v2board` (docker method) |
| `V2BOARD_BINARY_URL`, `V2BOARD_BINARY_VERSION` | no | - | `roles/v2board` (binary method) |
| `V2BOARD_ENV` | no | `development` | `roles/v2board` (use `development` for the first run, then `production`) |
| `V2BOARD_FRONTEND_PORT`, `V2BOARD_API_PORT`, `V2BOARD_GRPC_PORT`, `V2BOARD_NODEX_PORT` | no | `3001`, `8080`, `50051`, `18081` | `roles/v2board` |
| `V2BOARD_DB_TYPE` | no | `postgres` | `roles/v2board` |
| `V2BX_API_HOST` | yes, for V2bX nodes | - | `roles/v2bx`: panel URL reachable from the node |
| `V2BX_CORE` | no | `sing` | `roles/v2bx` (`sing`, `xray` or `hysteria2`) |
| `V2BX_AUTO_GENERATE_AUTHKEY`, `V2BX_AUTH_KEY`, `V2BX_AUTHKEY_EXPIRE_DAYS` | no | `true`, empty, `1` | `roles/v2bx` |
| `V2BX_BINARY_URL`, `V2BX_NODE_NAME`, `V2BX_PROTOCOLS`, `V2BX_CERT_MODE`, `V2BX_CERT_DOMAIN`, `V2BX_LOG_LEVEL` | no | see `.env.example` | `roles/v2bx` |

## Notifications | 通知

| Name | Required | Used by |
|---|---|---|
| `NOTIFICATION_WEBHOOK_URL` | no | `roles/lifecycle`: generic webhook after deploys and rollbacks |
| `SLACK_WEBHOOK_URL` | no | `roles/lifecycle`: Slack incoming webhook |

The weekly security patch workflow files its backlog issue with the automatic `GITHUB_TOKEN`
(`issues: write`); no extra secret is needed.

## Node platform | 节点平台

The `node-platform` environment needs `SSH_PRIVATE_KEY`, `ANSIBLE_USER`, `ANSIBLE_PORT`,
`ANIXOPS_NODE_PLATFORM_1_V4_SSH` and the `ANIXOPS_NODE_PLATFORM_*` application secrets; the
workflow also maps `VULTR_API_KEY`, `SMTP_*` and `SSL_CERTIFICATE_*`. The full list is in
[ANIXOPS_NODE_PLATFORM.md](ANIXOPS_NODE_PLATFORM.md).

## Local-only and unused names | 仅本地或未使用的变量

- `K3S_TOKEN` (optional) is read by `roles/k8s_provision` when joining k3s agents; it is not on the
  CI allow-list, so runs that need it are local.
- `.env.example` also lists `ACME_EMAIL`, `OBSERVABILITY_SSL_METHOD`, `CLOUDFLARE_MESH_ADVERTISE_SUBNETS`,
  `K8S_CONTROL_SSL_ENABLED`, `K8S_CONTROL_SSL_METHOD`, `K8S_DASHBOARD_DOMAIN`, `K8S_API_DOMAIN`,
  `K8S_METRICS_DOMAIN` and `SPEEDTEST_INSTALL_METHOD`; no role, playbook or workflow reads them at
  the moment.
- Older documentation described per-interface `*_V4`, `*_V6` and `*_SSH_IP` secrets with CIDR
  suffixes, hosts that are no longer in the fleet, and `FIREWALL_WHITELIST_IPS`. No playbook, role or
  workflow reads those names any more; the whitelist variable is `GLOBAL_WHITELIST_IPS` and each
  host has exactly one `<HOST>_V4_SSH` address. Delete the old secrets.

## Setting secrets | 设置方法

```bash
gh secret set SSH_PRIVATE_KEY < ~/.ssh/anixops_ed25519
gh secret set ANSIBLE_USER --body root
gh secret set JP_1_V4_SSH --body 203.0.113.10
gh secret set GRAFANA_ADMIN_PASSWORD --env NodeX     # prompts for the value
gh secret list
```

`tools/ssh_key_manager.py` uploads the private key (interactive without arguments, or
`--key-file <key> --repo owner/repo --token <token> [--secret-name SSH_PRIVATE_KEY]`), and
`tools/secrets_uploader.py` bulk-uploads a `.env` file (`--env .env --repo owner/repo --token-env`,
which reads `GITHUB_TOKEN`; try `--dry-run` first). Both need a GitHub token with `repo` scope and
create repository secrets, not environment secrets.

## Security practice | 安全建议

- Never commit `.env`, keys or certificates; `.gitignore` covers `.env`, `*.pem` and
  `.vault_password.txt`, and the repository tests and `security-scan.yml` fail on tracked keys.
- Rotate `SSH_PRIVATE_KEY` and API tokens regularly and after anyone with access leaves.
- Roles handle secrets with `no_log: true`; never print them with `debug`.
