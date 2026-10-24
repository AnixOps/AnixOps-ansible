# Hardening programme — handoff notes | 交接说明

Branch: `claude/eloquent-mayer-k1lnlt`. This file is a working document for finishing the
programme; delete it (or move its durable parts into `docs/`) before the final merge into `main`.

## 1. Where things stand | 现状

Fifteen parallel rewrites landed (inventory, workflows, every role, every playbook, CLI, tests).
Gate results on the last cloud run (`make check` equivalents):

| Gate | Result |
|---|---|
| `ansible-lint --offline` (whole repo, production profile) | 0 failures, 0 warnings |
| `yamllint -c .yamllint.yml .` | 0 errors |
| `ansible-playbook --syntax-check` on all 15 playbooks | all pass |
| `python3 -m pytest -q` (~4,150 tests) | all pass after the residual fixes in this commit |
| `python3 scripts/check-backup-coverage.py` | 0 findings (2 documented allowlist entries) |
| `make encoding-check` | clean |
| `python3 tools/generate_inventory.py local --check` | no drift |
| `shellcheck -x -S warning scripts/*.sh tools/*.sh` | clean |

Reproduce locally:

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
ansible-galaxy collection install -r requirements.yml
make check            # lint + syntax + pytest + inventory drift
make encoding-check
python3 scripts/check-backup-coverage.py
```

Conventions every change must meet: `docs/CONVENTIONS.md`.

## 2. Remaining work, in order | 剩余工作

1. **Integration tests (CI already wired, job is skipped until the files exist).**
   Create `tests/integration/localhost-converge.yml` and `tests/integration/localhost-verify.yml`.
   `ansible-ci.yml` runs them on `ubuntu-latest` as
   `sudo -E env PATH=$PATH HOME=$HOME ansible-playbook -i localhost, -c local <file>`, then runs the
   converge a second time and asserts `changed=0` in the recap. Suggested scope: roles `common`
   (`common_manage_ssh: false`, `common_manage_time: false` on a runner), `node_exporter`, `promtail`
   (`promtail_loki_url` pointing at a non-existent Loki is fine), `nginx` (default site, verify
   `/health`), `firewall` with `firewall_enabled: false` or `firewall_default_incoming_policy: allow`.
   Verify playbook: `uri` checks on 9100/metrics, 9080/ready, 80/health, `service_facts` states.
   On WSL Debian with systemd enabled the same playbooks can be run for real.
2. **Documentation refresh (wave 2).** `README.md` (playbook table, `kind.yml` targets group
   `k8s_local`, new tags, `make`/CLI command table, workflow inputs `limit_hosts`/`tags`/
   `verbosity`/`confirm`, tag-push deploy matrix), `docs/QUICKSTART.md`, `docs/GITHUB_ACTIONS_SETUP.md`
   and `docs/GITHUB_SECRETS_REFERENCE.md` (they still describe the retired `*_V4/_SSH_IP` scheme and
   `DE_1_V4_SSH`; the real variable set is `.env.example`), `docs/OBSERVABILITY_SETUP.md` (Grafana
   password mandatory and not `admin`, dashboards provisioned from `observability/grafana/dashboards/`,
   Loki retention on by default 30d), `docs/SSH_KEY_MANAGEMENT.md` (check paths), new `docs/RUNBOOK.md`
   (deploy, verify, rollback with `rollback.yml` and `lifecycle.yml`, incident steps, native backup
   naming `<file>.<pid>.<date>~`), `CHANGELOG.md` entry `v0.3.0`, `VERSION` → `v0.3.0`,
   `CONTRIBUTING.md` pointing at `docs/CONVENTIONS.md`.
3. **Small open items from the agent notes.**
   - `inventories/production/servers-config.yml`: pl-1 `k3s_version: v1.27.3+k3s1` is EOL (role default
     `v1.31.5+k3s1`) and `kubeconfig_local_path: /tmp/k3s-pl-1-kubeconfig.yaml` should become
     `~/.kube/k3s-pl-1.yaml`; then `make gen-inventory`.
   - `scripts/anixops.sh` (~line 725) and `.github/workflows/lifecycle.yml` (~line 180) still pass
     `-e lifecycle_hook_type=post_rollback` (harmless, obsolete) and do not pass
     `-e lifecycle_confirm_all=true` / `-e rollback_confirm_all=true` when a forced group-wide
     rollback or cleanup is requested; the playbooks refuse multi-host runs without it.
   - `roles/nginx/templates/k8s/k8s-dashboard.conf.j2` uses `k8s_dashboard_domain` without a default
     (the dashboard role defaults to `dashboard.local`); the `k8s/` and `observability/` nginx templates
     are reference templates referenced by nothing.
   - Optional workflow inputs: `allow_reboot` for `weekly-security-patch.yml`
     (`-e security_patch_allow_reboot=`), `ANIXOPS_NODE_PLATFORM_FORCE_HTTPS` for the node platform job.
   - Document behaviour changes: PostgreSQL now listens on localhost only (`postgresql_listen_addresses`,
     `postgresql_allowed_cidrs`); `nginx_stop_conflicting_services` defaults to false; speedtest scrape
     job disabled unless `prometheus_speedtest_exporter_host` is set; `ssh_password_authentication`
     is false in group_vars.
4. **Independent review wave.** Run adversarial reviewers per area (roles, playbooks, workflows, CLI,
   inventory) against `docs/CONVENTIONS.md`, verify each finding, fix confirmed ones. Where systemd is
   available (WSL with `systemd=true`), converge `common`, `nginx`, `node_exporter`, `promtail` and
   `firewall` for real and confirm the second run reports `changed=0`.
5. **Finish: one `main` branch.** Re-run every gate, commit, push, open a pull request from
   `claude/eloquent-mayer-k1lnlt` into `main`, merge it (squash is recommended: the branch carries
   many `WIP: checkpoint` commits), then delete the feature branch on the remote so only `main` remains.

## 3. Pitfalls discovered on the way | 已踩过的坑

- `ansible.cfg` uses `gathering = smart` with a one-hour fact cache, so `ansible_date_time` can be
  stale; anything that needs a fresh timestamp uses `now()` pinned once with `set_fact`
  (`roles/lifecycle`, `rollback.yml`). `ssh-config-force-apply.yml` style backups keyed on
  `ansible_date_time.epoch` have the same collision risk.
- `ansible.builtin.systemd` / `systemd_service` with only `name:` fails (`required_one_of`); read service
  state with `service_facts` or `systemctl show`/`is-active`.
- `.ansible-lint` `kinds` are matched in order; task-file globs must precede playbook globs.
- `\uXXXX` typed inside a Bash heredoc arrives as the real character; build such characters in Python
  with `chr()` or the repository tests flag them as mojibake/invisible characters.
- Ansible's native backup files are `<file>.<pid>.<YYYY-MM-DD@HH:MM:SS>~`, not `<file>.backup.*`.
- `lookup('env', 'X') | default('y')` returns `''` when `X` is unset; use `or 'y'` / `default('y', true)`.
