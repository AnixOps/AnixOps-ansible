# SSH Key Management | SSH 私钥管理

How the Ansible SSH key is used in this repository today, and the options for keeping it safe on
several operator machines. Secret names are listed in
[GITHUB_SECRETS_REFERENCE.md](GITHUB_SECRETS_REFERENCE.md).

## 1. How the key is used today | 当前实现

| Where | How |
|---|---|
| Operator workstation | `.env` sets `SSH_KEY_PATH` (default `~/.ssh/id_rsa`); the generated inventory turns it into `ansible_ssh_private_key_file`. `ANSIBLE_USER` (default `root`) and `ANSIBLE_PORT` (default `22`) come from `.env` as well. |
| GitHub Actions | the `SSH_PRIVATE_KEY` secret is written by `.github/actions/setup-ansible` to `$RUNNER_TEMP/ssh/id_ansible` (mode 0600, directory 0700) and exported as `SSH_KEY_PATH` / `ANSIBLE_PRIVATE_KEY_FILE`; every job removes it with `shred -u` in an `if: always()` step. The key is never written to `~/.ssh/id_rsa` on the runner. |
| Managed hosts | key-only login: `ssh_password_authentication: false` and `ssh_pubkey_authentication: true` in `inventories/production/group_vars/all/main.yml`, applied by the `common` role (sshd configuration validated with `sshd -t` before it is written). Root login stays enabled (`ssh_allow_root: true`) because the fleet is managed as root. |

Helpers in `tools/`:

| Tool | Purpose |
|---|---|
| `tools/ssh_key_manager.py` | find or generate a key, validate it and upload it as the `SSH_PRIVATE_KEY` repository secret (`--key-file`, `--repo`, `--token`, `--secret-name`; interactive without arguments) |
| `tools/ssh_key_deployer.py` | push a public key to one or many hosts (`--key-file`, `--host`, `--user`, `--port`; can read host addresses from `.env`) |
| `tools/secrets_uploader.py` | bulk-upload a `.env` file to repository secrets (`--env`, `--repo`, `--token-env`, `--exclude`, `--dry-run`) |

## 2. Generate and install a key | 生成与安装密钥

```bash
ssh-keygen -t ed25519 -f ~/.ssh/anixops_ed25519 -C "anixops-ansible"
ssh-copy-id -i ~/.ssh/anixops_ed25519.pub root@<host-address>     # once per host
chmod 600 ~/.ssh/anixops_ed25519
# .env
SSH_KEY_PATH=~/.ssh/anixops_ed25519
```

Then upload the private key for CI, either with `gh secret set SSH_PRIVATE_KEY < ~/.ssh/anixops_ed25519`
or with `python3 tools/ssh_key_manager.py`.

Install the key **before** the first deployment: the `common` role disables password logins.

## 3. Rotating the key | 轮换密钥

1. Generate the new key pair.
2. Add the new public key to `authorized_keys` of `ANSIBLE_USER` on every host while the old key still
   works (`tools/ssh_key_deployer.py`, `ssh-copy-id`, or an `ansible.posix.authorized_key` ad-hoc run).
3. Update `SSH_PRIVATE_KEY` (and the `node-platform` environment if it has its own copy) and
   `SSH_KEY_PATH` locally; run `make ping` and a dry-run deployment from CI.
4. Remove the old public key from every host and revoke it everywhere it was stored.

## 4. Options for operator machines | 多机器存放方案

The key must never be committed (`.gitignore` covers `.env`, `*.pem` and `.vault_password.txt`; the
repository tests and `security-scan.yml` fail on tracked key files). Pick a store that fits the team:

| Option | Fits | Notes |
|---|---|---|
| GitHub Secrets + a password manager (1Password, Bitwarden, KeePassXC) | small team, deployments mostly from GitHub Actions | what this repository is built for; operators keep their copy in the password manager |
| SSH agent backed by a password manager | operators who never want the key on disk | the agent offers the key (`ssh-add -l` must list it); the inventory still passes `SSH_KEY_PATH` as `ansible_ssh_private_key_file`, so point it at the public key file or override it with `-e ansible_ssh_private_key_file=...` |
| Ansible Vault | self-contained repository | encrypt a copy of the key with `ansible-vault encrypt`, decrypt it to a 0600 temporary file before a run; the CLI accepts `--vault-password-file` / `--ask-vault-pass` |
| HashiCorp Vault, AWS Secrets Manager, Azure Key Vault | larger teams, audit requirements, SSH certificates | fetch the key (or a short-lived signed certificate) into a 0600 temporary file and pass it with `--private-key`, then delete it |

Example: one-off run with a key from 1Password without leaving it on disk:

```bash
key="$(mktemp)"; chmod 600 "$key"
op read "op://Infrastructure/AnixOps Ansible Key/private key" > "$key"
ansible-playbook playbooks/provision/site.yml --private-key "$key" --check --diff
shred -u "$key"
```

## 5. Checklist | 安全检查清单

- [ ] Private keys have mode 0600 and are never committed.
- [ ] `SSH_PRIVATE_KEY` exists only as a GitHub secret (repository or environment).
- [ ] Every operator's key store is protected by a strong password and 2FA.
- [ ] Keys are rotated on a schedule (for example every 90 days) and when someone leaves.
- [ ] Password authentication is off on every host (`make deploy ANSIBLE_ARGS="--tags common"`
      applies `ssh_password_authentication: false`).
- [ ] A provider console login is available for each host in case SSH breaks
      (see [RUNBOOK.md](RUNBOOK.md), incident response).
