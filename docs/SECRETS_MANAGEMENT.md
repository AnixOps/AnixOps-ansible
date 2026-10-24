# Secrets Management | 机密管理

Secrets never live in git. Playbooks, roles and the generated inventory read them from environment
variables with `lookup('env', ...)`: locally from `.env`, in GitHub Actions from repository or
environment secrets of the same name. The full list of names is in
[GITHUB_SECRETS_REFERENCE.md](GITHUB_SECRETS_REFERENCE.md).

## 1. Rules | 原则

- Never commit `.env`, private keys, certificates or vault password files. `.gitignore` covers
  `.env`, `*.pem` and `.vault_password.txt`; `tests/test_repo_hygiene.py` and `security-scan.yml`
  (TruffleHog, tracked-key check) fail when such material is committed.
- Never hard-code a secret in a role, playbook or `group_vars`; read it from the environment:

  ```yaml
  grafana_admin_password: "{{ lookup('ansible.builtin.env', 'GRAFANA_ADMIN_PASSWORD') | default('', true) }}"
  ```

- Tasks that handle secrets use `no_log: true`; never print them with `debug`.
- Roles that need a secret assert it is set (and, for Grafana, that it is not `admin`) before they
  change anything.

## 2. Flow | 数据流

```text
.env (local, git-ignored)          GitHub secrets (repository / NodeX / node-platform)
          |                                         |
scripts/anixops.sh loads it              export-secrets action (allow-list) -> GITHUB_ENV
          |                                         |
          +------------- environment variables -----+
                                |
            lookup('env', ...) in hosts.yml, group_vars and role defaults
                                |
                   templates written with no_log / mode 0600
```

## 3. Local use | 本地使用

```bash
cp .env.example .env
$EDITOR .env
make deploy-dry-run                       # scripts/anixops.sh loads .env automatically
set -a; . ./.env; set +a                  # only needed for plain ansible-playbook runs
```

`scripts/anixops.sh` parses `.env` line by line (`KEY=value`, optional quotes and `export`), never
evaluates it, and keeps variables that are already set in the environment. `--env-file PATH` loads a
different file and `--no-env` skips it.

## 4. GitHub Actions | CI 使用

- `SSH_PRIVATE_KEY` goes to the `setup-ansible` action, which writes it to `$RUNNER_TEMP/ssh` and
  shreds it at the end of the job.
- All other secrets reach Ansible through the `export-secrets` action, which exports only names that
  match its allow-list (`<HOST>_V4_SSH`, `ANSIBLE_USER`/`ANSIBLE_PORT`, `V2BOARD_*`, `V2BX_*`,
  `GRAFANA_*`, `OBSERVABILITY_*`, `CLOUDFLARE_*`, `GLOBAL_WHITELIST_IPS`, the webhook URLs, ...). A
  secret with another name is not visible to the playbooks.
- `node-platform-deploy.yml` maps its secrets explicitly in the job environment.

Set secrets with `gh secret set NAME` (add `--env NodeX` for an environment secret), or upload a whole
`.env` file with `tools/secrets_uploader.py --env .env --repo owner/repo --token-env --dry-run`.

## 5. Ansible Vault (optional) | Ansible Vault（可选）

Values that must be versioned can be stored encrypted:

```bash
ansible-vault create inventories/production/group_vars/all/vault.yml
scripts/anixops.sh deploy --ask-vault-pass
scripts/anixops.sh deploy --vault-password-file ~/.config/anixops/vault-pass   # outside the repository
```

Keep the vault password outside the repository. No workflow passes a vault password at the moment,
so vaulted variables are only usable for local runs unless a workflow is extended for it.

## 6. Rotation | 轮换

1. Create the new value (key pair, token, password).
2. Update `.env` on every operator machine and the GitHub secret.
3. Redeploy the consuming role (for example `make deploy ANSIBLE_ARGS="--tags grafana"`; for the
   Grafana admin password add `-e grafana_reset_admin_password=true` once).
4. Revoke the old value. For SSH keys follow [SSH_KEY_MANAGEMENT.md](SSH_KEY_MANAGEMENT.md).

## 7. Checklist | 检查清单

- [ ] `.env` exists only locally and is git-ignored.
- [ ] Every required secret for the roles you deploy is set (`make doctor` checks the inventory;
      roles assert their own secrets).
- [ ] No secret appears in a workflow log (only exported names are printed).
- [ ] Old values are revoked after rotation.
