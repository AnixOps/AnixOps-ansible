# v2bx role | V2bX 角色

Deploys a **V2bX** proxy node (sing-box / Xray / Hysteria2 core) that
auto-registers with a v2board panel. Each node obtains its own AuthKey from the
panel's internal API, stores it locally and reuses it on later runs.

部署 V2bX 代理节点，自动向 v2board 面板申请 AuthKey 并完成注册。

## Flow | 流程

```
1. Resolve AuthKey   V2BX_AUTH_KEY env > /etc/V2bX/authkey (stored) > POST {V2BX_API_HOST}/api/v2/internal/auth-keys
2. Install           V2bX binary (+ geoip/geosite) from GitHub releases, optional checksum
3. Configure         /etc/V2bX/config.json (0600, validated with python3 -m json.tool) + hardened systemd unit
4. Start             daemon-reload -> enable --now V2bX (handlers flushed first)
5. Verify            service active, credential.json appears (auto-registration), optional port wait
```

The panel API call runs once **per host** (no `run_once`) on
`v2bx_authkey_api_delegate` (default `localhost`, the controller) because every
node registers under its own `v2bx_node_name`. The key is written to
`/etc/V2bX/authkey` (`0600`) and reused, so a second run leaves `config.json`
untouched and does not restart the service. Only the key id/name are printed.

## Variables | 变量

| Variable | Env | Default | Notes |
|----------|-----|---------|-------|
| `v2bx_api_host` | `V2BX_API_HOST` | required | panel base URL reachable from the node, e.g. `http://100.96.0.5:8080` |
| `v2bx_protocols` | `V2BX_PROTOCOLS` | `["vmess"]` | JSON array `["vmess","vless","shadowsocks","hysteria2"]` or comma list `vmess,vless` |
| `v2bx_node_name` | `V2BX_NODE_NAME` | `inventory_hostname` | the env value applies to *all* hosts of a run; use host_vars for multi-node deploys |
| `v2bx_core` | `V2BX_CORE` | `sing` | `sing`, `xray` or `hysteria2` |
| `v2bx_auth_key` | `V2BX_AUTH_KEY` | `""` | manual AuthKey (skips the API call) |
| `v2bx_auto_generate_authkey` | `V2BX_AUTO_GENERATE_AUTHKEY` | `true` | mint a key via the panel API when none is available |
| `v2bx_panel_api_token` | `V2BOARD_API_TOKEN` | `""` | same token as `app.api_token` in the panel's `config.yaml` |
| `v2bx_authkey_expire_days` | `V2BX_AUTHKEY_EXPIRE_DAYS` | `1` | |
| `v2bx_authkey_file` | | `/etc/V2bX/authkey` | stored key (0600) |
| `v2bx_binary_url` | `V2BX_BINARY_URL` | GitHub `releases/download/latest/V2bX-linux-<arch>` | |
| `v2bx_binary_checksum` | | `""` | e.g. `sha256:<hex>` |
| `v2bx_force_update` | | `false` | re-download the binary even if present |
| `v2bx_update_geodata` | | `false` | re-download geoip/geosite even if present |
| `v2bx_cert_mode` / `v2bx_cert_domain` | `V2BX_CERT_MODE` / `V2BX_CERT_DOMAIN` | `self` / `""` | |
| `v2bx_log_level` | `V2BX_LOG_LEVEL` | `info` | |
| `v2bx_extra_after_units` | | `[]` | extra systemd units to order after (e.g. `warp-svc.service`) |
| `v2bx_port` | | `0` | when > 0 the role waits for this port after start |

### Lifecycle contract | 生命周期契约

`v2bx_port` (0: ports come from the panel), `v2bx_health_url` (empty: no HTTP
endpoint), `v2bx_backup_files` (`config.json`, `authkey`, `credential.json`),
`v2bx_config_dirs`, `v2bx_packages` (empty) and `v2bx_service_name` (`V2bX`).

## Secrets handling | 密钥处理

* `config.json` contains the AuthKey and is written `0600`; `authkey` and the
  panel-issued `credential.json` live in `/etc/V2bX` and `/var/lib/V2bX`
  (`0750`).
* Tasks that read, render, store or restore these files run with
  `no_log: true`; the API response is never printed.
* Export the panel token as `V2BOARD_API_TOKEN` (the same secret the v2board
  role writes into `config.yaml`).

## Verification | 验证

```bash
systemctl status V2bX
journalctl -u V2bX -n 100 --no-pager
ls -l /var/lib/V2bX/credential.json      # created after successful auto-registration
python3 -m json.tool /etc/V2bX/config.json > /dev/null && echo "config.json OK"
```

In the panel: *Nodes* -> the node named `v2bx_node_name` should be online once
protocols (port, TLS, transport) are configured for it.

## Rollback | 回滚

* A failed configuration automatically restores the previous `config.json`
  (`.backup` file from the template task), restarts V2bX and fails the play
  with the journal tail.
* Manual rollback: copy the newest `/etc/V2bX/config.json.<timestamp>~` over
  `config.json` and run `systemctl restart V2bX`.
* To re-register a node from scratch delete `/etc/V2bX/authkey` and
  `/var/lib/V2bX/credential.json`, then re-run the role (a new AuthKey is
  requested from the panel).
* Binary rollback: set `V2BX_BINARY_URL` to a pinned build and run with
  `-e v2bx_force_update=true`.
