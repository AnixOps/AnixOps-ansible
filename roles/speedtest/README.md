# Speedtest Role | Speedtest 角色

Installs the AnixOps speedtest CLI binary from GitHub releases on every host.
No daemon, no configuration files.

## Behaviour | 行为

1. `stat` the installed binary.
2. When it is missing (or `speedtest_force_update: true`): download the
   release asset for `speedtest_arch` (amd64/arm64 via `_target_arch`) into a
   `tempfile` directory (`get_url` with retries, optional `speedtest_checksum`),
   run `--version` on the download as a sanity check, then copy it into
   `speedtest_install_dir` (the copy only changes the file when the content
   differs). The temp directory is removed in `always`.
3. Verify with `speedtest --version` and print a one-line summary.

`releases/latest/download/...` URLs are not cacheable, so the role deliberately
does not re-download on every run; use `speedtest_force_update: true` (or pin
`speedtest_version`) to upgrade.

## Variables | 变量

| Variable | Default | Description |
|----------|---------|-------------|
| `speedtest_repo_owner` / `speedtest_repo_name` | `AnixOps` / `AnixOps-speedtest` | GitHub repository. |
| `speedtest_version` | `latest` | `latest` or an exact release tag (e.g. `v1.2.0`). |
| `speedtest_arch` | `_target_arch` or mapped `ansible_architecture` | Asset architecture. |
| `speedtest_asset_name` | `speedtest-linux-<arch>` | Release asset name. |
| `speedtest_download_url` | derived from the above | Full URL; override for mirrors. |
| `speedtest_checksum` | `""` | Optional `sha256:<hex>`. |
| `speedtest_download_timeout` / `speedtest_download_retries` / `speedtest_download_delay` | `60` / `5` / `10` | Download behaviour. |
| `speedtest_install_dir` / `speedtest_bin_name` | `/usr/local/bin` / `speedtest` | Install location. |
| `speedtest_force_update` | `false` | Re-download even when the binary exists. |

Lifecycle contract (no service): `speedtest_service_name: ""`,
`speedtest_port: 0`, `speedtest_health_url: ""`, `speedtest_backup_files: []`,
`speedtest_packages: []`, `speedtest_config_dirs: []`.

Removed (unused) variables: `speedtest_repo_branch`, `speedtest_install_method`.

## Usage | 使用

```bash
ansible-playbook playbooks/provision/site.yml --tags speedtest
ansible-playbook playbooks/provision/site.yml --tags speedtest -e speedtest_force_update=true   # upgrade
speedtest --help
```

## Verification | 验证

```bash
/usr/local/bin/speedtest --version
```

A second run of the role must report `changed=0`.

## Rollback | 回滚

Pin the previous release and force the update:

```bash
ansible-playbook playbooks/provision/site.yml --tags speedtest \
  -e speedtest_version=v1.1.0 -e speedtest_force_update=true
```
