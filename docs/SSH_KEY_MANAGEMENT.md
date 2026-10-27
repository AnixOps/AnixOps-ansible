# SSH access and keys | SSH 访问与密钥

Hosts are reached through JumpServer (堡垒机). JumpServer owns the accounts, the keys and the audit
trail; this repository only needs a way to route Ansible's SSH connections through it.

## 1. Connection path | 连接路径

| Where | How |
|---|---|
| JumpServer | Ansible connects through a proxy command or a jump host you configure; the repository ships neither. |
| Operator workstation | `.env` sets `ANSIBLE_USER` (default `root`) and `ANSIBLE_PORT` (default `22`). `SSH_KEY_PATH` (default `~/.ssh/id_rsa`) is the key used for the connection. |
| GitHub Actions | the `SSH_PRIVATE_KEY` secret is written by `.github/actions/setup-ansible` to `$RUNNER_TEMP/ssh/id_ansible` (mode 0600, directory 0700), exported as `SSH_KEY_PATH` / `ANSIBLE_PRIVATE_KEY_FILE`, and shredded in an `if: always()` step. |
| Managed hosts | key-only login: `ssh_password_authentication: false` in `inventories/production/group_vars/all/main.yml`, applied by the `common` role (sshd configuration validated with `sshd -t` before it is written). |

### Routing through JumpServer | 通过 JumpServer 连接

Set the proxy in the environment, so no host name or address of the bastion is committed:

```bash
# Example: JumpServer's SSH gateway as a proxy command (copy the exact command from the JumpServer web UI)
export ANSIBLE_SSH_COMMON_ARGS='-o ProxyCommand="ssh -W %h:%p -p 2222 <jump-user>@<jumpserver-host>"'
```

Or use `ansible_ssh_common_args` / `ansible_ssh_host` per host in the inventory when the inventory
is private. Keep both out of the committed files. Host keys are not pinned (see `ansible.cfg`), so
JumpServer remains the trust anchor for who may reach a host.

## 2. Keys | 密钥

- Create the key pair and register its public key in JumpServer (the account of `ANSIBLE_USER` on
  each asset), so JumpServer can log in on your behalf or your key is pushed to the host by its
  account management.
- Upload the private key as the `SSH_PRIVATE_KEY` GitHub secret for CI, with `gh secret set SSH_PRIVATE_KEY < <key-file>`.
- The key must never be committed. `.gitignore` covers `.env`, `*.pem` and `.vault_password.txt`; the
  repository tests and `security-scan.yml` fail on tracked key files.

## 3. Rotating the key | 轮换密钥

1. Generate a new key pair and add the public key in JumpServer for every asset (while the old key still works).
2. Update `SSH_PRIVATE_KEY` in GitHub and `SSH_KEY_PATH` locally; run `make ping` and a dry-run deployment.
3. Remove the old key from JumpServer and revoke it everywhere it was stored.
