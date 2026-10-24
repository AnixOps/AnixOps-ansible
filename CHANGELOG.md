# Changelog | AnixOps Ansible 项目更新日志

## v0.3.0 - 2026-10-24 | Hardening programme | 加固计划

Every role, playbook, workflow and tool was rewritten to one written standard,
[docs/CONVENTIONS.md](docs/CONVENTIONS.md), and is now enforced by tests and CI gates. Read
**Behaviour changes in v0.3.0** below before the first deployment of this release.

### Inventory | 主机清单

- `inventories/production/servers-config.yml` (schema v2) is the single source of truth for hosts,
  groups and host metadata (`server_alias`, `location`, `server_environment`, `description`).
- `tools/generate_inventory.py` renders `inventories/production/hosts.yml` (`make gen-inventory`);
  `python3 tools/generate_inventory.py local --check` is the drift gate in `make check`,
  `make doctor` and CI. The generator rejects unknown keys and groups, duplicate hosts and duplicate
  address variables.
- Host addresses come only from one `<HOST>_V4_SSH` variable per host (`.env` locally, a secret of the
  same name in CI); connection defaults from `ANSIBLE_USER`, `ANSIBLE_PORT`, `SSH_KEY_PATH`.
  `inventories/staging/hosts.yml` is an explicit empty placeholder.

### Roles and playbooks | 角色与 Playbook

- All roles and playbooks follow the conventions: FQCN modules, no `ignore_errors`, `changed_when`
  on every command, retries on every network operation, optional checksums for release downloads,
  `no_log` for secrets, role-prefixed variables, `backup: true` plus `validate:` for every file under
  `/etc`, and a template, flush handlers, verify health, restore-on-failure roll-out.
- systemd units written by roles are hardened (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`,
  `ProtectHome`, restart limits, `network-online.target`).
- Every service role defines the lifecycle contract (`<role>_service_name`, `_port`, `_health_url`,
  `_backup_files`, `_config_dirs`, `_packages`).
- Every play declares `serial`, `max_fail_percentage` and `any_errors_fatal: false`: production plays
  `serial: "30%"` / `max_fail_percentage: 25`, SSH, rollback, lifecycle and Kubernetes plays
  `serial: 1` / `0`.
- `playbooks/provision/site.yml` has one play and exactly one tag per service (`common`,
  `node_exporter`, `promtail`, `firewall`, `nginx`, `prometheus`, `loki`, `grafana`, `postgresql`,
  `v2board`, `v2bx`, `speedtest`, `health`) behind an `always`-tagged preflight (OS family, Python 3,
  free disk). `playbooks/maintenance/health-check.yml` is the single health playbook and is imported
  by `site.yml` and `quick-setup.yml`.
- PLG observability roles: `prometheus` (promtool-validated configuration and alert rules from
  `observability/prometheus/rules/`), `loki` (`-verify-config`, compactor retention 30 days by
  default), `grafana` (mandatory admin password, provisioned datasources, dashboards provisioned from
  `observability/grafana/dashboards/`), plus the `node_exporter` and `promtail` agents.
- `roles/lifecycle` and `playbooks/maintenance/lifecycle.yml`: `status`, `deploy`, `rollback`,
  `cleanup` per role, with versioned snapshots and manifests under `/var/backups/<role>/` and JSON
  state and history under `/var/lib/anixops/state/`; rollback targets `prev`, `initial` or
  `v<YYYYMMDDTHHMMSS>`.
- `playbooks/maintenance/rollback.yml` restores configuration files from Ansible's native backups
  (`<file>.<pid>.<YYYY-MM-DD@HH:MM:SS>~`) and the legacy `<file>.backup.*`, with a pre-rollback
  snapshot, validation, revert on failure and a health probe.
- Weekly security patching: `playbooks/maintenance/security-patch.yml` (Trivy scan, apt/dnf
  remediation, optional reboot, rescan, JSON and Markdown report) and
  `.github/workflows/weekly-security-patch.yml`, which files a single backlog issue through
  `scripts/upsert_security_patch_issue.py`.

### CLI, CI and tests | 命令行、CI 与测试

- `scripts/anixops.sh` is the single CLI (stable exit codes, confirmations for production changes,
  `.env` parsed and never evaluated, every run logged under `.ansible/logs/`, `doctor`); every
  `make` target is a thin wrapper around it.
- About 4,200 repository tests (`python3 -m pytest -q`): text hygiene, role, playbook and workflow
  structure, inventory generator and drift, backup coverage, security patch helpers.
- CI gates: `ansible-lint` production profile with an empty skip list, `yamllint`, backup coverage
  (`scripts/check-backup-coverage.py`), encoding guard, unit tests, `py_compile`, shellcheck,
  inventory drift, syntax check of every playbook, and the localhost integration suite;
  `security-scan.yml` adds TruffleHog, pip-audit, a tracked-key check and the `ignore_errors` policy.
  Shared composite actions `setup-ansible`, `export-secrets` and `job-summary`; deployment workflows
  share the concurrency group `deploy-NodeX-<target>` and never cancel a running job.
- Localhost integration suite: `tests/integration/localhost-converge.yml` converges `common`,
  `node_exporter`, `promtail`, `nginx` and `firewall` on the runner,
  `tests/integration/localhost-verify.yml` checks the services and their endpoints, and CI runs the
  converge a second time and asserts `changed=0`.
- `deploy.yml` gained the inputs `limit_hosts`, `tags`, `verbosity` and `confirm` and the target
  group `postgres_servers`; a `v*` tag now runs the lint gate, every `site.yml` play tag in
  dependency order (one job at a time) and a fleet-wide health check.
- `node-platform-deploy.yml` gained the input `force_https`.
- Documentation refreshed: README, QUICKSTART, GitHub Actions setup, secrets reference,
  observability, SSH keys, secrets management; new `docs/RUNBOOK.md`, `docs/CONVENTIONS.md` and
  `CONTRIBUTING.md`.

### Behaviour changes in v0.3.0 | v0.3.0 行为变更

- **PostgreSQL listens on localhost only.** `postgresql_listen_addresses` defaults to `localhost`,
  and `pg_hba.conf` admits the application role only from `postgresql_allowed_cidrs` (default
  `127.0.0.1/32` and `::1/128`) with `scram-sha-256`; everything else is rejected. To expose the
  database, set both variables (and keep port 5432 whitelisted). The role tests the application login
  and re-sets the password when it fails, which also migrates old md5 password hashes.
- **`nginx_stop_conflicting_services` defaults to `false`.** The nginx role no longer stops other
  services on ports 80/443 unless you opt in; when enabled it stops and disables only the units in
  `nginx_conflicting_services` that exist, and it never signals processes.
- **Speedtest scrape job is opt-in.** Prometheus renders the `speedtest` job only when
  `prometheus_speedtest_exporter_host` (or the legacy `speedtest_exporter_host`) is set.
- **Password logins are off.** `ssh_password_authentication: false` in
  `inventories/production/group_vars/all/main.yml`; the next `common` run makes every host key-only.
  Install your public key everywhere first.
- **pl-1 k3s test cluster.** `k3s_version` is now `v1.31.5+k3s1` (was `v1.27.3+k3s1`) and the
  kubeconfig is fetched to `~/.kube/k3s-pl-1.yaml` (was `/tmp/k3s-pl-1-kubeconfig.yaml`). The installer
  step is guarded by the k3s binary, so an existing installation is not upgraded automatically.
- **New workflow input `allow_reboot`** on `weekly-security-patch.yml`: `inventory` (default) keeps the
  per-host/group `security_patch_allow_reboot`; `true` / `false` pass
  `-e security_patch_allow_reboot=<value>`.
- **Forced group-wide lifecycle runs pass the confirmation flags.** `rollback.yml` and `lifecycle.yml`
  refuse to roll back or clean up more than one host without `rollback_confirm_all=true` /
  `lifecycle_confirm_all=true`. The Lifecycle Management workflow passes `lifecycle_confirm_all=true`
  when `force=true`; `scripts/anixops.sh rollback`, `rollback-files` and `cleanup-role` pass the
  matching flag after their confirmation prompt. The obsolete `-e lifecycle_hook_type=post_rollback`
  is no longer passed.
- **Lifecycle version format.** The workflow accepts `prev`, `initial` and `vYYYYMMDDTHHMMSS` (the
  format the lifecycle role writes); `rollback-files --timestamp` takes any substring of the native
  backup name, e.g. `2026-10-24@14`.
- **Grafana admin password.** It is read from `GRAFANA_ADMIN_PASSWORD` (or `grafana_admin_password`),
  is mandatory and must not be `admin`; the role fails before installing anything otherwise. Grafana is
  no longer pinned to 10.0.0: `grafana_version: ""` installs the current release from
  `apt.grafana.com` and never upgrades an existing installation (set `grafana_version` to pin).
- **Loki retention is on.** `loki_retention_enabled: true` with `loki_retention_period: 30d`; after the
  first deployment of this release the compactor deletes log data older than 30 days. Set
  `loki_retention_period` (or `loki_retention_enabled: false`) before deploying if you need more.
- **Localhost integration suite in CI.** Pull requests now also converge `common`, `node_exporter`,
  `promtail`, `nginx` and `firewall` on the runner, verify them and fail when a second converge is not
  idempotent.

---

## v0.2.0 - 2026-04-27 🚀 Cloudflare Mesh 迁移

### 🔄 网络架构重构

- **Cloudflare Mesh 统一网络方案**
  - 删除旧的 Cloudflare Tunnel/WARP 方案（`cloudflared`、`cloudflared_deploy`、`warp_connector` roles）
  - 删除 Headscale/Tailscale 方案（`headscale`、`headscale_agent` roles）
  - 新增 `cloudflare_mesh` role：使用 Cloudflare One Client (`warp-cli`) headless 模式
  - 原生 IP 路由（TCP/UDP/ICMP），地址空间 `100.96.0.0/12`
  - Dashboard 端集中管理路由和访问控制

### 🗑️ 删除的文件

- **删除 5 个 roles**：`cloudflared`、`cloudflared_deploy`、`warp_connector`、`headscale`、`headscale_agent`
- **删除 2 个工具**：`tools/tunnel_manager.py`、`tools/tunnel.example`
- **删除 1 个脚本**：`scripts/deploy_netmaker_clients.sh`
- **删除 1 个文档**：`docs/HEADSCALE_QUICK_REF.md`
- **删除 2 个 group_vars**：`inventories/production/group_vars/headscale_clients.yml`、`headscale_server.yml`

### ✨ 新增文件

- `roles/cloudflare_mesh/` - 新的 Mesh 节点 role
- `inventories/production/hosts.yml` 新增 `mesh_nodes` 组

### 🔧 配置变更

- `.env.example` 新增 `CLOUDFLARE_MESH_TOKEN`、`CLOUDFLARE_MESH_NODE_NAME`、`CLOUDFLARE_MESH_ADVERTISE_SUBNETS`
- `.env.example` 删除 `CLOUDFLARE_TUNNEL_TOKEN`、`WARP_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` 等旧变量
- `playbooks/maintenance/rollback.yml` 删除 `headscale`、`cloudflared` 回滚支持
- `roles/README-stability.md` 更新角色清单，新增 `cloudflare_mesh`

---

## v0.1.0 - 2025-10-28 🎉 重大重构版本

### 🚀 重大功能更新

#### ✨ Kubernetes 部署支持（重要里程碑）

- **🆕 K8s 集群自动化部署**
  - 新增 `k8s_provision` Role：支持本地 Kind 和生产 K3s 集群部署
  - 自动检测并安装 Docker、kubectl、Helm 等依赖工具
  - 本地环境：自动创建 Kind 集群，适合开发测试
  - 生产环境：一键部署 K3s 轻量级 Kubernetes 集群
  - 完整的集群验证和健康检查流程

- **🆕 Cloudflared K8s 部署**
  - 新增 `cloudflared_deploy` Role：使用 Helm 部署 Cloudflared
  - 支持本地和生产环境自动适配
  - 安全的 Token 管理（支持命令行、环境变量、Ansible Vault）
  - 自动化 Namespace、Secret、Helm Chart 管理
  - 完整的部署验证和日志查看

#### 🔧 统一管理脚本

- **🎯 anixops.sh - 统一入口**
  - 集成所有管理功能到单一脚本
  - 支持命令：`deploy-local`、`deploy-production`、`cleanup-local`、`status-local` 等
  - 友好的彩色输出和进度提示
  - 完整的参数支持：`--tags`、`--skip-tags`、`--dry-run`、`--verbose`
  - 详细的帮助文档和使用示例
  - 所有脚本统一移至 `scripts/` 目录

#### 📁 项目结构重组

- **Playbooks 多级目录结构**
  - `playbooks/deployment/` - 部署相关（local.yml、production.yml 等）
  - `playbooks/cloudflared/` - Cloudflared 专用（k8s-helm.yml 等）
  - `playbooks/maintenance/` - 维护管理（health-check.yml 等）
  - 总计 14 个 playbooks，按功能清晰分类

- **环境配置完全分离**
  - `inventories/local/` - 本地 Kind 集群配置
  - `inventories/production/` - 生产 K3s 集群配置
  - 独立的 hosts.ini 和 group_vars，互不干扰

#### 📚 文档重构

- **精简和归档**
  - 根目录只保留 1 个主 README.md
  - 核心文档：22 个（常用和实用）
  - 归档文档：14 个（历史和过时文档移至 docs/archive/）
  - 新增 `PROJECT_STRUCTURE.md` - 完整的项目结构说明
  - 新增 `docs/README.md` - 文档索引和导航
  - 新增 `playbooks/README.md` - Playbooks 详细说明

### 🔄 重构和改进

#### 架构优化

- ✅ Role 模块化设计：k8s_provision + cloudflared_deploy
- ✅ 三阶段部署流程：K8s 部署 → Cloudflared 部署 → 验证
- ✅ 环境隔离：本地和生产完全独立配置
- ✅ 统一脚本管理：从多个脚本到一个 anixops.sh

#### 安全增强

- ✅ 多种 Token 管理方式（命令行、环境变量、Vault）
- ✅ Ansible Vault 完整集成
- ✅ 敏感信息不记录日志（no_log: true）
- ✅ 生产部署前确认提示

#### 用户体验

- ✅ 友好的彩色输出界面
- ✅ 详细的进度和状态展示
- ✅ 完整的错误提示和故障排除指南
- ✅ Dry-run 模式支持
- ✅ Tags 支持（只运行特定部分）

### 📊 统计数据

- **Playbooks**: 14 个（重组为 3 级目录）
- **Roles**: 13+ 个（新增 2 个核心 Role）
- **Scripts**: 3 个（全部在 scripts/ 目录）
- **Inventories**: 2 套（完全隔离）
- **文档**: 22 核心 + 14 归档

### 🎯 使用示例

```bash
# 本地部署（最简单）
./scripts/anixops.sh deploy-local -t "your-cloudflare-token"

# 生产部署（使用 Vault）
./scripts/anixops.sh deploy-production --vault-password ~/.vault_pass

# 查看状态
./scripts/anixops.sh status-local

# 清理环境
./scripts/anixops.sh cleanup-local
```

### 🔗 相关文档

- [README.md](README.md) - 快速开始和完整指南
- [docs/REFACTORED_DEPLOYMENT_GUIDE.md](docs/REFACTORED_DEPLOYMENT_GUIDE.md) - 详细部署指南
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - 项目结构总览
- [playbooks/README.md](playbooks/README.md) - Playbooks 说明

---

## v0.0.2 - 2025-10-23

### 🚀 功能增强

#### ✨ 新增功能

- **🆕 Secrets 批量上传工具**（重要更新）
  - 新增 `secrets_uploader.py` 工具，从 .env 文件批量上传 GitHub Secrets
  - 支持交互式和命令行两种模式
  - 自动加密并安全上传敏感信息
  - 支持过滤和排除特定变量
  - 提供 Dry Run 测试模式
  - 实时显示上传进度和结果统计
  - 完整的错误处理和用户友好提示
  - 详细的使用文档和示例

- **GitHub Actions 工作流完善**
  - 完善 `deploy.yml` 工作流，添加完整的环境变量支持（45+ 环境变量）
  - 更新 `lint.yml` 工作流，优化代码检查流程
  - 改进 `ansible-ci.yml` CI/CD 流程，添加 Dry Run 测试
  - 支持 workflow_dispatch 手动触发部署，可选择部署目标
  - 添加部署摘要和详细的错误通知

- **环境变量系统**
  - 完善 `.env.example` 文件，提供详细的配置说明
  - 支持多服务器 IP 配置（IPv4/IPv6）
  - 添加可观测性服务配置（Prometheus、Loki、Grafana）
  - 支持 SSL/TLS 配置（自定义证书和 ACME）
  - Cloudflare API 集成配置
  - Grafana 认证配置
  - 防火墙白名单配置

#### 📝 文档改进

- 新增 `docs/GITHUB_SECRETS_REFERENCE.md` - 完整的 Secrets 配置参考手册
- 新增 `docs/RELEASE_GUIDE.md` - 版本发布流程和检查清单
- 新增 `tools/README_SECRETS_UPLOADER.md` - Secrets 上传工具详细文档
- 更新 README.md，添加版本徽章和许可证徽章
- 完善快速开始指南，添加新工具使用说明
- 优化项目结构说明
- 改进 SSH 密钥管理说明
- 文档索引添加新文档链接

#### 🔧 工作流改进

- 优化部署流程，添加部署摘要输出
- 改进错误处理和失败通知
- 添加更多调试信息输出
- 支持动态 inventory 生成

### 🐛 Bug 修复

- 修复工作流中环境变量传递问题
- 修正文档中的示例错误
- 优化 SSH 密钥权限设置

### 📦 依赖更新

- 更新 GitHub Actions 版本（checkout@v4, setup-python@v5）
- 使用 Python 3.11 作为默认版本

---

## v0.0.1 - 2025-10-20

### 🎉 初始版本发布

#### ✨ 新功能

- **GitOps 工作流**
  - 完整的 GitHub Actions CI/CD 集成
  - 自动化代码检查 (ansible-lint, yamllint)
  - 自动化部署到生产环境
  
- **Ansible Roles**
  - `common`: 基础系统配置、安全加固、用户管理
  - `nginx`: Web 服务器部署和配置
  - `node_exporter`: Prometheus 主机监控
  - `promtail`: Loki 日志收集代理

- **Playbooks**
  - `site.yml`: 完整部署所有配置
  - `quick-setup.yml`: 快速初始化新服务器
  - `web-servers.yml`: 专门部署 Web 服务器
  - `health-check.yml`: 健康检查和状态监控

- **可观测性**
  - Prometheus 告警规则（主机和 Nginx）
  - Grafana 仪表盘模板
  - 完整的 PLG (Prometheus + Loki + Grafana) 栈集成

- **工具**
  - `ssh_key_manager.py`: SSH 密钥安全管理工具
  - 支持加密上传私钥到 GitHub Secrets
  - 交互式和命令行模式

#### 🔒 安全特性

- SSH 密钥认证，禁用密码登录
- UFW/Firewalld 防火墙配置
- Fail2Ban 入侵防护
- 系统内核参数优化
- 安全的 SSH 配置模板

#### 📚 文档

- 完整的中英文双语运维手册
- README.md 快速开始指南
- QUICKSTART.md 5 分钟部署指南
- 代码内详细注释

#### 🌐 全球分布式支持

- 支持多区域服务器管理
- 环境变量驱动的主机配置
- 跳板机支持（可选）

---

## 路线图

### v0.1.0 (计划中)

- [ ] Docker 容器支持
- [ ] K8s 集成
- [ ] 更多应用 roles (Redis, PostgreSQL, etc.)
- [ ] Vault 集成用于密钥管理
- [ ] 更完善的回滚机制

### v0.2.0 (计划中)

- [ ] 多云支持 (AWS, GCP, Azure)
- [ ] Terraform 集成
- [ ] 自动化测试框架
- [ ] 性能优化和并发执行

---

## 贡献者

- @kalijerry - 项目创建者和主要维护者

---

**感谢所有贡献者和使用者！**
