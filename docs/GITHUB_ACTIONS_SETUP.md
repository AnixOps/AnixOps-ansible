# GitHub Actions Setup | GitHub Actions 配置

How the workflows in `.github/workflows/` reach the fleet and what they need. The list of secret
names is in [GITHUB_SECRETS_REFERENCE.md](GITHUB_SECRETS_REFERENCE.md); operating procedures are in
[RUNBOOK.md](RUNBOOK.md).

## 1. Workflows | 工作流

| File | Name | Trigger | Environment | What it does |
|---|---|---|---|---|
| `ansible-ci.yml` | Ansible CI | pull request and push to `main`, manual | - | lint gate, pytest, `py_compile`, `bash -n` + shellcheck, inventory drift, `--syntax-check` of every playbook, localhost integration converge, verify and idempotency |
| `security-scan.yml` | Security Scan | pull request (`main`, `staging`), push to `main`, Monday 06:00 UTC, manual | - | TruffleHog (verified results), pip-audit, tracked keys / `.env` check, `ignore_errors` policy gate |
| `reusable-lint.yml` | Reusable Lint (job: Code Quality Check) | `workflow_call` | - | yamllint, ansible-lint (production profile, offline), backup coverage, encoding guard |
| `deploy.yml` | Deploy | manual, tag push `v*` | `NodeX` | run one playbook against a group, or the release deploy |
| `lifecycle.yml` | Lifecycle Management | manual | `NodeX` | `status`, `deploy`, `rollback`, `cleanup` of one role |
| `weekly-security-patch.yml` | Weekly Security Patch | Monday 04:00 UTC, manual | `NodeX` | Trivy scan, OS updates, backlog issue |
| `node-platform-deploy.yml` | Deploy AnixOps Node Platform | manual | `node-platform` | node platform stack on its own inventory |

The CI workflows (`ansible-ci.yml`, `security-scan.yml`, `reusable-lint.yml`) never read fleet
secrets and never touch production hosts.

## 2. One-time setup | 一次性配置

1. **Environments.** Create the GitHub Environments `NodeX` and `node-platform`
   (Settings, Environments). Add required reviewers to `NodeX` if production runs need an approval.
2. **Secrets.** Add at least `SSH_PRIVATE_KEY`, `ANSIBLE_USER`, `ANSIBLE_PORT` and one
   `<HOST>_V4_SSH` per host (`JP_1_V4_SSH`, `UK_1_V4_SSH`, `US_W_1_V4_SSH`, `SG_1_V4_SSH`,
   `HK_1_V4_SSH`, `UK_2_V4_SSH`, `FR_1_V4_SSH`, `PL_1_V4_SSH`), plus the service secrets for what you
   deploy (`GRAFANA_ADMIN_PASSWORD`, `V2BOARD_*`, ...). Repository secrets are visible to every job;
   environment secrets only to jobs of that environment.
3. **Key on the hosts.** The public half of `SSH_PRIVATE_KEY` must be in `authorized_keys` of
   `ANSIBLE_USER` on every host.
4. **Issues.** The weekly patch job needs permission to create issues (`issues: write` is
   declared in the workflow).

## 3. How a deploy job reaches the fleet | 部署任务如何连接主机

Every job that runs Ansible uses the same composite actions:

1. `./.github/actions/export-secrets` exports the allow-listed secrets (`toJSON(secrets)` filtered
   by name) into `GITHUB_ENV`; only names are logged.
2. `./.github/actions/setup-ansible` installs Python 3.11, `requirements.txt` and the Galaxy
   collections (retried), writes `SSH_PRIVATE_KEY` to `$RUNNER_TEMP/ssh/id_ansible`, exports
   `SSH_KEY_PATH` / `ANSIBLE_PRIVATE_KEY_FILE`, and renders the inventory with
   `python3 tools/generate_inventory.py github-actions --output $RUNNER_TEMP/ansible-inventory.yml`
   (exported as `ANSIBLE_INVENTORY`; the weekly patch job renders it in its own step). The
   committed `hosts.yml` is never overwritten.
3. The inventory reads each host address with `lookup('env', '<HOST>_V4_SSH')`, so a missing secret
   shows up as an unreachable host.
4. A final `if: always()` step shreds `$RUNNER_TEMP/ssh`, and `./.github/actions/job-summary` writes
   the step summary.

`node-platform-deploy.yml` is the exception: it maps its secrets explicitly in the job `env` (some
are renamed from shared names such as `SSL_CERTIFICATE_PEM`, `VULTR_API_KEY`, `SMTP_*`) and uses
`inventories/production/node-platform.actions.yml`.

## 4. Deploy workflow | 部署工作流

Manual run inputs:

| Input | Type | Meaning |
|---|---|---|
| `playbook` | choice | `provision/site.yml` (default), `provision/quick-setup.yml`, `provision/web-servers.yml`, `maintenance/health-check.yml`, `maintenance/firewall-setup.yml`, `maintenance/lifecycle.yml`, `maintenance/emergency-cleanup.yml` |
| `target_group` | choice | `all` (default), `web_servers`, `proxy_servers`, `observability`, `dev_servers`, `v2bx_servers`, `v2board_servers`, `postgres_servers` |
| `limit_hosts` | string | optional comma-separated host names (`jp-1,uk-1`); every host must be a member of `target_group` or the job fails |
| `tags` | string | optional comma-separated play tags (`nginx,firewall`) |
| `dry_run` | boolean | `--check --diff` |
| `verbosity` | choice | `v` (default), `vv`, `vvv` |
| `confirm` | string | must be `deploy` for a real deploy to `target_group=all` |

Steps: validate inputs, resolve the limit inside `target_group`, syntax-check the playbook, ping the
limit, run the playbook, then run `maintenance/health-check.yml` on the same limit (not for dry runs
or when the selected playbook is the health check).

**Tag-push release deploy.** `git tag v0.3.0 && git push origin v0.3.0` runs:

1. `lint` (the reusable lint workflow);
2. `deploy-tag`, a matrix over the `site.yml` play tags in dependency order: `common`,
   `node_exporter`, `promtail`, `firewall`, `nginx`, `prometheus`, `loki`, `grafana`, `postgresql`,
   `v2board`, `v2bx`, `speedtest`, with `max-parallel: 1` and `fail-fast: false`;
3. `health-check-tag`, a fleet-wide `maintenance/health-check.yml` run (unless the workflow was
   cancelled), with the deploy result in its summary.

## 5. Lifecycle Management workflow | 生命周期工作流

| Input | Meaning |
|---|---|
| `action` | `status` (default), `deploy`, `rollback`, `cleanup` |
| `role` | `common`, `nginx`, `node_exporter`, `promtail`, `prometheus`, `loki`, `grafana`, `postgresql`, `v2board`, `v2bx`, `speedtest`, `firewall`, `acme_ssl` |
| `version` | rollback target: `prev` (default), `initial` or `vYYYYMMDDTHHMMSS` |
| `target_group` | a group or a single host (`jp-1`, `uk-1`, `us-w-1`, `sg-1`, `hk-1`, `uk-2`, `pl-1`, `fr-1`) |
| `force` | confirms a group-wide rollback or cleanup: required for `target_group=all`, needed for any multi-host target, and passed to the playbook as `-e lifecycle_confirm_all=true` (cleanup also gets `cleanup_force=yes`) |
| `keep_backups` | snapshot versions kept by cleanup (default 5) |

`deploy` of `postgresql`, `v2bx` and `speedtest` runs the matching `site.yml` tag, and `v2board` runs
`postgresql,v2board`; every other action goes through `playbooks/maintenance/lifecycle.yml`. A health
check follows `deploy` and `rollback`.

## 6. Weekly Security Patch workflow | 每周安全补丁

Scheduled runs patch `all` with updates applied and the inventory's reboot policy. Manual inputs:

| Input | Meaning |
|---|---|
| `target_group` | group to patch (`localhost` is added to the limit for the report play) |
| `apply_updates` | `false` = scan and report only |
| `allow_reboot` | `inventory` (default) keeps each host's or group's `security_patch_allow_reboot`; `true` / `false` override it with `-e security_patch_allow_reboot=...` |

Details, report schema and the backlog-issue runbook: [SECURITY_PATCHING.md](SECURITY_PATCHING.md).

## 7. Node platform workflow | 节点平台工作流

Inputs: `domain` (public hostname, mapped to `ANIXOPS_NODE_PLATFORM_DOMAIN` and
`ANIXOPS_NODE_PLATFORM_SERVER_NAME`), `dry_run`, and `force_https` (`ANIXOPS_NODE_PLATFORM_FORCE_HTTPS`:
answer port 80 with a redirect to HTTPS; needs SSL enabled, keep it off during HTTP-01 ACME). See
[ANIXOPS_NODE_PLATFORM.md](ANIXOPS_NODE_PLATFORM.md).

## 8. Concurrency | 并发控制

| Group | Workflows | Policy |
|---|---|---|
| `deploy-NodeX-<target_group>` | `deploy.yml`, `lifecycle.yml`, `weekly-security-patch.yml` | queue; a running job is never cancelled |
| `deploy-node-platform` | `node-platform-deploy.yml` | queue; never cancelled |
| `ci-<workflow>-<ref>`, `security-<workflow>-<ref>` | CI and security scan | a newer push cancels the running check |

## 9. Local development vs. CI | 本地与 CI 的区别

| | Local | GitHub Actions |
|---|---|---|
| Host addresses and secrets | `.env` (loaded by `scripts/anixops.sh`) | repository / environment secrets |
| SSH key | `SSH_KEY_PATH` (default `~/.ssh/id_rsa`) | `SSH_PRIVATE_KEY`, written to `$RUNNER_TEMP/ssh` |
| Inventory | committed `inventories/production/hosts.yml` | rendered into `$RUNNER_TEMP` from `servers-config.yml` |
| Entry point | `make <target>` / `scripts/anixops.sh` | the workflows above |
