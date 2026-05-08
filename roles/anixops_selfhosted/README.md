# AnixOps Self-Hosted Web Stack

This role deploys the upstream `AnixOps-xray-install` self-hosted stack as a normal host-managed compose project.

## What it does

- Installs Docker and the Compose plugin
- Checks out the upstream application source into `{{ anixops_source_dir }}`
- Renders the stack config into `{{ anixops_compose_file }}`
- Renders secrets into `/etc/anixops-selfhosted.env`
- Starts or updates the compose project
- Verifies container health and the local frontend port

## Boundary

- The web frontend is published on `127.0.0.1:30000`
- The API container is internal to Docker only
- The provision container is internal to Docker only
- Nginx stays in the separate `nginx` role and proxies only to the frontend

## Required inputs

- `PROVISION_SERVER_TOKEN`
- `API_SECRET`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `ADMIN_EMAILS`

Optional values include SMTP, Stripe, cloud provider, and probe settings.
