# v2board role | v2board 角色

Deploys the **v2board** control panel (the management panel for V2bX proxy
nodes) either as a Docker container (default) or as a systemd-managed binary.

部署 v2board 控制面板，支持 Docker（默认）与二进制两种方式。

## What the role does | 功能

| Step | docker | binary |
|------|--------|--------|
| Validate secrets / OS | yes | yes |
| Install runtime | Docker Engine from the official apt repository (`deb822` source signed with the Docker key, **no** `curl \| sh`), only when `docker` is missing | Release archive from GitHub (or `V2BOARD_BINARY_URL`), optional checksum, idempotent version marker |
| Configure | `config.yaml` (backup, `no_log`) | `config.yaml` + hardened systemd unit (backup) |
| Start | `community.docker.docker_container` (restart policy `unless-stopped`, host network, idempotent) | `systemctl enable --now v2board` after `daemon-reload` |
| Verify | `GET /api/v2/status` with retries; on failure the previous `config.yaml` is restored, the service restarted and the play fails with the last log lines | same |

The image is pulled with `community.docker.docker_image` (`source: pull`).
When the tag is `latest` and `v2board_docker_pull` is true the pull is forced
on every run, but the task only reports *changed* when the image id differs,
so a second run is `changed=0`.

## Requirements | 依赖

* Debian 11/12 or Ubuntu 22.04/24.04 (apt based).
* Collections: `community.docker` (docker method). Python `requests` is
  installed on the target by the role.
* A reachable PostgreSQL instance when `V2BOARD_DB_TYPE=postgres`
  (see `roles/postgresql`).

## Variables | 变量

Secrets and most knobs come from environment variables (GitHub Actions secrets
or a local `.env`), see `defaults/main.yml` for the full list.

| Variable | Env | Default | Notes |
|----------|-----|---------|-------|
| `v2board_deploy_method` | `V2BOARD_DEPLOY_METHOD` | `docker` | `docker` or `binary` |
| `v2board_docker_image` / `v2board_docker_tag` | `V2BOARD_DOCKER_TAG` | `kalijerry/v2board:latest` | |
| `v2board_docker_pull` | | `true` | force pull when tag is `latest` |
| `v2board_docker_install` | | `true` | install Docker Engine when missing |
| `v2board_binary_url` | `V2BOARD_BINARY_URL` | `""` | custom archive URL |
| `v2board_binary_version` | `V2BOARD_BINARY_VERSION` | `latest` | release tag |
| `v2board_binary_checksum` / `v2board_frontend_checksum` | | `""` | e.g. `sha256:<hex>` |
| `v2board_force_update` | | `false` | re-download even if the version marker matches |
| `v2board_env` | `V2BOARD_ENV` | `development` | `development` runs AutoMigrate; switch to `production` afterwards |
| `v2board_api_port` / `v2board_frontend_port` / `v2board_grpc_port` / `v2board_nodex_port` | `V2BOARD_*_PORT` | `8080` / `3001` / `50051` / `18081` | |
| `v2board_db_type` | `V2BOARD_DB_TYPE` | `postgres` | `postgres` or `sqlite` |
| `v2board_pg_host` / `v2board_pg_password` | `V2BOARD_PG_HOST` / `V2BOARD_PG_PASSWORD` | `localhost` / required | |
| `v2board_redis_host` / `v2board_redis_password` | `V2BOARD_REDIS_HOST` / `V2BOARD_REDIS_PASSWORD` | `localhost` / `""` | memory cache is used unless a non-local host or a password is set |
| `v2board_jwt_secret` | `V2BOARD_JWT_SECRET` | required | |
| `v2board_api_token` | `V2BOARD_API_TOKEN` | required | internal API token, also used by `roles/v2bx` to mint AuthKeys |
| `v2board_admin_email` / `v2board_admin_password` | `V2BOARD_ADMIN_EMAIL` / `V2BOARD_ADMIN_PASSWORD` | required | |
| `v2board_health_retries` / `v2board_health_delay` | | `12` / `5` | health wait (60 s) |
| `v2board_service_user` | | `root` | binary method service account |

### Lifecycle contract | 生命周期契约

`v2board_port`, `v2board_health_url` (`http://127.0.0.1:<api_port>/api/v2/status`),
`v2board_backup_files`, `v2board_config_dirs`, `v2board_packages` (empty on
purpose so a cleanup never removes Docker Engine) and `v2board_service_name`.

## Secrets handling | 密钥处理

* All tasks that render or restore `config.yaml` run with `no_log: true`.
* `config.yaml` is written `0640` and contains the database password, JWT
  secret, admin password and API token. Keep `V2BOARD_*` values in GitHub
  Secrets or a local `.env` that is not committed.
* The same `V2BOARD_API_TOKEN` must be exported when deploying `roles/v2bx`.

## Verification | 验证

```bash
# health endpoint (both methods)
curl -fsS http://127.0.0.1:8080/api/v2/status
# docker
docker ps --filter name=v2board
docker logs --tail 100 v2board
# binary
systemctl status v2board
journalctl -u v2board -n 100 --no-pager
```

## Rollback | 回滚

* A failed health check automatically restores the previous `config.yaml`
  (the `.backup` file produced by the template task) and restarts the service
  before failing the play.
* Manual rollback of the configuration: copy the newest
  `/etc/v2board/config.yaml.<timestamp>~` over `config.yaml` and run
  `docker restart v2board` (docker) or `systemctl restart v2board` (binary).
* Docker image rollback: set `V2BOARD_DOCKER_TAG` to the previous tag and
  re-run the role; the container is recreated with the pinned image.
* Binary rollback: set `V2BOARD_BINARY_VERSION` to the previous release tag
  (or `V2BOARD_BINARY_URL`) and re-run; the version marker triggers the
  download.

## Deployment flow | 部署流程

```
postgresql role  ->  v2board role (writes V2BOARD_API_TOKEN into config.yaml)
                 ->  v2bx role    (uses V2BOARD_API_TOKEN to mint a node AuthKey)
```
