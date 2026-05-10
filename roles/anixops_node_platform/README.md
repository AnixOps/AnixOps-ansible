# AnixOps node platform Web Stack

This role deploys the upstream `anixops-node-platform` node platform stack as a normal host-managed compose project.

## What it does

- Installs Docker and the Compose plugin
- Checks out the upstream application source into `{{ anixops_node_platform_source_dir }}`
- Renders the stack config into `{{ anixops_node_platform_compose_file }}`
- Renders secrets into `/etc/anixops-node-platform.env`
- Starts or updates the web, API, provision, PostgreSQL, Redis, and scheduler services
- Applies a UFW edge policy that blocks direct inbound access to `30000` and `8787`
- Verifies container health and the local frontend port

## Boundary

- The web frontend listens on `127.0.0.1:30000`
- The API listens on `127.0.0.1:8787`
- UFW denies direct inbound access to `30000` and `8787`
- The provision container is internal to Docker only
- The scheduler container is internal to Docker only
- Nginx stays in the separate `nginx` role and proxies the public domain to `127.0.0.1:30000`

## Required inputs

- `ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN`
- `ANIXOPS_NODE_PLATFORM_API_SECRET`
- `ANIXOPS_NODE_PLATFORM_POSTGRES_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_REDIS_PASSWORD`
- `ANIXOPS_NODE_PLATFORM_ADMIN_EMAILS`

Optional values use the same `ANIXOPS_NODE_PLATFORM_` prefix, including SMTP, Stripe, cloud provider, probe, chain-backed topup, audit anchor, Cloudflare DNS, release-profile, and scheduler settings.

Set `ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `ANIXOPS_NODE_PLATFORM_DOMAIN` to the public hostname, for example `x.anixops.com`.

The generated `/etc/anixops-node-platform.env` file keeps the upstream runtime keys, such as `PROVISION_SERVER_TOKEN`, `API_SECRET`, `INSTALL_MODE`, and `DISGUISE_DOMAINS`, because those are read by the application containers.

Node provisioning is handled by the upstream provision server. This role passes `ANIXOPS_NODE_PLATFORM_INSTALL_MODE` and `ANIXOPS_NODE_PLATFORM_DISGUISE_DOMAINS` through to the API and provision containers; it does not install node runtime software directly on the node platform web host.
