# postgresql role | PostgreSQL 角色

Installs and hardens a PostgreSQL server for the v2board control panel:
distribution packages (or the official PGDG repository on request), a
rollback-safe `postgresql.conf` / `pg_hba.conf`, scram-sha-256 only access for
the application role, memory tuning derived from the host RAM and an optional
daily logical backup.

为 v2board 安装并加固 PostgreSQL：安全认证、按内存自动调优、配置失败自动回滚、可选逻辑备份。

## Behaviour | 行为

1. **Install** `postgresql-<version>` + client from the distribution. When the
   distribution lacks the version, set `postgresql_use_pgdg: true`: the PGDG
   key is downloaded to `/etc/apt/keyrings/postgresql.asc` and a signed
   `deb822` source is added (no `apt-key`, no shell hacks). A **missing**
   cluster is created with `pg_createcluster` (data checksums on); an existing
   cluster is never dropped or recreated, whatever its state.
2. **Configure** `postgresql.conf` and `pg_hba.conf` (templates with
   `backup: true`, owned by `postgres`), `meta: flush_handlers`, then wait for
   `pg_isready` with retries. If the instance does not come back the backups
   are restored, the instance restarted and the play fails with the journal
   and cluster-log tail.
3. **Provision** the application role and database. Every write is guarded by
   a read-only `SELECT` so a second run is `changed=0`. The password is only
   (re)set when a login test with the configured password fails, which also
   migrates legacy `md5` verifiers to `scram-sha-256`.
4. **Backup** (optional) a daily `pg_dump --format=custom` plus
   `pg_dumpall --globals-only` via cron as `postgres`, with retention.
5. **Verify** the instance is `active`, `pg_isready` succeeds and the
   application role can log in over the Unix socket and (by default) TCP.

### Access model | 访问模型

```
local  <db>  <user>            scram-sha-256   # application role via Unix socket (password)
local  all   postgres          peer            # administration as the postgres OS user
local  all   all               peer
host   <db>  <user>  <cidr>    scram-sha-256   # one line per postgresql_allowed_cidrs entry
host   all   all     0.0.0.0/0 reject
host   all   all     ::/0      reject
```

`listen_addresses` defaults to `localhost`; `password_encryption` is
`scram-sha-256`. Super-user access is local only (`sudo -u postgres psql`).

## Variables | 变量

| Variable | Default | Notes |
|----------|---------|-------|
| `postgresql_version` | `"15"` | distro package version |
| `postgresql_use_pgdg` | `false` | add the PGDG repository (deb822 + keyring) |
| `postgresql_listen_addresses` | `localhost` | e.g. `localhost,100.96.0.5` |
| `postgresql_port` | `5432` | |
| `postgresql_allowed_cidrs` | `["127.0.0.1/32", "::1/128"]` | networks allowed for the application role |
| `postgresql_extra_hba_rules` | `[]` | raw `pg_hba.conf` lines appended before the reject rules |
| `postgresql_password_encryption` | `scram-sha-256` | |
| `postgresql_ssl_enabled` | `true` | uses the Debian snakeoil certificate when present |
| `postgresql_user` / `postgresql_database` | env `V2BOARD_PG_USER` / `V2BOARD_PG_DATABASE`, default `v2board` | |
| `postgresql_password` | env `V2BOARD_PG_PASSWORD` (required) | |
| `postgresql_max_connections` | `100` | |
| `postgresql_shared_buffers` | 25 % of `ansible_memtotal_mb` (min 128MB) | |
| `postgresql_effective_cache_size` | 75 % of RAM (min 384MB) | |
| `postgresql_work_mem` / `postgresql_maintenance_work_mem` | `4MB` / `64MB` | |
| `postgresql_wal_level`, `postgresql_min_wal_size`, `postgresql_max_wal_size` | `replica`, `80MB`, `1GB` | |
| `postgresql_extra_settings` | `{}` | extra `key = value` pairs appended to `postgresql.conf` |
| `postgresql_timezone` / `postgresql_locale` | global `timezone` / `locale` | fall back to `Asia/Shanghai` / `en_US.UTF-8` |
| `postgresql_backup_enabled` | `false` | daily `pg_dump` cron |
| `postgresql_backup_dir` | `/var/backups/postgresql` | |
| `postgresql_backup_hour` / `postgresql_backup_minute` | `3` / `17` | |
| `postgresql_backup_retention_days` | `7` | |
| `postgresql_verify_tcp` | `true` | TCP login test over 127.0.0.1 |

### Lifecycle contract | 生命周期契约

`postgresql_port`, `postgresql_health_url` (empty: no HTTP endpoint),
`postgresql_backup_files` (`postgresql.conf`, `pg_hba.conf`),
`postgresql_config_dirs`, `postgresql_packages`, `postgresql_service_name`
(`postgresql`; the instance unit is `postgresql@<version>-main`).

## Secrets handling | 密钥处理

* `V2BOARD_PG_PASSWORD` is never passed on a command line: SQL is fed through
  stdin and login tests use `PGPASSWORD` in the task environment. All such
  tasks run with `no_log: true`.
* The same value must be exported when deploying `roles/v2board`.

## Verification | 验证

```bash
pg_lsclusters
systemctl status postgresql@15-main
sudo -u postgres pg_isready -h /var/run/postgresql -p 5432
PGPASSWORD="$V2BOARD_PG_PASSWORD" psql -h 127.0.0.1 -U v2board -d v2board -c 'SELECT 1'
sudo -u postgres psql -c 'SHOW listen_addresses' -c 'SHOW shared_buffers' -c 'SHOW password_encryption'
tail -n 50 /var/log/postgresql/postgresql-15-main.log
ls -l /var/backups/postgresql/          # when postgresql_backup_enabled
```

## Rollback and restore | 回滚与恢复

**Configuration**: a failed `pg_isready` after a config change restores the
`.backup` files produced by the template tasks and restarts the instance
automatically. Manual rollback:

```bash
cp /etc/postgresql/15/main/postgresql.conf.<timestamp>~ /etc/postgresql/15/main/postgresql.conf
cp /etc/postgresql/15/main/pg_hba.conf.<timestamp>~     /etc/postgresql/15/main/pg_hba.conf
systemctl restart postgresql@15-main
```

**Data (from a logical backup)**:

```bash
# roles / global objects
sudo -u postgres psql -f /var/backups/postgresql/globals-<stamp>.sql
# database: drop and recreate, then restore the custom-format dump
sudo -u postgres psql -c 'DROP DATABASE v2board' -c 'CREATE DATABASE v2board OWNER v2board'
sudo -u postgres pg_restore -d v2board --no-owner --role=v2board /var/backups/postgresql/v2board-<stamp>.dump
```

**Package downgrade / version change**: this role never removes a cluster. To
move to another major version create the new cluster with
`postgresql_version`, dump from the old one and `pg_restore` into the new one,
then drop the old cluster manually with `pg_dropcluster`.
