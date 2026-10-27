# Quick Start | 快速上手

From a fresh clone to a verified deployment. Day-2 operations (rollback, incidents) are in
[RUNBOOK.md](RUNBOOK.md); the rules for changing the code are in [CONVENTIONS.md](CONVENTIONS.md).

## 1. Prerequisites | 前置条件

- A Linux control node (or WSL) with Python 3, `git` and bash 4 or newer.
- SSH access to the target servers with a key (the fleet is managed as `root` by default).
- Targets: Debian/Ubuntu is the reference platform (Grafana and the node platform are
  apt-only, and so is V2board). The preflight play of `quick-setup.yml` and `site.yml` accepts the Debian and RedHat
  families and asserts Python 3 and at least 1024 MB free on `/` (`preflight_min_free_mb`).

## 2. Install | 安装

```bash
git clone https://github.com/AnixOps/AnixOps-ansible.git
cd AnixOps-ansible
scripts/anixops.sh setup --dev     # creates ./venv, installs requirements and Galaxy collections
. venv/bin/activate
```

`make install-dev` does the same inside an already active virtualenv and also installs the
pre-commit hooks.

## 3. Configure `.env` | 配置环境变量

```bash
cp .env.example .env
```

`.env` is git-ignored. `scripts/anixops.sh` (and therefore every `make` target) loads it
automatically; for plain `ansible-playbook` runs export it first with
`set -a; . ./.env; set +a`.

Fill in at least:

| Variable | Meaning |
|---|---|
| `<HOST>_V4_SSH` | SSH address of each host you deploy to, plain IPv4 or hostname without a CIDR suffix: `JP_1_V4_SSH`, `UK_1_V4_SSH`, `US_W_1_V4_SSH`, `SG_1_V4_SSH`, `HK_1_V4_SSH`, `UK_2_V4_SSH`, `FR_1_V4_SSH`, `PL_1_V4_SSH` |
| `ANSIBLE_USER`, `ANSIBLE_PORT` | SSH user (default `root`) and port (default `22`) |
| `SSH_KEY_PATH` | private key used by Ansible (default `~/.ssh/id_rsa`) |
| `GRAFANA_ADMIN_PASSWORD` | required before deploying Grafana; must not be empty or `admin` |
| `V2BOARD_*` values | required before deploying the panel and its database: `V2BOARD_PG_PASSWORD`, `V2BOARD_JWT_SECRET`, `V2BOARD_API_TOKEN`, `V2BOARD_ADMIN_EMAIL`, `V2BOARD_ADMIN_PASSWORD` |

Everything else has a working default or is only needed by optional features; see
[GITHUB_SECRETS_REFERENCE.md](GITHUB_SECRETS_REFERENCE.md) for the full list.

## 4. SSH keys | SSH 密钥

```bash
ssh-keygen -t ed25519 -f ~/.ssh/anixops_ed25519 -C "anixops-ansible"
ssh-copy-id -i ~/.ssh/anixops_ed25519.pub root@<host-address>     # repeat per host
# then in .env: SSH_KEY_PATH=~/.ssh/anixops_ed25519
```

Access goes through JumpServer, which manages accounts and keys; see [SSH_KEY_MANAGEMENT.md](SSH_KEY_MANAGEMENT.md).
Password authentication is disabled fleet-wide by the `common` role
(`ssh_password_authentication: false` in `group_vars/all/main.yml`), so install the key before the
first deployment.

## 5. Check the setup | 环境自检

```bash
make doctor        # tools, .env, inventory parses, no drift, collections
make list-hosts    # inventory graph
make ping          # all hosts; narrow with ANIXOPS_FLAGS="--limit jp-1"
```

## 6. Deploy | 部署

```bash
make quick-setup ANSIBLE_ARGS="--limit <new-host>"   # base stack on a new server
make deploy-dry-run                                  # full site.yml in check mode with diff
make deploy                                          # full deployment, asks for confirmation
make deploy ANSIBLE_ARGS="--tags nginx --limit web_servers"   # one service, one group
```

The `site.yml` tags are `common`, `node_exporter`, `promtail`, `firewall`, `nginx`,
`prometheus`, `loki`, `grafana`, `postgresql`, `v2board`, `v2bx`, `speedtest` and `health`.
The same commands without `make`:

```bash
scripts/anixops.sh deploy --dry-run --tags nginx --limit web_servers
ansible-playbook playbooks/provision/site.yml --tags nginx --limit web_servers --check --diff
```

## 7. Verify | 验证

```bash
make health-check                               # read-only, every host
make health-check ANSIBLE_ARGS="--limit jp-1"
```

On a host you can also probe the local endpoints directly:

```bash
curl -fsS http://127.0.0.1:9100/metrics | head   # node_exporter
curl -fsS http://127.0.0.1:9080/ready            # promtail
curl -fsS http://127.0.0.1/health                # nginx default site (web_servers)
```

The restricted ports (9100, 9080, 9090, 3100, 3000, 5432) are only reachable from the monitoring
whitelist (pl-1 plus `GLOBAL_WHITELIST_IPS`), so test them from the host itself or from a
whitelisted address.

## 8. Add a server | 添加服务器

1. Add the host to `inventories/production/servers-config.yml` with a new `env_var`
   (`<HOST>_V4_SSH`) and its `groups`.
2. `make gen-inventory` (shows the diff, asks before writing `hosts.yml`).
3. Put the address in `.env` and, for CI, create a repository secret with the same name.
4. Commit `servers-config.yml` and `hosts.yml` together; `make check` must stay green
   (inventory drift gate).
5. `make quick-setup ANSIBLE_ARGS="--limit <host>"`, then `make deploy ANSIBLE_ARGS="--limit <host>"`.

## 9. GitHub Actions | 自动化部署

Add `SSH_PRIVATE_KEY`, `ANSIBLE_USER`, `ANSIBLE_PORT` and the `<HOST>_V4_SSH` addresses as
secrets (repository or the `NodeX` environment), then run the **Deploy** workflow manually or push
a `v*` tag. Details: [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md).

## 10. Troubleshooting | 排错

| Problem | Check |
|---|---|
| `make ping` fails for one host | the `<HOST>_V4_SSH` value in `.env`, `ssh -i <SSH_KEY_PATH> -p <ANSIBLE_PORT> <ANSIBLE_USER>@<address>` |
| `Permission denied (publickey)` | the public key is not in `authorized_keys` on the host, or `SSH_KEY_PATH` points at the wrong key (`chmod 600` the private key) |
| Grafana play fails at the start | `GRAFANA_ADMIN_PASSWORD` is empty or `admin` |
| Inventory drift reported by `make doctor` / `make check` | run `make gen-inventory` and commit `hosts.yml` |
| Old facts used in a run | facts are cached for an hour in `.ansible/facts_cache`; `make clean` clears them |
| More output needed | `ANIXOPS_FLAGS=-vvv`, and the full log under `.ansible/logs/` |
