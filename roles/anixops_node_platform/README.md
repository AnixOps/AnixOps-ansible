# anixops_node_platform | AnixOps 节点平台角色

Deploys the upstream `AnixOps-node-platform` web stack (web, API, provision server,
PostgreSQL, Redis, scheduler) as a host-managed Docker Compose project behind the
`nginx` role. The role owns everything below the Nginx edge; the public virtual
hosts come from `inventories/production/group_vars/anixops_node_platform_servers/main.yml`.

## What it does | 功能

1. `install-docker.yml` - installs Docker Engine and the Compose plugin from the
   official apt repository using `ansible.builtin.deb822_repository` plus a GPG key
   fetched with `get_url` (optional `anixops_node_platform_docker_apt_key_checksum`).
   No `curl | sh`, no `apt_key`. The legacy `/etc/apt/sources.list.d/docker.list`
   is removed so the repository is defined once.
2. `configure.yml` - checks out the application source, renders
   `/etc/anixops-node-platform.env` (`0600`, `no_log`, `backup: true`) and the compose
   file (`backup: true`), removes containers left behind by the pre-rename
   `anixops-selfhosted` project, validates the compose file and converges the project
   with `community.docker.docker_compose_v2` (`state: present`, `remove_orphans: true`,
   `wait: true`).
3. `firewall.yml` - probes `ufw status`, deletes unrestricted `ALLOW` rules for the
   application ports only when they exist, adds `DENY` rules (`AnixOps edge only`),
   guarantees the SSH port and 80/443 are allowed, then enables UFW with
   `firewall_default_incoming_policy` (default `allow`).
4. `tls.yml` - installs the certificate/key provided as base64 PEM secrets (validated
   with `openssl x509` / `openssl pkey`), or creates a self-signed fallback pair with
   `openssl req` (`creates:` makes it run once). An orphaned cert or key fails loudly.
5. `verify.yml` - waits until each container reports `healthy` and checks the web and
   API ports on loopback. Failures land in the rescue block of `tasks/main.yml`, which
   prints `docker compose ps --all` and `docker compose logs --tail 100` before failing.

## Boundary | 边界

| Service | Exposure |
|---|---|
| Nginx (separate role) | `80` / `443` public |
| Web frontend | `127.0.0.1:30000`, UFW denies direct inbound |
| API | `127.0.0.1:8787`, UFW denies direct inbound |
| Provision / scheduler / PostgreSQL / Redis | Docker network only |

## Requirements | 要求

- Debian bullseye/bookworm or Ubuntu jammy/noble on `x86_64` or `aarch64`.
- Collections: `community.docker` >= 3.4 (`docker_compose_v2`), `community.general` (`ufw`).
- Outbound HTTPS to `download.docker.com`, GitHub and the container registries.

## Variables | 变量

Every operator-facing value reads an `ANIXOPS_NODE_PLATFORM_*` environment variable
first, so GitHub Actions secrets flow through without inventory edits. The complete
list is in `defaults/main.yml`; the important ones:

| Variable | Default | Purpose |
|---|---|---|
| `anixops_node_platform_repo_url` / `_repo_version` | upstream repo / `main` | Source to deploy. Pin a tag or sha for releases and rollbacks. |
| `anixops_node_platform_deploy_dir` | `/opt/anixops-node-platform` | Compose project directory (`src/` holds the checkout). |
| `anixops_node_platform_env_file` | `/etc/anixops-node-platform.env` | Rendered secrets (`0600`). |
| `anixops_node_platform_compose_pull` | `missing` | `docker compose up` pull policy: `missing`, `always`, `never`, `policy`. |
| `anixops_node_platform_compose_build` | `always` | Rebuild services built from source after each checkout. |
| `anixops_node_platform_compose_wait` / `_wait_timeout` | `true` / `300` | Pass `--wait` so `up` returns only when services are healthy. |
| `anixops_node_platform_healthcheck_retries` / `_delay` | `20` / `6` | Per-container health polling in `verify.yml`. |
| `anixops_node_platform_min_free_disk_gb` | `5` | Playbook preflight threshold. |
| `anixops_node_platform_server_name` | `localhost` (group_vars: `x.anixops.com`) | Public hostname (`ANIXOPS_NODE_PLATFORM_SERVER_NAME` or `_DOMAIN`). |
| `anixops_node_platform_ssl_enabled` | `true` | Render the HTTPS vhost and manage TLS files. |
| `anixops_node_platform_ssl_certificate_pem` / `_key_pem` | `""` | Base64 PEM from `SSL_CERTIFICATE_PEM` / `SSL_CERTIFICATE_KEY_PEM`. Set both or neither. |
| `anixops_node_platform_ssl_self_signed_fallback` | `true` | Create a self-signed pair when no certificate exists. |
| `anixops_node_platform_force_https` | `false` | Emit `return 301 https://...` on the port-80 vhost (needs SSL enabled). |
| `anixops_node_platform_frontend_port` / `_api_port` | `30000` / `8787` | Loopback-published ports; also the UFW deny list. |
| `anixops_node_platform_block_direct_public_ports` | both ports above | Ports denied for direct inbound access. |
| `anixops_node_platform_cleanup_legacy_containers` | `true` | Remove `anixops-selfhosted` / `anixops-*-audit` containers. |

Required secrets (the role asserts they are non-empty): `ANIXOPS_NODE_PLATFORM_PROVISION_SERVER_TOKEN`,
`ANIXOPS_NODE_PLATFORM_API_SECRET`, `ANIXOPS_NODE_PLATFORM_POSTGRES_PASSWORD`,
`ANIXOPS_NODE_PLATFORM_REDIS_PASSWORD`, `ANIXOPS_NODE_PLATFORM_ADMIN_EMAILS`.

Lifecycle contract (consumed by `roles/lifecycle` and the rollback playbook):

```yaml
anixops_node_platform_port: "{{ anixops_node_platform_frontend_port }}"
anixops_node_platform_health_url: "http://127.0.0.1:30000/"
anixops_node_platform_backup_files: [/etc/anixops-node-platform.env, /opt/anixops-node-platform/docker-compose.node-platform.yml]
anixops_node_platform_config_dirs: [/opt/anixops-node-platform]
anixops_node_platform_packages: []        # Docker is never removed by lifecycle cleanup
anixops_node_platform_service_name: docker
```

## Health checks | 健康检查

- Compose: `--wait` blocks until every service with a healthcheck is healthy
  (`anixops_node_platform_compose_wait_timeout` seconds).
- `verify.yml`: `docker inspect .State.Health.Status` for web, API, PostgreSQL, Redis,
  provision and scheduler (`retries x delay` = 20 x 6 s by default), then
  `GET http://127.0.0.1:30000/` and `GET http://127.0.0.1:8787/health`.
- Playbook post-tasks: `GET http://127.0.0.1/` and `https://127.0.0.1/` with
  `Host: <server_name>`, accepting `200/301/302` without following redirects.

## Rollback | 回滚

1. **Previous release**: set `ANIXOPS_NODE_PLATFORM_REPO_VERSION` (or
   `anixops_node_platform_repo_version`) to the previous tag/sha and re-run the playbook.
   The checkout moves back, images are rebuilt and the project is recreated in place.
2. **Previous configuration**: every render keeps the prior file next to the original
   (Ansible `backup: true`, e.g. `/etc/anixops-node-platform.env.<pid>.<timestamp>~`).
   Restore it and recreate the stack:

   ```bash
   cp /etc/anixops-node-platform.env.<backup> /etc/anixops-node-platform.env
   cd /opt/anixops-node-platform
   docker compose --project-name anixops-node-platform \
     --env-file /etc/anixops-node-platform.env -f docker-compose.node-platform.yml up -d --wait
   ```

3. **Full stop/start** (data volumes are preserved):

   ```bash
   docker compose --project-name anixops-node-platform \
     --env-file /etc/anixops-node-platform.env -f docker-compose.node-platform.yml down
   # then re-run the playbook or `up -d --build --wait`
   ```

PostgreSQL data lives in the `postgres_data` volume; take a `pg_dump` before schema
changing upgrades (`docker exec anixops-node-platform-postgres pg_dump -U anixops anixops`).

## Idempotency | 幂等

A second run reports `changed=0`: apt caches are reused for an hour, the repository
and key are content-compared, the git checkout only changes when upstream moves,
compose uses `ignore_build_events` so an unchanged rebuild is not a change, UFW rules
are compared before/after, and the self-signed certificate uses `creates:`.

## Troubleshooting | 排错

| Symptom | Cause / fix |
|---|---|
| `Missing required AnixOps node platform values` | One of the five required secrets is empty in the environment or inventory. |
| `docker compose up` times out with `wait` | A service never became healthy. The rescue output shows `ps --all` and the last 100 log lines; check `DATABASE_URL`/`REDIS_URL` credentials and upstream build errors. |
| `address already in use` on 30000/8787 | A container from the old `anixops-selfhosted` project still runs and cleanup is disabled; run with `anixops_node_platform_cleanup_legacy_containers=true` or remove it manually. |
| `Exactly one of ... .crt / .key exists` | A certificate or key was removed by hand. Provide both PEM secrets or delete the orphan so a matching self-signed pair is created. |
| `must be set together` assertion | Only one of `SSL_CERTIFICATE_PEM` / `SSL_CERTIFICATE_KEY_PEM` is set in the GitHub Environment. |
| Browser shows a self-signed warning | No PEM secrets were provided; upload a CA-issued or Cloudflare Origin certificate pair or run the `acme_ssl` role. |
| UFW is inactive and a stale `allow 30000/tcp` exists | `ufw status` only lists rules while active; the role still appends the `DENY` rules. Remove the stale allow with `ufw delete allow 30000/tcp` or re-run after UFW is enabled. |
| apt cannot find `docker-ce` | The distribution release is not published by Docker yet; override `anixops_node_platform_docker_apt_repo_url` or pin `ansible_distribution_release` via a supported codename. |
