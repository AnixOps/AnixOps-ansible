# AnixOps Node Platform Web Template | 节点平台 Web 模板

This template turns the AnixOps node platform into a normal host-managed deployment:

- The frontend container listens on `127.0.0.1:30000`.
- The API container listens on `127.0.0.1:8787`.
- UFW denies direct inbound access to `30000` and `8787`.
- Nginx is the public edge and proxies the configured domain to the frontend on HTTP and,
  when a certificate exists, HTTPS.
- The provision and scheduler services stay internal to Docker and are not published on the host.

## Layout | 结构

| Path | Role |
|---|---|
| `roles/anixops_node_platform/` | Installs Docker, checks out the source, renders the stack, converges the compose project, applies the UFW edge policy and TLS files, verifies health. |
| `roles/nginx/` | Host reverse proxy (HTTP and HTTPS virtual hosts). |
| `playbooks/provision/node-platform.yml` | Preflight checks, both roles, edge verification. Tag: `node_platform`. |
| `inventories/production/group_vars/anixops_node_platform_servers/main.yml` | Public domain, TLS paths and the `nginx_sites` definition. |
| `inventories/production/node-platform.actions.yml` | Inventory used by GitHub Actions (host from `ANIXOPS_NODE_PLATFORM_1_V4_SSH`). |
| `inventories/production/node-platform.example.yml` | Minimal host group shape for local runs. |
| `.github/workflows/node-platform-deploy.yml` | Dedicated GitHub Actions deployment entry. |

## Ports | 端口

| Service | Exposure |
|---|---|
| Nginx | `80` and `443` on the host |
| Web frontend | `127.0.0.1:30000`, direct inbound denied by UFW |
| API | `127.0.0.1:8787`, direct inbound denied by UFW |
| Provision | internal Docker network only |
| Scheduler | internal Docker network only |
| PostgreSQL / Redis | internal Docker network only (named volumes `postgres_data`, `redis_data`) |

## Variables | 变量

Operator-facing environment variables use the `ANIXOPS_NODE_PLATFORM_` prefix and map 1:1 to
`anixops_node_platform_*` role variables (see `roles/anixops_node_platform/README.md` for the table):

- Connection: `ANIXOPS_NODE_PLATFORM_1_V4_SSH`, `ANSIBLE_USER`, `ANSIBLE_PORT`, `SSH_KEY_PATH`
  (exported by the shared `setup-ansible` composite action).
- Required secrets: `ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN`, `ANIXOPS_NODE_PLATFORM_API_SECRET`,
  `ANIXOPS_NODE_PLATFORM_POSTGRES_PASSWORD`, `ANIXOPS_NODE_PLATFORM_REDIS_PASSWORD`,
  `ANIXOPS_NODE_PLATFORM_ADMIN_EMAILS`.
- Edge: `ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `ANIXOPS_NODE_PLATFORM_DOMAIN` (for example `x.anixops.com`),
  `ANIXOPS_NODE_PLATFORM_PUBLIC_URL`, `ANIXOPS_NODE_PLATFORM_PUBLIC_SCHEME`, `ANIXOPS_NODE_PLATFORM_FORCE_HTTPS`.
- TLS: `ANIXOPS_NODE_PLATFORM_SSL_ENABLED`, `ANIXOPS_NODE_PLATFORM_SSL_CERT`, `ANIXOPS_NODE_PLATFORM_SSL_KEY`,
  `ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_PEM`, `ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_KEY_PEM`,
  `ANIXOPS_NODE_PLATFORM_SSL_SELF_SIGNED_FALLBACK`.
- Release: `ANIXOPS_NODE_PLATFORM_REPO_URL`, `ANIXOPS_NODE_PLATFORM_REPO_VERSION` (tag/sha to deploy or roll back to),
  `ANIXOPS_NODE_PLATFORM_NEXT_PUBLIC_RELEASE_PROFILE`.
- Optional SMTP, Stripe, cloud provider, probe, chain-backed topup, audit anchor, Cloudflare DNS and
  scheduler settings (same prefix; defaults in `roles/anixops_node_platform/defaults/main.yml`).

The generated env file is stored at `/etc/anixops-node-platform.env` (`0600`, rendered with `no_log`),
outside the source checkout, so secrets never sit inside the Docker build context. It keeps the upstream
runtime keys such as `PROVISION_SERVER_TOKEN`, `API_SECRET`, `INSTALL_MODE` and `DISGUISE_DOMAINS`
because the application containers read them.

Node provisioning stays inside the upstream provision server. Set `ANIXOPS_NODE_PLATFORM_INSTALL_MODE` and
`ANIXOPS_NODE_PLATFORM_DISGUISE_DOMAINS` to control that path; this playbook does not install node runtime
software on the web host.

During the project rename the role removes old `anixops-selfhosted` / `anixops-*-audit` containers before
starting `anixops-node-platform`, so stale containers cannot keep `30000` or `8787` allocated.

## Deployment flow | 部署流程

1. **Preflight** (playbook `pre_tasks`): Debian/Ubuntu on `x86_64`/`aarch64`, at least
   `anixops_node_platform_min_free_disk_gb` (5 GiB) free on the filesystem that holds
   `/opt/anixops-node-platform`, and a probe of any existing Docker daemon.
2. **Docker**: official apt repository via `deb822_repository` and a verified GPG key download; every
   apt/get_url step retries.
3. **Stack**: git checkout, env + compose render (previous versions kept as `*~` backups), legacy cleanup,
   `docker compose config`, then `community.docker.docker_compose_v2` with `pull: missing`
   (`ANIXOPS_NODE_PLATFORM`-tunable via `anixops_node_platform_compose_pull`), `build: always`,
   `remove_orphans: true` and `--wait`.
4. **Edge policy**: UFW `DENY 30000/tcp`, `DENY 8787/tcp` (`AnixOps edge only`), SSH and 80/443 allowed
   before UFW is enabled.
5. **TLS**: PEM secrets decoded and validated, or a self-signed fallback created once.
6. **Verify**: every container healthy, loopback HTTP checks, then the Nginx role and the playbook's edge
   checks (`http://127.0.0.1/` and `https://127.0.0.1/` with the public `Host` header, `200/301/302`).

If anything after the Docker install fails, the role prints `docker compose ps --all` and
`docker compose logs --tail 100` and fails the host; the play continues with the next batch
(`serial: 30%`, `max_fail_percentage: 25`).

## GitHub Actions

Use the standalone `Deploy AnixOps Node Platform` workflow for this stack. It runs
`playbooks/provision/node-platform.yml` against `inventories/production/node-platform.actions.yml` and
reads secrets from the GitHub Environment named `node-platform`.

Required secrets in the `node-platform` GitHub Environment:

- `SSH_PRIVATE_KEY`
- `ANSIBLE_USER`
- `ANSIBLE_PORT`
- `ANIXOPS_NODE_PLATFORM_1_V4_SSH`
- `ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN`
- `ANIXOPS_NODE_PLATFORM_API_SECRET`
- `ANIXOPS_NODE_PLATFORM_POSTGRES_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_REDIS_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_ADMIN_EMAILS`

`ANSIBLE_USER` is the SSH login user for the target server, for example `root` or `ubuntu`. `ANSIBLE_PORT`
is the SSH port, usually `22`. `ANIXOPS_NODE_PLATFORM_1_V4_SSH` is the node platform host address, matching
the same pattern as the fleet secrets such as `PL_1_V4_SSH`. The composite action writes the private key and
exports `SSH_KEY_PATH`, which the inventory reads for `ansible_ssh_private_key_file`.

Required domain input:

- Set the workflow `domain` input to the public hostname, for example `x.anixops.com`. The workflow maps it
  to `ANIXOPS_NODE_PLATFORM_SERVER_NAME` and `ANIXOPS_NODE_PLATFORM_DOMAIN` for Ansible.

The dedicated workflow also maps the shorter Environment secret names you already use:

- `VULTR_API_KEY` becomes `ANIXOPS_NODE_PLATFORM_VULTR_API_KEY`
- `SMTP_HOST` becomes `ANIXOPS_NODE_PLATFORM_SMTP_HOST`
- `SMTP_PORT` becomes `ANIXOPS_NODE_PLATFORM_SMTP_PORT`
- `SMTP_USER` becomes `ANIXOPS_NODE_PLATFORM_SMTP_USER`
- `SMTP_PASS` becomes `ANIXOPS_NODE_PLATFORM_SMTP_PASS`
- `SMTP_SECURE` becomes `ANIXOPS_NODE_PLATFORM_SMTP_SECURE`
- `SMTP_FROM` becomes `ANIXOPS_NODE_PLATFORM_SMTP_FROM`
- `SSL_CERTIFICATE_PEM` becomes `ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_PEM`
- `SSL_CERTIFICATE_KEY_PEM` becomes `ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_KEY_PEM`

Common optional secrets:

- `ANIXOPS_NODE_PLATFORM_REPO_URL`
- `ANIXOPS_NODE_PLATFORM_REPO_VERSION`
- `ANIXOPS_NODE_PLATFORM_PUBLIC_URL`
- `ANIXOPS_NODE_PLATFORM_INSTALL_MODE`
- `ANIXOPS_NODE_PLATFORM_DISGUISE_DOMAINS`
- `ANIXOPS_NODE_PLATFORM_CLOUD_PROVIDER`
- `ANIXOPS_NODE_PLATFORM_DIGITALOCEAN_TOKEN`
- `ANIXOPS_NODE_PLATFORM_DO_API_TOKEN`
- `ANIXOPS_NODE_PLATFORM_CLOUDFLARE_TOKEN`
- `ANIXOPS_NODE_PLATFORM_CLOUDFLARE_ZONE_ID`

## Nginx

Keep Nginx as the public edge. The application listens on `30000` and `8787`, but UFW blocks direct
inbound access to both ports. Use a single upstream target, `http://127.0.0.1:30000`. The public domain
comes from `ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `ANIXOPS_NODE_PLATFORM_DOMAIN`.

The node platform host generates separate HTTP and HTTPS virtual hosts for that `server_name`. The HTTPS
vhost defaults to:

- `/etc/nginx/ssl/<domain>.crt`
- `/etc/nginx/ssl/<domain>.key`

If `SSL_CERTIFICATE_PEM` and `SSL_CERTIFICATE_KEY_PEM` are present in Actions, the workflow passes them
through and the role decodes and validates them into those files. If they are missing, the role creates a
self-signed fallback certificate so Nginx can still route `https://x.anixops.com` by `server_name`. Replace
it with an ACME or Cloudflare Origin certificate when browser-trusted TLS is required. Set
`ANIXOPS_NODE_PLATFORM_SSL_ENABLED=false` to disable the HTTPS vhost, or set `ANIXOPS_NODE_PLATFORM_SSL_CERT`
and `ANIXOPS_NODE_PLATFORM_SSL_KEY` to custom paths. Without a matching HTTPS vhost for `x.anixops.com`,
Nginx can serve whatever existing `443` default catches the request, such as Grafana.

### HTTP to HTTPS redirect | HTTP 跳转 HTTPS

`anixops_node_platform_force_https` (env `ANIXOPS_NODE_PLATFORM_FORCE_HTTPS`, default `false`) adds a
server-level `return 301 https://$host$request_uri;` to the port-80 vhost when SSL is enabled. The
`location /` proxy stays in place, so switching the flag off restores plain HTTP without a redeploy of the
stack. Keep it `false` while issuing HTTP-01 ACME challenges or while the fallback certificate is still
self-signed, otherwise browsers are forced onto an untrusted certificate.

Example site definition (the group_vars file already contains the templated version):

```yaml
nginx_default_site_enabled: false
nginx_sites:
  - name: anixops-node-platform
    listen: 80
    listen_ipv6: true
    server_name: x.anixops.com
    locations:
      - path: /
        proxy_pass: "http://127.0.0.1:30000"
        custom_content: |
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection "upgrade";
          proxy_buffering off;
```

## Rollback | 回滚

- **Application**: set `ANIXOPS_NODE_PLATFORM_REPO_VERSION` to the previous tag/sha (workflow secret or
  `-e anixops_node_platform_repo_version=<tag>`) and re-run the workflow/playbook. The checkout moves back,
  images are rebuilt and containers are recreated in place; volumes are untouched.
- **Configuration**: restore the previous `/etc/anixops-node-platform.env` or compose file from the `*~`
  backup Ansible leaves next to it, then `docker compose ... up -d --wait` (commands in the role README).
- **Database**: take `pg_dump` snapshots before upgrades that change the schema; `postgres_data` is a
  named volume and survives `compose down`.

## Troubleshooting | 排错

- Deployment failed: read the rescue output (`docker compose ps --all`, last 100 log lines) in the job log,
  then `ssh` to the host and run `docker compose --project-name anixops-node-platform logs -f <service>`.
- Edge check returned 502/504: the frontend container is not healthy; `docker inspect
  anixops-node-platform-web --format '{{.State.Health}}'`.
- HTTPS check failed but HTTP works: certificate files are missing or unreadable;
  `nginx -t` and `ls -l /etc/nginx/ssl/`.
- Wrong site served on 443: another vhost is `default_server`; make sure the `anixops-node-platform-https`
  server block exists for the public `server_name`.
- Locked out after enabling UFW: the role always allows `ansible_port` (fallback `ssh_port`, then 22)
  before enabling UFW; use the provider console and `ufw allow <port>/tcp` if a custom port was not set.

## Run | 运行

```bash
# Local operator run (host group from your inventory, secrets from the environment)
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/node-platform.yml

# Only the node platform play from a multi-play run
ansible-playbook playbooks/provision/node-platform.yml --tags node_platform

# Dry run
ansible-playbook playbooks/provision/node-platform.yml --check --diff
```
