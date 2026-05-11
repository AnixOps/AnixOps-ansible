# AnixOps node platform Web Template

This template turns the AnixOps stack into a normal host-managed deployment:

- The frontend container listens on `127.0.0.1:30000`.
- The API container listens on `127.0.0.1:8787`.
- UFW blocks direct inbound access to `30000` and `8787`.
- Nginx is the public edge and proxies the configured domain to the frontend on both HTTP and HTTPS when a certificate exists.
- The provision service stays internal to Docker and is not published on the host.
- The scheduler service stays internal to Docker and runs billing, topup, audit-anchor, and compliance jobs.

## Recommended layout

- `roles/anixops_node_platform/` installs Docker, clones the source repo, renders the stack config, and starts the compose project.
- `roles/nginx/` provides the host reverse proxy.
- `playbooks/provision/node-platform.yml` ties the two together.
- `inventories/production/group_vars/anixops_node_platform_servers/main.yml` defines the public edge.
- `inventories/production/node-platform.example.yml` shows the minimal host group shape.
- `.github/workflows/node-platform-deploy.yml` provides a dedicated GitHub Actions deployment entry.

## Ports

| Service | Exposure |
|---|---|
| Nginx | `80` on the host |
| Web frontend | `127.0.0.1:30000`, direct inbound denied by UFW |
| API | `127.0.0.1:8787`, direct inbound denied by UFW |
| Provision | internal Docker network only |
| Scheduler | internal Docker network only |

## Variables

Operator-facing environment variables use the `ANIXOPS_NODE_PLATFORM_` prefix:

- `ANIXOPS_NODE_PLATFORM_1_V4_SSH`
- `ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN`
- `ANIXOPS_NODE_PLATFORM_API_SECRET`
- `ANIXOPS_NODE_PLATFORM_POSTGRES_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_REDIS_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_ADMIN_EMAILS`
- `ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `ANIXOPS_NODE_PLATFORM_DOMAIN`, for example `x.anixops.com`
- optional SMTP, Stripe, cloud provider, probe, chain-backed topup, audit anchor, Cloudflare DNS, release-profile, and scheduler settings
- optional `ANIXOPS_NODE_PLATFORM_SSL_ENABLED`, `ANIXOPS_NODE_PLATFORM_SSL_CERT`, `ANIXOPS_NODE_PLATFORM_SSL_KEY`, `ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_PEM`, `ANIXOPS_NODE_PLATFORM_SSL_CERTIFICATE_KEY_PEM`, `ANIXOPS_NODE_PLATFORM_SSL_SELF_SIGNED_FALLBACK`, and `ANIXOPS_NODE_PLATFORM_PUBLIC_SCHEME` for the Nginx HTTPS virtual host

The generated env file is stored at `/etc/anixops-node-platform.env`, outside the source checkout, so secrets do not sit inside the Docker build context. That file keeps upstream runtime keys such as `PROVISION_SERVER_TOKEN`, `API_SECRET`, `INSTALL_MODE`, and `DISGUISE_DOMAINS`, because those are read by the application containers.

Node provisioning stays inside the upstream provision server. Set `ANIXOPS_NODE_PLATFORM_INSTALL_MODE` and `ANIXOPS_NODE_PLATFORM_DISGUISE_DOMAINS` in the Ansible environment or group vars to control that path; this playbook does not install node runtime software on the node platform web host.

During the project rename, the role removes old `anixops-selfhosted` / `anixops-audit-*` containers before starting `anixops-node-platform`. This prevents old self-hosted containers from keeping `30000` or `8787` allocated.

## GitHub Actions

Use the standalone `Deploy AnixOps Node Platform` workflow for this stack. It runs `playbooks/provision/node-platform.yml` against `inventories/production/node-platform.actions.yml` and reads secrets from the GitHub Environment named `node-platform`.

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

`ANSIBLE_USER` is the SSH login user for the target server, for example `root` or `ubuntu`. `ANSIBLE_PORT` is the SSH port, usually `22`. `ANIXOPS_NODE_PLATFORM_1_V4_SSH` is the node platform host address, matching the same pattern as the old server secrets such as `PL_V4_SSH`.

Required domain input:

- Set the workflow `domain` input to the public hostname, for example `x.anixops.com`. The workflow maps it to `ANIXOPS_NODE_PLATFORM_SERVER_NAME` and `ANIXOPS_NODE_PLATFORM_DOMAIN` for Ansible.

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

Keep Nginx as the public edge. The application may listen on `30000` and `8787`, but UFW should block direct inbound access to both ports.

Use a single upstream target, `http://127.0.0.1:30000`. The public domain comes from `ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `ANIXOPS_NODE_PLATFORM_DOMAIN`.

The node platform host generates separate HTTP and HTTPS virtual hosts for that `server_name`. The HTTPS vhost defaults to:

- `/etc/nginx/ssl/<domain>.crt`
- `/etc/nginx/ssl/<domain>.key`

If `SSL_CERTIFICATE_PEM` and `SSL_CERTIFICATE_KEY_PEM` are present in Actions, the workflow passes them through and the role decodes them into those files. If they are missing, the role creates a self-signed fallback certificate so Nginx can still route `https://x.anixops.com` by `server_name`. Replace it with an ACME or Cloudflare Origin certificate when browser-trusted TLS is required. Set `ANIXOPS_NODE_PLATFORM_SSL_ENABLED=false` to disable the HTTPS vhost, or set `ANIXOPS_NODE_PLATFORM_SSL_CERT` and `ANIXOPS_NODE_PLATFORM_SSL_KEY` to custom paths. Without a matching HTTPS vhost for `x.anixops.com`, Nginx can serve whatever existing `443` default catches the request, such as Grafana.

Example site definition:

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

## Run

```bash
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/node-platform.yml
```
