# AnixOps node platform Web Template

This template turns the AnixOps stack into a normal host-managed deployment:

- The frontend container listens on `127.0.0.1:30000`.
- The API container listens on `127.0.0.1:8787`.
- UFW blocks direct inbound access to `30000` and `8787`.
- Nginx is the public edge and proxies the configured domain to the frontend.
- The provision service stays internal to Docker and is not published on the host.
- The scheduler service stays internal to Docker and runs billing, topup, audit-anchor, and compliance jobs.

## Recommended layout

- `roles/anixops_node_platform/` installs Docker, clones the source repo, renders the stack config, and starts the compose project.
- `roles/nginx/` provides the host reverse proxy.
- `playbooks/provision/node-platform.yml` ties the two together.
- `inventories/production/group_vars/anixops_node_platform_servers/main.yml` defines the public edge.
- `inventories/production/node-platform.example.yml` shows the minimal host group shape.

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

- `ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN`
- `ANIXOPS_NODE_PLATFORM_API_SECRET`
- `ANIXOPS_NODE_PLATFORM_POSTGRES_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_REDIS_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_ADMIN_EMAILS`
- `ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `ANIXOPS_NODE_PLATFORM_DOMAIN`, for example `x.anixops.com`
- optional SMTP, Stripe, cloud provider, probe, chain-backed topup, audit anchor, Cloudflare DNS, release-profile, and scheduler settings

The generated env file is stored at `/etc/anixops-node-platform.env`, outside the source checkout, so secrets do not sit inside the Docker build context. That file keeps upstream runtime keys such as `PROVISION_SERVER_TOKEN`, `API_SECRET`, `INSTALL_MODE`, and `DISGUISE_DOMAINS`, because those are read by the application containers.

Node provisioning stays inside the upstream provision server. Set `ANIXOPS_NODE_PLATFORM_INSTALL_MODE` and `ANIXOPS_NODE_PLATFORM_DISGUISE_DOMAINS` in the Ansible environment or group vars to control that path; this playbook does not install node runtime software on the node platform web host.

## Nginx

Keep Nginx as the public edge. The application may listen on `30000` and `8787`, but UFW should block direct inbound access to both ports.

Use a single `proxy_pass` target to `http://127.0.0.1:30000`. The public domain comes from `ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `ANIXOPS_NODE_PLATFORM_DOMAIN`.

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
