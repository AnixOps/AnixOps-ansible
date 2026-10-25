# cloudflare_mesh

Enroll a server as a [Cloudflare Mesh](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-mesh/)
node with the headless Cloudflare One client (`warp-cli`). Mesh gives every enrolled server, laptop and
phone a private Mesh IP (`100.96.0.0/12`) and routes TCP, UDP and ICMP natively between participants.

将服务器注册为 Cloudflare Mesh 节点（headless `warp-cli`），实现节点间原生 IP 路由，替代
Headscale/Tailscale 和旧的 WARP Connector 方案。

## Behaviour | 行为

1. Validates that `cloudflare_mesh_token` is set and the OS family is Debian/Ubuntu or RHEL-compatible.
2. Installs `cloudflare-warp` from the official repository (apt: signing key downloaded with `get_url`
   (conditional GET, replaced when upstream changes it) and re-dearmored into the `signed-by` keyring
   whenever the key changed or is newer than the keyring; rpm: `yum_repository` + `dnf`). Every network
   step retries `5 x 10s`.
3. Applies the kernel settings Cloudflare recommends for Mesh nodes through `ansible.posix.sysctl`
   (`net.ipv4.ip_forward=1`, `net.ipv6.conf.all.forwarding=1`, `net.ipv6.conf.all.accept_ra=2`).
4. Starts and enables `warp-svc`, waits until `warp-cli status` answers.
5. Enrolls **once**: `warp-cli --accept-tos registration show` is the probe; only when it reports no
   registration does `warp-cli --accept-tos connector new <token>` run (`no_log: true`).
6. Runs `warp-cli --accept-tos connect` when the status is not `Connected`, then waits
   (`cloudflare_mesh_connect_retries x cloudflare_mesh_connect_delay`) for `Status update: Connected`.
7. Optionally pins the interface MTU (`cloudflare_mesh_mtu > 0`).

A second run reports `changed=0`. Device names, advertised routes and access policies are managed in the
Zero Trust dashboard (Networking > Mesh), not by this role.

## Variables | 变量

| Variable | Default | Description |
|---|---|---|
| `cloudflare_mesh_token` | `$CLOUDFLARE_MESH_TOKEN` | enrollment token (dashboard > Networking > Mesh > Add node > CLI enrollment string); never logged |
| `cloudflare_mesh_package` | `cloudflare-warp` | package name |
| `cloudflare_mesh_service_name` | `warp-svc` | systemd unit |
| `cloudflare_mesh_interface` | `CloudflareWARP` | tunnel interface name |
| `cloudflare_mesh_mtu` | `0` (client default / PMTUD) | MTU override, minimum 1281 |
| `cloudflare_mesh_sysctl_file` | `/etc/sysctl.d/99-zzz-cloudflare-warp-connector.conf` | sysctl drop-in |
| `cloudflare_mesh_sysctl` | see defaults | key/value map applied with `ansible.posix.sysctl` |
| `cloudflare_mesh_apt_key_url`, `_apt_key_file`, `_apt_keyring`, `_apt_repo` | Cloudflare apt source | apt repository settings |
| `cloudflare_mesh_rpm_baseurl`, `_rpm_gpgkey` | Cloudflare rpm source | rpm repository settings |
| `cloudflare_mesh_download_retries` / `_download_delay` | `5` / `10` | retry policy for package/network steps |
| `cloudflare_mesh_connect_retries` / `_connect_delay` | `12` / `5` | wait policy for daemon/connection |

Lifecycle contract: `cloudflare_mesh_port: 0`, `cloudflare_mesh_health_url: ""`,
`cloudflare_mesh_backup_files: [<sysctl drop-in>]`, `cloudflare_mesh_config_dirs: [/var/lib/cloudflare-warp]`,
`cloudflare_mesh_packages: [cloudflare-warp]`, `cloudflare_mesh_service_name: warp-svc`.

## Usage | 使用

```bash
export CLOUDFLARE_MESH_TOKEN='<enrollment token>'   # or a GitHub Actions secret
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/site.yml --tags cloudflare_mesh
```

```yaml
- name: Cloudflare Mesh nodes
  hosts: mesh_nodes
  become: true
  gather_facts: true
  roles:
    - role: cloudflare_mesh
```

RHEL 9 and later need EPEL enabled before the client installs
(`dnf install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm`).

## Verification | 验证

```bash
warp-cli --accept-tos status            # Status update: Connected
warp-cli --accept-tos registration show
ip addr show CloudflareWARP
ping <mesh ip of another node>          # e.g. 100.96.x.y
```

The node must show as **Online** on the Mesh overview page with its assigned Mesh IP.

## Rollback | 回滚

Mesh enrollment is state in `/var/lib/cloudflare-warp`, not a config file, so rollback is manual:

1. Dashboard: Networking > Mesh > Nodes > delete the node.
2. Server: `warp-cli --accept-tos disconnect && warp-cli --accept-tos registration delete`.
3. `systemctl disable --now warp-svc` (and `apt remove cloudflare-warp` if the client is no longer wanted).

The sysctl drop-in can be removed with `rm /etc/sysctl.d/99-zzz-cloudflare-warp-connector.conf && sysctl --system`.

## References | 参考

- [Cloudflare Mesh](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-mesh/)
- [Get started with Cloudflare Mesh](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-mesh/get-started/)
