# common

Base configuration and hardening for every managed server | 所有服务器的基础配置与安全加固。

The role is the first thing `site.yml` / `quick-setup.yml` run on a host. It is
idempotent (a second run reports `changed=0`), fails loudly instead of hiding
errors, and rolls back the SSH / chrony / fail2ban configuration automatically
when a new configuration does not pass verification.

## What the role does | 功能

Task files run in this order (`tasks/main.yml`); every optional stage has a
`common_manage_*` toggle.

| Stage | File | What happens |
|---|---|---|
| preflight | `preflight.yml` | Gathers minimal facts if missing, asserts the OS family is Debian or RedHat, validates variable shapes, records `common_ssh_service_name` once. |
| packages | `packages.yml` | apt cache refresh (`cache_valid_time`, `lock_timeout: 300`, retries) and base package install; `dnf` on RedHat. No third-party repository hacks (see below). |
| hostname | `hostname.yml` | Sets the hostname from `inventory_hostname` and the `127.0.1.1` line in `/etc/hosts`. Skipped for `localhost`/`127.0.0.1`. |
| time | `time.yml` | Timezone (`community.general.timezone`), locale (`community.general.locale_gen`, Debian only), chrony installed, `chrony.conf` templated with backup + validation, verified with `chronyc tracking`. |
| users | `users.yml` | Admin users with shell, sudo group (`sudo` / `wheel`), optional `authorized_keys`, optional validated `NOPASSWD` sudoers drop-in. |
| ssh | `ssh.yml` | Switches Ubuntu `ssh.socket` activation to `ssh.service` (so `Port` is honoured), templates `sshd_config` (validated with `sshd -t`), restarts, then verifies sshd answers on `common_ssh_port`; restores the backup on failure. |
| sysctl | `sysctl.yml` | Applies `common_sysctl` to `/etc/sysctl.conf` and reloads. |
| limits | `limits.yml` | Applies `security.limits` through `community.general.pam_limits`. |
| fail2ban | `fail2ban.yml` | Only when `security.fail2ban_enabled` is true: install, template `jail.local` (journald backend), `fail2ban-client -t`, restart, `fail2ban-client ping`; restores the backup on failure. |
| services | `services.yml` | Stops and disables `avahi-daemon` / `cups` (service, socket and path units) only when the unit exists, using `service_facts` instead of `ignore_errors`. |

### Config roll-out pattern (stability) | 配置下发模式

For `sshd_config`, `chrony.conf` and `jail.local` the role follows the same
pattern:

1. `template` with `backup: true` (and `validate:` where the daemon has a
   syntax checker: `sshd -t -f %s`, `chronyd -p -f %s`), notifying the restart
   handler.
2. `meta: flush_handlers` so the restart happens immediately.
3. Verify the service: `sshd -t` plus a TCP banner check on
   `common_ssh_port` from the controller (`wait_for` with `search_regex:
   SSH-2.0-`), `chronyc tracking`, `fail2ban-client ping`.
4. `rescue`: copy the `.backup_file` produced in step 1 back into place,
   restart the service, then `fail` with a message that names the restored
   backup.

With `serial: 30%` and `max_fail_percentage: 25` in the playbooks this means a
bad SSH change can never lock you out of a whole fleet: the first batch
restores its old configuration and the play stops.

## Variables | 变量

All role variables start with `common_`. Where a global key exists in
`inventories/production/group_vars/all/main.yml` the role default falls back
to it, so **operators keep editing the global keys** (they are not renamed).

### Global keys consumed through fallbacks

| Role variable | Falls back to | Default when the global is absent |
|---|---|---|
| `common_timezone` | `timezone` | `Asia/Shanghai` |
| `common_locale` | `locale` | `en_US.UTF-8` |
| `common_packages` | (it *is* the global key) | `curl wget vim htop git unzip tar chrony` |
| `common_ntp_servers` | `ntp_servers` | `0.pool.ntp.org`, `1.pool.ntp.org` |
| `common_ssh_port` | `ssh_port` | `22` |
| `common_ssh_allow_root` | `ssh_allow_root` | `true` |
| `common_ssh_password_authentication` | `ssh_password_authentication` | `true` (set the global to `false` once keys are deployed) |
| `common_ssh_pubkey_authentication` | `ssh_pubkey_authentication` | `true` |
| `common_admin_users` | `admin_users` | `[]` |
| `common_security` | `security` | `{}` |
| `common_security_limits` | `security.limits` | `[]` |
| `common_fail2ban_enabled` | `security.fail2ban_enabled` | `false` |
| `common_fail2ban_ban_time` | `security.fail2ban_ban_time` | `3600` |
| `common_fail2ban_find_time` | `security.fail2ban_find_time` | `600` |
| `common_fail2ban_max_retry` | `security.fail2ban_max_retry` | `5` |
| `common_sysctl` | `sysctl_config` | `{}` |

### Feature toggles

| Variable | Default | Purpose |
|---|---|---|
| `common_manage_hostname` | `true` | Hostname + `/etc/hosts` |
| `common_manage_packages` | `true` | Cache refresh + base packages |
| `common_manage_time` | `true` | Timezone, locale, chrony |
| `common_manage_users` | `true` | Admin users |
| `common_manage_ssh` | `true` | sshd hardening |
| `common_manage_sysctl` | `true` | Kernel parameters |
| `common_manage_limits` | `true` | PAM limits |
| `common_manage_fail2ban` | `true` | fail2ban (also needs `security.fail2ban_enabled`) |
| `common_manage_services` | `true` | Disable unneeded services |

### Packages

| Variable | Default | Purpose |
|---|---|---|
| `common_refresh_apt_cache` | `true` | Run `apt-get update` (escape hatch when a third-party repo is broken) |
| `common_apt_cache_valid_time` | `3600` | Skip the refresh when the cache is younger than this (seconds) |
| `common_apt_lock_timeout` | `300` | Seconds to wait for the dpkg/apt lock |
| `common_package_retries` / `common_package_retry_delay` | `5` / `10` | Retry budget for every package operation |

### Hostname

| Variable | Default | Purpose |
|---|---|---|
| `common_hostname` | `{{ inventory_hostname }}` | Hostname to apply |
| `common_hostname_skip_list` | `[localhost, 127.0.0.1]` | Names that are never applied (local runs) |

### Time

| Variable | Default | Purpose |
|---|---|---|
| `common_locale_packages` | `[locales]` | Installed on Debian before `locale_gen` |
| `common_ntp_pools` | `[]` | Extra `pool` directives |
| `common_chrony_package` | `chrony` | Package name |
| `common_chrony_service_name` | `chrony` / `chronyd` | OS-aware service name |
| `common_chrony_conf_path` | `/etc/chrony/chrony.conf` / `/etc/chrony.conf` | OS-aware config path |
| `common_chrony_validate_cmd` | `/usr/sbin/chronyd -p -f %s` on Debian, `""` on RedHat | Set to `""` to skip validation (chrony < 4.0) |
| `common_chrony_makestep` | `1.0 3` | `makestep` directive |
| `common_chrony_extra_config` | `""` | Raw lines appended to `chrony.conf` |

### Admin users

Each `common_admin_users` item: `name` (required), `shell`, `state`
(`present`/`absent`), `groups` (default `[sudo]` or `[wheel]`),
`authorized_keys` (list of public key strings), `authorized_keys_exclusive`
(remove keys that are not in the list), `remove` (delete the home directory
when `state: absent`). Passwords are intentionally not managed.

| Variable | Default | Purpose |
|---|---|---|
| `common_admin_default_shell` | `/bin/bash` | Shell when the item has none |
| `common_sudo_group` | `sudo` / `wheel` | OS-aware sudo group |
| `common_admin_sudo_nopasswd` | `false` | Write a `visudo`-validated `NOPASSWD:ALL` drop-in for present users |
| `common_admin_sudoers_file` | `/etc/sudoers.d/90-common-admins` | Drop-in path (removed when the toggle is false) |

```yaml
admin_users:
  - name: ops
    shell: /bin/bash
    state: present
    authorized_keys:
      - "ssh-ed25519 AAAA... ops@laptop"
```

### SSH

| Variable | Default | Purpose |
|---|---|---|
| `common_ssh_address_family` | `any` | `AddressFamily` |
| `common_ssh_listen_addresses` | `["0.0.0.0"]` | `ListenAddress` lines; `[]` = all addresses |
| `common_ssh_allow_users` / `common_ssh_allow_groups` | `[]` | `AllowUsers` / `AllowGroups` when non-empty |
| `common_ssh_login_grace_time` | `30` | `LoginGraceTime` |
| `common_ssh_max_auth_tries` | `3` | `MaxAuthTries` |
| `common_ssh_max_sessions` | `10` | `MaxSessions` |
| `common_ssh_max_startups` | `10:30:60` | `MaxStartups` |
| `common_ssh_client_alive_interval` / `common_ssh_client_alive_count_max` | `300` / `2` | Keep-alive |
| `common_ssh_allow_tcp_forwarding` | `true` | `AllowTcpForwarding` |
| `common_ssh_allow_agent_forwarding` | `false` | `AllowAgentForwarding` |
| `common_ssh_x11_forwarding` | `false` | `X11Forwarding` |
| `common_ssh_use_dns` | `false` | `UseDNS` |
| `common_ssh_log_level` | `INFO` | `LogLevel` |
| `common_ssh_banner` | `none` | `Banner` |
| `common_ssh_kex_algorithms` / `common_ssh_ciphers` / `common_ssh_macs` | hardened lists | Algorithm allow-lists |
| `common_ssh_sftp_server_path` | `/usr/lib/openssh/sftp-server` / `/usr/libexec/openssh/sftp-server` | OS-aware sftp subsystem |
| `common_ssh_extra_config` | `""` | Raw lines appended (e.g. `Match` blocks) |
| `common_ssh_disable_socket_activation` | `true` | Ubuntu 22.10+: switch `ssh.socket` to `ssh.service` so `Port` works |
| `common_ssh_verify_from_controller` | `true` | Verify from the controller (`false` = check `127.0.0.1` on the host, for bastion setups) |
| `common_ssh_verify_host` | `ansible_host` | Address the controller connects to during verification |
| `common_ssh_verify_timeout` / `_retries` / `_delay` | `30` / `3` / `5` | Verification budget |

Notes:

* `/etc/ssh/sshd_config.d/*.conf` is **not** included. Ubuntu cloud images
  ship `50-cloud-init.conf` with `PasswordAuthentication yes`, which would
  silently override the hardened settings. The templated file is the single
  source of truth.
* The template no longer contains a timestamp, so it is idempotent.
* Changing `ssh_port`: run once with the old `ansible_port`, let the role
  verify the new port, then update the inventory. If the controller cannot
  reach the new port the role restores the previous configuration and fails.
* The template needs the role's defaults. Playbooks that want to re-apply it
  should use `ansible.builtin.include_role: name: common` with
  `tasks_from: ssh.yml` instead of templating the file directly.

### Kernel parameters and limits

| Variable | Default | Purpose |
|---|---|---|
| `common_sysctl_file` | `/etc/sysctl.conf` | Where keys are persisted (kept for backward compatibility) |
| `common_sysctl_ignore_unknown_keys` | `true` | `sysctl -e`: keys missing in containers do not abort the run |
| `common_limits_file` | `/etc/security/limits.conf` | `pam_limits` destination |

### fail2ban

| Variable | Default | Purpose |
|---|---|---|
| `common_fail2ban_ignore_ips` | `[127.0.0.1/8, ::1]` | Never banned; add your controller / office IPs |
| `common_fail2ban_backend` | `systemd` | journald backend; works on Debian 12+ without rsyslog |
| `common_fail2ban_banaction` | `""` | Empty keeps the distribution default (nftables on Debian 12) |
| `common_fail2ban_dest_email` | `root@localhost` | `destemail` |
| `common_fail2ban_packages` | `[fail2ban, python3-systemd]` / `[fail2ban]` | OS-aware package list (RedHat needs EPEL) |
| `common_fail2ban_extra_jails` | `""` | Raw INI appended to `jail.local` |
| `common_fail2ban_verify_retries` / `_delay` | `5` / `3` | `fail2ban-client ping` budget |

### Services

| Variable | Default | Purpose |
|---|---|---|
| `common_disable_services` | `[avahi-daemon, cups]` | Stopped and disabled when the unit exists |

### Lifecycle contract (`roles/lifecycle`)

| Variable | Value |
|---|---|
| `common_port` | `common_ssh_port` |
| `common_health_url` | `""` (no HTTP endpoint) |
| `common_service_name` | `ssh` / `sshd` |
| `common_backup_files` | `sshd_config`, chrony config, `jail.local`, `sysctl.conf`, `limits.conf` |
| `common_config_dirs` | `/etc/ssh`, `/etc/chrony`, `/etc/fail2ban` |
| `common_cleanup_packages` | `[]` |

**Nuance:** the generic contract key `<role>_packages` means "packages to
remove on cleanup", but `common_packages` is the long-standing global
*install* list (it contains `python3`, `curl`, `chrony`...). It is therefore
kept as the install list and the removal list is the separate, empty
`common_cleanup_packages`. Never run the lifecycle `cleanup` hook against
`common`: removing its packages or `/etc/ssh` would destroy the host.

## Repository hygiene | 软件源

The old role deleted Grafana apt sources before refreshing the cache. That
logic was removed: a third-party repository is owned by the role that adds it
(`roles/grafana` removes the unsigned `grafana.list` and re-adds a `signed-by`
source). If `apt-get update` fails because of a foreign repository, fix it in
that role; `common_refresh_apt_cache: false` is the temporary escape hatch.

## Usage | 用法

```yaml
- name: Base configuration
  hosts: all
  become: true
  serial: "30%"
  max_fail_percentage: 25
  roles:
    - common
```

Tags: `common` plus one per stage (`common_packages`, `common_ssh`,
`common_time`, `common_users`, `common_sysctl`, `common_limits`,
`common_fail2ban`, `common_services`, `common_hostname`, `common_preflight`).

## Verification | 验证

```bash
# Static checks
yamllint -c .yamllint.yml roles/common
ansible-lint --offline roles/common
ansible-playbook --syntax-check playbooks/provision/quick-setup.yml

# Idempotency: the second run must report changed=0
ansible-playbook playbooks/provision/quick-setup.yml --limit <host> --tags common
ansible-playbook playbooks/provision/quick-setup.yml --limit <host> --tags common | grep -E "changed=[1-9]"

# On the host
sshd -t && ss -tlnp | grep ":{{ ssh_port }}"
timedatectl && chronyc tracking && chronyc sources
fail2ban-client status sshd
systemctl is-enabled avahi-daemon cups 2>&1
sysctl net.core.somaxconn
```

## Rollback | 回滚

Every templated file is written with `backup: true`, so the previous version
is kept next to it (`/etc/ssh/sshd_config.<pid>.<timestamp>~`). Three
options:

1. Automatic: the role itself restores the backup and restarts the service
   when post-change verification fails (see the roll-out pattern above).
2. Playbook: `ansible-playbook playbooks/maintenance/rollback.yml -e
   rollback_role=common` (add `rollback_dry_run=yes` to list backups,
   `rollback_timestamp=...` to pick one).
3. Manual: `cp /etc/ssh/sshd_config.<backup> /etc/ssh/sshd_config && sshd -t
   && systemctl restart ssh`.

## Requirements | 依赖

Collections `ansible.posix` and `community.general` (`requirements.yml`).
Supported platforms: Debian 11/12, Ubuntu 22.04/24.04; RedHat-family hosts are
supported on a best-effort basis (fail2ban needs EPEL).
