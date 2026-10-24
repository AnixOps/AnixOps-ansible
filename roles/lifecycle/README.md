# Lifecycle role | 生命周期管理

Unified deploy / rollback / status / cleanup hooks for every service role, with
versioned snapshot directories and JSON state + history per role and host.
统一的服务生命周期管理：部署前后快照、回滚、状态查询与清理。

Two rollback mechanisms exist in this repository; they are complementary:

| Mechanism | What it restores | Entry point |
|---|---|---|
| **lifecycle role** (this role) | Whole deployment versions: every `<role>_backup_files` file as recorded in a manifest, state/history kept | `playbooks/maintenance/lifecycle.yml --tags rollback` |
| **file-level rollback** | The `<file>.<pid>.<date>~` / `<file>.backup.*` copies that `backup: true` leaves next to each templated file | `playbooks/maintenance/rollback.yml` |

## Role contract | 角色约定

Every service role defines these variables in its `defaults/main.yml`; the lifecycle
role loads them automatically (see *How the contract is loaded*).

| Variable | Type | Used by | Meaning |
|---|---|---|---|
| `<role>_service_name` | string | all hooks | systemd unit to probe/stop/restart. Empty string = no service. Default: `<role>` |
| `<role>_port` | int | post_deploy, post_rollback | TCP port waited for on 127.0.0.1 (`0` = skip) |
| `<role>_health_url` | string | post_deploy, post_rollback | HTTP URL that must answer 200/204. A relative path is prefixed with `http://localhost:<port>`; empty = skip |
| `<role>_backup_files` | list | pre_deploy, post_deploy, post_rollback | Absolute paths snapshotted before and after a deployment (systemd units, sshd_config ... anywhere, not only `/etc/<role>`) |
| `<role>_config_dirs` | list | cleanup | Directories archived (and removed when `cleanup_keep_data=false`) |
| `<role>_packages` | list | cleanup (fallback) | Packages removed by cleanup when `<role>_cleanup_packages` is undefined |
| `<role>_cleanup_packages` | list | cleanup | Packages removed by cleanup (preferred over `<role>_packages`, which may be a base install list) |

## Hooks | Hook 说明

| Hook | What it does |
|---|---|
| `pre_deploy` | Creates `<backup_root>/<YYYYMMDDTHHMMSS>/pre/` with every existing contract file (`NN-<basename>`) plus `manifest.json` (original path, owner, group, mode), records the service state, prunes versions older than `lifecycle_hooks_backup_retention_days` while keeping the newest `lifecycle_hooks_backup_min_keep` |
| `post_deploy` | Snapshots the same files into `<version>/post/`, waits for the port, probes systemd, polls the health URL (retries), writes `<role>_state.json` and appends to `<role>_history.json`, notifies, and **fails in strict mode when the service is unhealthy** (after recording the failure) |
| `pre_rollback` | Records the current version and service state (fact + `<role>_pre_rollback.json`), optionally stops the service (`hooks_graceful_stop`) |
| `post_rollback` | Resolves the target (below), snapshots the files about to be overwritten into `<backup_root>/<ts>-pre-rollback/`, restores the target snapshot to the **original paths from its manifest**, runs the config validators, reverts on any error, reloads systemd if unit files changed, restarts the service, verifies health, updates state/history, notifies |
| `status` | Read-only summary: version, service state, recent history, snapshot count, contract |
| `cleanup` | Requires `cleanup_confirm=yes`; stops/disables the service, removes `<role>_cleanup_packages`, archives the config dirs (`community.general.archive`), removes them only when `cleanup_keep_data=false`, keeps the newest `cleanup_keep_backups` snapshot versions, removes a role-owned unit file and the state files. **`common` can never be cleaned up** (host keys, base packages) |

### Backup layout | 备份目录结构

```
/var/backups/<role>/
├── 20260426T120000/            # version v20260426T120000
│   ├── pre/                    # configuration BEFORE this deployment
│   │   ├── 00-nginx.conf
│   │   ├── 01-default
│   │   └── manifest.json       # {"files":[{"stored":"00-nginx.conf","original":"/etc/nginx/nginx.conf",...}]}
│   └── post/                   # configuration right AFTER this deployment
└── 20260427T090000-pre-rollback/   # safety snapshot taken by post_rollback
/var/lib/anixops/state/
├── <role>_state.json           # current version / status / backup_location
├── <role>_history.json         # one record per deployment or rollback
├── <role>_pre_deploy.json
└── <role>_pre_rollback.json
```

### Rollback target resolution | 回滚目标

Record *N* = deployment *N*: `pre/` holds the configuration from **before** it,
`post/` the configuration right **after** it.

| `lifecycle_version` | Restores | Fallback |
|---|---|---|
| `prev` (default) | `post/` of the deployment before the current one (`state.current_version`) | `pre/` of the current deployment (identical content) |
| `initial` | `pre/` of the first recorded deployment | – |
| `v<YYYYMMDDTHHMMSS>` | `post/` of that deployment | `pre/` of the following deployment |
| `lifecycle_restore_from=/abs/dir` | that snapshot directory (e.g. a `*-pre-rollback` safety snapshot) | – |

Repeating `prev` walks further back through the history; an explicit version rolls
forward again. Fewer than two usable records or an unknown version fail with a clear
message listing what is available. Directories written by the pre-manifest version of
this role are refused unless `lifecycle_rollback_allow_legacy=true`.

## Hook sequences | 执行顺序

```
deploy   (lifecycle.yml --tags deploy)
  lifecycle: pre_deploy ──► snapshot <ts>/pre + manifest ──► record service state ──► prune old versions
  include_role: <role>  ──► the service role deploys (its own handlers/validate/rescue)
  lifecycle: post_deploy ─► snapshot <ts>/post ──► wait port ──► probe systemd ──► poll health URL
                           ──► write state + history ──► notify ──► FAIL if unhealthy (strict)

rollback (lifecycle.yml --tags rollback)
  lifecycle: pre_rollback ─► read state ──► probe systemd ──► write pre_rollback.json [──► stop svc]
  lifecycle: post_rollback ► resolve target ──► snapshot current files (<ts>-pre-rollback)
      ┌─ block ──► restore manifest files to original paths ──► validators (nginx -t, sshd -t, promtool)
      └─ rescue ─► put pre-rollback snapshot back ──► fail
      ──► daemon-reload (if units) ──► restart service ──► wait port / health ──► state + history ──► notify
      ──► FAIL if unhealthy (strict; set lifecycle_rollback_revert_on_unhealthy=true to also revert)

cleanup  (lifecycle.yml --tags cleanup, cleanup_confirm=yes)
  refuse protected roles ──► stop/disable ──► remove packages ──► archive config dirs [──► remove]
  ──► prune snapshots beyond keep ──► remove unit ──► remove state files ──► notify
```

## How the contract is loaded | 约定变量如何载入

`tasks/main.yml` includes the target role with
`include_role: name=<role> public=true apply: {when: false}`. The role's `defaults`
and `vars` become visible to the play while **none of its tasks run** (every task,
nested include and `meta` is skipped). Inventory values still win because role
defaults have the lowest precedence. Set `lifecycle_load_target_defaults=false` if the
contract variables are provided by the inventory instead.

## Variables | 变量

All knobs are prefixed `lifecycle_`; the old un-prefixed names stay valid as fallbacks
so existing `-e` flags from `scripts/anixops.sh` and the GitHub workflow keep working.

| Variable (fallback) | Default | Purpose |
|---|---|---|
| `lifecycle_target_role` | – | **required**, service role name |
| `lifecycle_hook` (`lifecycle_hook_type`) | – | **required** when the role is used directly; `lifecycle.yml` sets it per action tag |
| `lifecycle_version` | `prev` | rollback target, see above |
| `lifecycle_restore_from` | `""` | snapshot dir to restore, bypassing the history |
| `lifecycle_dry_run` (`hooks_dry_run`) | `false` | rollback/cleanup print their plan and stop |
| `lifecycle_state_dir` (`state_dir`) | `/var/lib/anixops/state` | state/history location |
| `lifecycle_hooks_backup_base_dir` (`hooks_backup_base_dir`) | `/var/backups` | snapshot root (`<base>/<role>/`) |
| `lifecycle_hooks_backup_retention_days` (`hooks_backup_retention_days`) | `30` | age-based pruning in pre_deploy (0 = off) |
| `lifecycle_hooks_backup_min_keep` | `3` | versions never pruned by age |
| `lifecycle_hooks_verify_enabled` (`hooks_verify_enabled`) | `true` | run port/health verification |
| `lifecycle_hooks_verify_strict` | `true` | fail post_deploy/post_rollback when unhealthy |
| `lifecycle_hooks_verify_retries/_delay/_timeout` (`hooks_verify_*`) | `6` / `5` / `30` | health polling |
| `lifecycle_hooks_verify_status_codes` | `[200, 204]` | accepted health codes |
| `lifecycle_hooks_graceful_stop` (`hooks_graceful_stop`) | `false` | stop the service in pre_rollback |
| `lifecycle_rollback_allow_legacy` | `false` | restore manifest-less dirs into `/etc/<role>/` |
| `lifecycle_rollback_revert_on_unhealthy` | `false` | revert when the rolled-back service is unhealthy |
| `lifecycle_validators` | nginx/acme_ssl/common/prometheus | `{role: [{bin, argv}]}` run after restore |
| `lifecycle_notification_webhook_url` (`notification_webhook_url`, env `NOTIFICATION_WEBHOOK_URL`) | `""` | JSON POST per event, `no_log`, never fails the play |
| `lifecycle_notification_slack_url` (`notification_slack_url`, env `SLACK_WEBHOOK_URL`) | `""` | Slack text message |
| `lifecycle_cleanup_confirm` (`cleanup_confirm`) | `false` | must be `yes`/`true` for cleanup |
| `lifecycle_cleanup_force` (`cleanup_force`) | `false` | confirm + continue past archive/package errors |
| `lifecycle_cleanup_strategy` (`cleanup_strategy`) | `conservative` | `aggressive` removes config dirs and packages regardless of keep flags |
| `lifecycle_cleanup_keep_data` (`cleanup_keep_data`) | `true` | keep config dirs (they are archived either way) |
| `lifecycle_cleanup_keep_package` (`cleanup_keep_package`) | `false` | keep packages |
| `lifecycle_cleanup_keep_backups` (`cleanup_keep_backups`) | `5` | snapshot versions kept by cleanup |
| `lifecycle_cleanup_archive_path` (`cleanup_archive_path`) | `/var/lib/anixops/archive` | tar.gz destination |
| `lifecycle_cleanup_protected_roles` | `[]` | extra roles that may never be cleaned up (`common` always is) |
| `lifecycle_serial` / `lifecycle_max_fail` / `lifecycle_max_hosts` | `1` / `0` / `1` | consumed by `playbooks/maintenance/lifecycle.yml` |

## Examples | 示例

```bash
# Status of nginx on every host
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx --tags status

# Deploy prometheus with pre/post snapshots, one host at a time, stop on first failure
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=prometheus \
  --tags deploy --limit observability

# Roll nginx back to the previous version on one host (dry run first)
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx \
  -e lifecycle_dry_run=true --tags rollback --limit jp-1
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx \
  -e lifecycle_version=prev --tags rollback --limit jp-1

# Roll forward to a specific version
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx \
  -e lifecycle_version=v20260426T120000 --tags rollback --limit jp-1

# Undo a rollback from its safety snapshot
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=nginx \
  -e lifecycle_restore_from=/var/backups/nginx/20260427T090000-pre-rollback --tags rollback --limit jp-1

# Clean up loki on one host, keep the 10 newest snapshot versions
ansible-playbook playbooks/maintenance/lifecycle.yml -e lifecycle_target_role=loki \
  -e cleanup_confirm=yes -e cleanup_keep_backups=10 --tags cleanup --limit jp-1

# Use the role directly inside another play
- role: lifecycle
  vars:
    lifecycle_target_role: nginx
    lifecycle_hook: post_deploy
```

Rollback and cleanup refuse to run on more than `lifecycle_max_hosts` (1) hosts unless
`-e lifecycle_confirm_all=true` is given; `deploy` and `status` are limited only by
`--limit`, `serial` (1) and `max_fail_percentage` (0).

## Verification | 验证

* `--tags status` shows the recorded version and the live systemd state.
* After deploy/rollback: `cat /var/lib/anixops/state/<role>_state.json`,
  `python3 -m json.tool /var/lib/anixops/state/<role>_history.json`.
* Snapshot content: `cat /var/backups/<role>/<version>/post/manifest.json`.
