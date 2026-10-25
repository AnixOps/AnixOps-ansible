# firewall role | 防火墙角色

Lockout-proof host firewall for every AnixOps server. On Debian/Ubuntu it drives
**UFW**, on RedHat-family hosts **firewalld**, with the same semantics:

| Port class | Source | Example |
|---|---|---|
| SSH port(s) | anywhere, **always allowed first** | `ansible_port` / `ssh_port`, default 22 |
| Public ports | anywhere | `firewall_public_ports` + `proxy_additional_ports` |
| Restricted ports | `monitoring_whitelist` only, denied for everyone else | 9100, 9080, 9090, 3100, 3000 (+5432 in production) |

## Lockout protection | 防锁死保护

1. **Preflight refuses dangerous input** before anything is touched: unsupported OS,
   malformed ports, a whitelist entry that is not an IPv4/IPv6 address or CIDR, and any
   port that is both public (or the SSH port) and restricted.
2. The SSH port is computed from the live connection
   (`firewall_ssh_port = ansible_port | default(ssh_port | default(22))`). When `ssh_port`
   differs from the port Ansible is connected on (for example while the `common` role is
   moving sshd), **both** ports are allowed.
3. The SSH allow rule is the first rule written, before public ports, before deny rules,
   before the default policy is set and before the firewall is enabled.
4. After enabling, the role reads `ufw status verbose` / `firewall-cmd --state` and
   **asserts** that the firewall is active and the SSH allow rule is present. A host that
   fails this check fails the play (and `max_fail_percentage` stops the rollout).
5. `firewall_enabled: false` leaves the host untouched; the role never disables a firewall.

## Variables | 变量

Operator knobs are the global keys in `inventories/production/group_vars/all/main.yml`;
the role consumes them through prefixed defaults with fallbacks.

| Variable | Default | Description |
|---|---|---|
| `firewall_enabled` | `true` | Master switch (global key). |
| `firewall_public_ports` | `["22", "80", "443"]` | TCP ports open to anyone (global key). |
| `firewall_restricted_ports` | `["9100", "9080", "9090", "3100", "3000"]` | TCP ports open to the whitelist only (global key). |
| `firewall_proxy_additional_ports` | `proxy_additional_ports \| default([])` | Extra public ports (group/host vars). |
| `firewall_whitelist` | `monitoring_whitelist \| default([])` | Whitelisted sources; trimmed, comma-split, validated, converted to ufw's canonical form and de-duplicated. |
| `firewall_ssh_port` | `ansible_port \| default(ssh_port \| default(22))` | SSH port that must stay reachable. |
| `firewall_default_incoming_policy` | `allow` | `allow` keeps the historical behaviour, `deny`/`reject` = allow-list mode. |
| `firewall_default_outgoing_policy` | `allow` | |
| `firewall_fail_on_empty_whitelist` | `false` | Fail (true) or warn and skip whitelist rules (false) when restricted ports exist but the whitelist is empty. |
| `firewall_prune_stale_whitelist_rules` | `true` | Delete whitelist rules created by this role for addresses that left the whitelist (UFW). |
| `firewall_ufw_logging` | `low` | `on`, `off`, `low`, `medium`, `high`, `full`. |
| `firewall_ipv6_enabled` | `true` | Keeps `IPV6=yes` in `/etc/default/ufw` (backup taken). |
| `firewall_docker_user_chain` | `false` | Append the ufw-docker `DOCKER-USER` rules to `/etc/ufw/after.rules` (see Docker). |
| `firewall_firewalld_zone` | `public` | firewalld zone. |
| `firewall_firewalld_manage_target` | `false` | Map the incoming policy onto the zone target (`ACCEPT`/`DROP`/`%%REJECT%%`). |

Lifecycle contract (`roles/lifecycle`): `firewall_port: 0`, `firewall_health_url: ""`,
`firewall_service_name` (`ufw` / `firewalld`), `firewall_packages`, `firewall_backup_files`
(`/etc/default/ufw`, `/etc/ufw/ufw.conf`, `/etc/ufw/user.rules`, `/etc/ufw/user6.rules`,
`/etc/ufw/after.rules`), `firewall_config_dirs` (`/etc/ufw`).

Facts computed by `tasks/preflight.yml` (usable by playbooks after
`include_role: name=firewall tasks_from=preflight`): `firewall_ssh_ports`,
`firewall_effective_public_ports`, `firewall_effective_restricted_ports`,
`firewall_effective_whitelist`, `firewall_whitelist_rules`, `firewall_whitelist_rules_enabled`.

After validation every whitelist entry is converted (filter `firewall_ufw_address` in
`filter_plugins/firewall_address.py`, standard library only) to the form ufw stores and prints:
`/32` and `/128` are dropped, IPv4 CIDRs are reduced to the network address (`10.0.0.5/24` becomes
`10.0.0.0/24`), IPv6 is lower-cased and compressed and IPv6 prefixes keep their host bits, as in
ufw. That form is what appears in `firewall_effective_whitelist`, the plan output, the ufw rule
comment (`Monitoring access from <address>`) and the firewalld rich rules; entries that become
identical are de-duplicated. Before, a non-canonical entry such as `1.2.3.4/32` lost its allow rule
on every second run (pruned, then re-added). Entries that match the regex but are not valid
addresses (e.g. `010.0.0.1`) fail in preflight with `firewall_ufw_address: ... is not a valid
IPv4/IPv6 address or CIDR`. On firewalld hosts that had a non-canonical entry, the canonical rich
rule is added once and the old one stays as a harmless duplicate (firewalld rules are never
pruned); remove it by hand if wanted.

## Behaviour | 行为

### UFW (Debian/Ubuntu)

1. Install `ufw` (with retries), set `IPV6=` in `/etc/default/ufw`, optionally append the
   Docker block to `/etc/ufw/after.rules` (both with `backup: true`).
2. Read `ufw show added` once; every deletion below is guarded by that output so a second
   run reports `changed=0`.
3. Allow SSH port(s) (`comment "SSH (managed by Ansible)"`), then the public ports.
4. Delete a plain `allow <port>/tcp` rule for each restricted port if one exists (it would
   bypass the whitelist).
5. Add `allow from <ip> to any port <port> proto tcp` for every whitelist x restricted
   pair. New rules are **inserted at the top** (IPv4: position 1, IPv6: before the first
   IPv6 rule) so they always precede the deny rules, even on later runs.
6. Ordering repair: if an existing deny rule still precedes a whitelist allow rule
   (for instance after rules were edited by hand), that deny rule is deleted and re-added
   at the end.
7. Add `deny <port>/tcp` for each restricted port; prune whitelist rules created by this
   role whose address is no longer whitelisted.
8. Set default policies (`incoming` from `firewall_default_incoming_policy`, `outgoing allow`),
   logging level, `ufw enable`, flush handlers (`Reload ufw`), verify and summarise.

### firewalld (RedHat family)

Install and start `firewalld`; allow the SSH port(s) (and the `ssh` service while SSH is
on 22); open public ports; remove plain openings of restricted ports; add rich rules
`priority="-100" ... accept` per whitelist address and `priority="-50" ... reject` per
restricted port (IPv4 and IPv6); optionally set the zone target; verify
`firewall-cmd --state` is `running` and the SSH port is listed in the zone.

### Empty whitelist

When restricted ports are configured but the whitelist is empty the role prints a warning,
keeps the deny rules and leaves existing whitelist rules untouched
(`firewall_fail_on_empty_whitelist: false`). `playbooks/maintenance/firewall-setup.yml`
is stricter: it asserts a non-empty whitelist unless run with
`-e firewall_require_whitelist=false`.

## Docker caveat | Docker 注意事项

Docker publishes ports with its own `nat`/`FORWARD` rules, which **UFW's INPUT rules do
not see**: a container published with `-p 3000:3000` is reachable from the Internet even
if UFW denies 3000/tcp. Options:

* Bind containers to loopback (`-p 127.0.0.1:3000:3000`) and front them with Nginx.
* Set `firewall_docker_user_chain: true`. The role then appends the standard
  [ufw-docker](https://github.com/chaifeng/ufw-docker) block to `/etc/ufw/after.rules`
  (marker `# BEGIN/END UFW AND DOCKER`, backup taken, `ufw reload`). Afterwards published
  ports are reachable only from private networks; expose one explicitly with
  `ufw route allow proto tcp from any to any port <container-port>`. Enabling it is a
  behaviour change for every container on the host, so roll it out group by group.
  Setting the flag back to `false` does not remove the block; delete it by hand and
  `ufw reload`.

## Verification | 验证

```bash
sudo ufw status verbose          # Status: active, SSH ALLOW IN, restricted DENY IN
sudo ufw show added              # the exact rules the role manages (with comments)
sudo firewall-cmd --list-all     # RedHat: ports, rich rules
# from a whitelisted host
curl -s http://<server>:9100/metrics | head -1
# from any other host the restricted port must time out / be refused
```

The maintenance playbook prints the effective plan in `pre_tasks` and the live status in
`post_tasks`; run it with `--check --diff` first on a new group.

## Rollback | 回滚

```bash
sudo ufw disable                                   # stop filtering immediately (rules are kept)
sudo ufw delete deny 9100/tcp                      # drop a single rule
sudo cp /etc/default/ufw.<timestamp>~ /etc/default/ufw   # restore a backup written by the role
sudo cp /etc/ufw/after.rules.<timestamp>~ /etc/ufw/after.rules
sudo ufw reload
sudo ufw reset                                     # last resort: back to package defaults
# RedHat
sudo systemctl stop firewalld
```

`roles/lifecycle` backs up `firewall_backup_files` before changes and can restore them;
`playbooks/maintenance/rollback.yml` uses the same list.

## Usage | 使用

```yaml
- hosts: all
  become: true
  roles:
    - role: firewall
```

```bash
ansible-playbook playbooks/maintenance/firewall-setup.yml --limit web_servers --check --diff
ansible-playbook playbooks/maintenance/firewall-setup.yml
ansible-playbook playbooks/provision/site.yml --tags firewall
```
