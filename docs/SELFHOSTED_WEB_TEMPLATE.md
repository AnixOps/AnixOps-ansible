# AnixOps Self-Hosted Web Template

This template turns the AnixOps stack into a normal host-managed deployment:

- The frontend container is published on `127.0.0.1:30000`.
- Nginx is the public edge and proxies only to the frontend.
- The API container stays internal to Docker and is not published on the host.
- The provision service stays internal to Docker and is not published on the host.

## Recommended layout

- `roles/anixops_selfhosted/` installs Docker, clones the source repo, renders the stack config, and starts the compose project.
- `roles/nginx/` provides the host reverse proxy.
- `playbooks/provision/selfhosted-web.yml` ties the two together.
- `inventories/production/group_vars/anixops_selfhosted_servers/main.yml` defines the public edge.
- `inventories/production/selfhosted-web.example.yml` shows the minimal host group shape.

## Ports

| Service | Exposure |
|---|---|
| Nginx | `80` on the host |
| Web frontend | `127.0.0.1:30000` |
| API | internal Docker network only |
| Provision | internal Docker network only |

## Variables

The role reads the same environment values used by the upstream self-hosted deployment:

- `PROVISION_SERVER_TOKEN`
- `API_SECRET`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `ADMIN_EMAILS`
- optional SMTP, Stripe, cloud provider, and probe settings

The generated env file is stored at `/etc/anixops-selfhosted.env`, outside the source checkout, so secrets do not sit inside the Docker build context.

## Nginx

Keep Nginx as an edge concern. Do not publish the API on the host just to make reverse proxying easier.

Use a single `proxy_pass` target to `http://127.0.0.1:30000` and keep `/api` traffic inside the frontend container.

Example site definition:

```yaml
nginx_default_site_enabled: false
nginx_sites:
  - name: anixops-selfhosted
    listen: 80
    listen_ipv6: true
    server_name: anixops.example.com
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
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/selfhosted-web.yml
```
