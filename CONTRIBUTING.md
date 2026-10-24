# Contributing | 贡献指南

Thanks for improving AnixOps Ansible. Every change, however small, must meet
[docs/CONVENTIONS.md](docs/CONVENTIONS.md); the checks below enforce it.

## 1. Set up | 环境准备

```bash
git clone https://github.com/AnixOps/AnixOps-ansible.git && cd AnixOps-ansible
scripts/anixops.sh setup --dev      # ./venv, requirements(-dev), Galaxy collections
. venv/bin/activate
make install-dev                    # also installs the pre-commit hooks
```

## 2. Make the change | 修改

- Branch from `main`; keep one topic per branch and pull request.
- Follow [docs/CONVENTIONS.md](docs/CONVENTIONS.md): UTF-8 without BOM, LF, English comments with an
  optional Chinese part after ` | `, FQCN modules, no `ignore_errors`, `changed_when` on commands,
  retries on network operations, `backup: true` plus `validate:` for files under `/etc`,
  role-prefixed variables, the lifecycle contract for service roles and the play keys every playbook
  needs. Read its *Known pitfalls* section before touching timestamps, systemd probes or
  `.ansible-lint`.
- Hosts and groups change only in `inventories/production/servers-config.yml`; run
  `make gen-inventory` and commit the regenerated `hosts.yml` with it.
- New secrets are read with `lookup('env', ...)`, added to `.env.example` without a value, documented
  in [docs/GITHUB_SECRETS_REFERENCE.md](docs/GITHUB_SECRETS_REFERENCE.md) and, if CI needs them,
  matched by the allow-list of `.github/actions/export-secrets`.
- Update the role `README.md`, the relevant file under `docs/` and `CHANGELOG.md` when behaviour
  changes.

## 3. Check before you commit | 提交前检查

```bash
make check             # yamllint + ansible-lint, syntax check of every playbook, pytest, inventory drift
make encoding-check    # no BOM, no mojibake
make backup-coverage   # /etc templates use backup: true
make pre-commit        # optional: every pre-commit hook on the whole repository
```

`make check` must be green. For role changes, also run the localhost integration suite on a
disposable Debian/Ubuntu host with systemd (never on a production machine) and make sure the second
converge reports `changed=0`:

```bash
sudo -E env "PATH=$PATH" "HOME=$HOME" ansible-playbook -i localhost, -c local tests/integration/localhost-converge.yml
sudo -E env "PATH=$PATH" "HOME=$HOME" ansible-playbook -i localhost, -c local tests/integration/localhost-verify.yml
```

## 4. Pull requests | 拉取请求

- Describe what changes on the hosts, the risk level (LOW, MEDIUM, HIGH as defined in
  [docs/RUNBOOK.md](docs/RUNBOOK.md)) and how to roll back.
- For changes to hosts, attach the output of a dry run (`make deploy-dry-run ANSIBLE_ARGS="..."`).
- The `Ansible CI` and `Security Scan` workflows must pass before merging.
- Never commit `.env`, keys, certificates or vault passwords.
