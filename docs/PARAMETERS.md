# 📋 参数需求表 | Parameters Requirements

> **中文说明：** 本文档列出了 AnixOps Ansible 项目所需的所有配置参数，包括环境变量、GitHub Secrets 和 Ansible 变量配置。
>
> **English Description:** This document lists all configuration parameters required for the AnixOps Ansible project, including environment variables, GitHub Secrets, and Ansible variable configurations.

---

## 📑 目录 | Table of Contents

- [GitHub Secrets 配置 | GitHub Secrets Configuration](#github-secrets-配置--github-secrets-configuration)
- [环境变量配置 (.env) | Environment Variables Configuration (.env)](#环境变量配置-env--environment-variables-configuration-env)
- [Ansible 全局变量 | Ansible Global Variables](#ansible-全局变量--ansible-global-variables)
- [服务器节点配置 | Server Node Configuration](#服务器节点配置--server-node-configuration)

---

## 🔐 GitHub Secrets 配置 | GitHub Secrets Configuration

### 必需参数 | Required Parameters

在 GitHub 仓库的 Settings → Secrets and variables → Actions 中配置以下参数：

Configure the following parameters in your GitHub repository: Settings → Secrets and variables → Actions:

| Secret 名称<br>Secret Name | 类型<br>Type | 说明<br>Description | 示例值<br>Example | 是否必需<br>Required |
|------------|------|------|--------|---------|
| `SSH_PRIVATE_KEY` | SSH 密钥<br>SSH Key | 用于连接服务器的 SSH 私钥（完整内容）<br>SSH private key for server connection (full content) | `-----BEGIN OPENSSH PRIVATE KEY-----\n...` | ✅ 必需<br>Required |
| `ANSIBLE_USER` | 字符串<br>String | SSH 连接用户名<br>SSH connection username | `root` 或 or `ubuntu` | ✅ 必需<br>Required |
| `ANSIBLE_PORT` | 数字<br>Number | SSH 连接端口<br>SSH connection port | `22` | ✅ 必需<br>Required |

### 服务器 IP 地址 | Server IP Addresses

| Secret 名称<br>Secret Name | 类型<br>Type | 说明<br>Description | 示例值<br>Example | 是否必需<br>Required |
|------------|------|------|--------|---------|
| `DE_1_V4_SSH` | IP 地址<br>IP Address | 德国测试服务器 IPv4 地址<br>Germany test server IPv4 address | `203.0.113.10` | ✅ 必需<br>Required |
| `PL_1_V4_SSH` | IP 地址<br>IP Address | 波兰测试服务器 IPv4 地址（可观测性服务器）<br>Poland test server IPv4 (observability server) | `203.0.113.20` | ✅ 必需<br>Required |

### 可观测性配置（可选）| Observability Configuration (Optional)

| Secret 名称<br>Secret Name | 类型<br>Type | 说明<br>Description | 示例值<br>Example | 是否必需<br>Required |
|------------|------|------|--------|---------|
| `PROMETHEUS_URL` | URL | Prometheus 服务器地址<br>Prometheus server address | `http://prometheus.example.com:9090` | ⚪ 可选<br>Optional |
| `LOKI_URL` | URL | Loki 日志服务器地址<br>Loki log server address | `http://loki.example.com:3100` | ⚪ 可选<br>Optional |
| `GRAFANA_URL` | URL | Grafana 仪表盘地址<br>Grafana dashboard address | `http://grafana.example.com:3000` | ⚪ 可选<br>Optional |

---

## 🌍 环境变量配置 (.env) | Environment Variables Configuration (.env)

用于本地开发和测试，不要提交到 Git 仓库。

For local development and testing, do not commit to Git repository.

### 创建 .env 文件 | Create .env File

```bash
cp .env.example .env
vim .env
```

### 必需环境变量 | Required Environment Variables

```bash
# SSH 连接配置 | SSH Connection Configuration
ANSIBLE_USER=root                      # SSH 用户名 | SSH username
ANSIBLE_PORT=22                        # SSH 端口
SSH_KEY_PATH=~/.ssh/id_rsa            # SSH 私钥路径

# 服务器 IP 地址
DE_1_V4_SSH=203.0.113.10              # 德国测试服务器
PL_1_V4_SSH=203.0.113.20              # 波兰测试服务器（可观测性）
```

### 可选环境变量

```bash
# 可观测性服务地址
PROMETHEUS_URL=http://localhost:9090   # Prometheus 地址
LOKI_URL=http://localhost:3100         # Loki 地址
GRAFANA_URL=http://localhost:3000      # Grafana 地址
```

---

## ⚙️ Ansible 全局变量

配置文件位置：`inventory/group_vars/all/main.yml`

### 1. 时区和本地化

| 变量名 | 默认值 | 说明 | 可选值 |
|--------|--------|------|--------|
| `timezone` | `Asia/Shanghai` | 系统时区 | `UTC`, `America/New_York`, `Europe/London` 等 |
| `locale` | `en_US.UTF-8` | 系统语言环境 | `zh_CN.UTF-8`, `en_GB.UTF-8` 等 |

### 2. 常用软件包

```yaml
common_packages:
  - curl
  - wget
  - vim
  - htop
  - git
  - net-tools
  - telnet
  - unzip
  - tar
  - python3
  - python3-pip
  - chrony
```

### 3. NTP 时间同步

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `ntp_servers` | `["ntp.aliyun.com", "pool.ntp.org"]` | NTP 服务器列表 |

### 4. SSH 配置

| 变量名 | 默认值 | 说明 | 可选值 |
|--------|--------|------|--------|
| `ssh_port` | `22` | SSH 服务端口 | 任意端口号 |
| `ssh_allow_root` | `true` | 是否允许 root 登录 | `true`, `false` |
| `ssh_password_authentication` | `false` | 是否允许密码认证 | `true`, `false` |
| `ssh_pubkey_authentication` | `true` | 是否允许公钥认证 | `true`, `false` |

⚠️ **生产环境建议**：
- `ssh_allow_root: false`
- `ssh_password_authentication: false`
- 使用非标准 SSH 端口

### 5. 防火墙配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `firewall_enabled` | `true` | 是否启用防火墙 |
| `firewall_public_ports` | `[22, 80, 443]` | 公开访问端口列表（无白名单限制） |
| `firewall_restricted_ports` | `[9100, 9080, 9090, 3100, 3000]` | 受限访问端口列表（需要白名单） |

**公开端口说明**（所有 IP 均可访问）：
- `22` - SSH
- `80` - HTTP
- `443` - HTTPS

**受限端口说明**（仅白名单 IP 可访问）：
- `9100` - Prometheus Node Exporter
- `9080` - Promtail (Loki agent)
- `9090` - Prometheus Server
- `3100` - Loki Server
- `3000` - Grafana

### 6. 监控服务白名单

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `monitoring_allowed_ips` | 列表 | 监控服务白名单 IP 列表（从环境变量读取） |
| `monitoring_whitelist` | 列表 | 自动过滤后的白名单（移除空值） |

**配置示例**：
```yaml
monitoring_allowed_ips:
  - "{{ lookup('env', 'DE_1_V4_SSH') | default('') }}"
  - "{{ lookup('env', 'PL_1_V4_SSH') | default('') }}"
```

**工作原理**：
- 从环境变量自动读取所有服务器 IP
- 这些 IP 将被添加到防火墙白名单
- 白名单服务器可以访问所有监控端口
- 其他 IP 将被拒绝访问监控端口

⚠️ **重要提示**：
- 白名单统一应用到所有服务器
- 添加新服务器时，其 IP 会自动加入白名单
- 公开服务（SSH, HTTP, HTTPS）不受白名单限制

### 6. 用户管理

```yaml
admin_users:
  - name: ansible
    shell: /bin/bash
    state: present
```

**说明**：
- Debian/Ubuntu 系统：自动加入 `sudo` 组
- RedHat/CentOS 系统：自动加入 `wheel` 组

### 7. 安全配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `security.fail2ban_enabled` | `true` | 是否启用 Fail2Ban |
| `security.fail2ban_max_retry` | `5` | 最大失败尝试次数 |
| `security.fail2ban_ban_time` | `3600` | 封禁时长（秒） |
| `security.limits` | 见配置文件 | 系统资源限制 |

### 8. 系统内核参数优化

```yaml
sysctl_config:
  net.ipv4.tcp_tw_reuse: 1
  net.ipv4.ip_forward: 0
  net.ipv4.conf.default.rp_filter: 1
  net.ipv4.conf.default.accept_source_route: 0
  kernel.sysrq: 0
  kernel.core_uses_pid: 1
  net.ipv4.tcp_syncookies: 1
  fs.file-max: 65535
  net.core.somaxconn: 1024
  net.ipv4.tcp_max_syn_backlog: 2048
```

### 9. Prometheus 监控配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `prometheus.version` | `2.45.0` | Prometheus 版本 |
| `prometheus.port` | `9090` | Prometheus 服务端口 |
| `prometheus.node_exporter.version` | `1.7.0` | Node Exporter 版本 |
| `prometheus.node_exporter.port` | `9100` | Node Exporter 端口 |
| `prometheus.server_url` | `http://localhost:9090` | Prometheus 服务器地址 |

### 10. Loki 日志配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `loki.version` | `2.9.0` | Loki 版本 |
| `loki.port` | `3100` | Loki 服务端口 |
| `loki.promtail.version` | `2.9.3` | Promtail 版本 |
| `loki.promtail.port` | `9080` | Promtail 端口 |
| `loki.server_url` | `http://localhost:3100` | Loki 服务器地址 |

### 11. Grafana 配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `grafana.url` | `http://localhost:3000` | Grafana 地址 |

### 12. Nginx 配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `nginx.version` | `latest` | Nginx 版本 |
| `nginx.worker_processes` | `auto` | Worker 进程数 |
| `nginx.worker_connections` | `1024` | 每个 Worker 的最大连接数 |
| `nginx.client_max_body_size` | `10M` | 客户端请求体最大大小 |
| `nginx.keepalive_timeout` | `65` | 保持连接超时时间（秒） |

### 13. 应用通用配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `app.deploy_dir` | `/opt/apps` | 应用部署目录 |
| `app.log_dir` | `/var/log/apps` | 应用日志目录 |
| `app.app_user` | `appuser` | 应用运行用户 |
| `app.app_group` | `appgroup` | 应用运行组 |

---

## 🖥️ 服务器节点配置

配置文件位置：`inventory/hosts.yml`

### 当前配置的节点

| 节点名称 | 环境变量 | 所属组 | 角色 | 说明 |
|---------|---------|--------|------|------|
| `de-test-1` | `DE_1_V4_SSH` | `web_servers` | Web 服务器 | 德国测试服务器 |
| `pl-test-1` | `PL_1_V4_SSH` | `web_servers`, `observability` | Web + 可观测性 | 波兰测试服务器 |

### 添加新节点

编辑 `inventory/hosts.yml`，按以下格式添加：

```yaml
all:
  children:
    web_servers:
      hosts:
        your-new-server:
          ansible_host: "{{ lookup('env', 'YOUR_SERVER_IP') }}"
      vars:
        server_role: web
```

**步骤**：
1. 在 `.env` 或 GitHub Secrets 中添加服务器 IP
2. 在 `hosts.yml` 中添加节点配置
3. 更新 `.github/workflows/deploy.yml` 中的环境变量

---

## 🚀 快速配置检查清单

### 本地开发环境

- [ ] 创建 `.env` 文件并配置服务器 IP
- [ ] 配置 SSH 密钥路径
- [ ] 设置 `ANSIBLE_USER` 和 `ANSIBLE_PORT`
- [ ] 测试连接：`ansible all -m ping`

### GitHub Actions CI/CD

- [ ] 上传 `SSH_PRIVATE_KEY` 到 GitHub Secrets
- [ ] 配置 `ANSIBLE_USER` 和 `ANSIBLE_PORT`
- [ ] 配置所有服务器 IP 环境变量（`DE_1_V4_SSH`, `PL_1_V4_SSH`）
- [ ] （可选）配置可观测性服务地址
- [ ] 推送代码到 `deploy` 分支触发部署

### 生产环境安全建议

- [ ] 更改默认 SSH 端口
- [ ] 禁用 root 登录（`ssh_allow_root: false`）
- [ ] 禁用密码认证（仅使用密钥认证）
- [ ] 启用 Fail2Ban 入侵防护
- [ ] 配置防火墙规则，只开放必要端口
- [ ] 定期更新系统和软件包
- [ ] 使用 Ansible Vault 加密敏感数据

---

## 📚 相关文档

- [快速开始指南](QUICKSTART.md)
- [GitHub Actions 配置](docs/GITHUB_ACTIONS_SETUP.md)
- [SSH 密钥管理](docs/SSH_KEY_MANAGEMENT.md)
- [可观测性设置](docs/OBSERVABILITY_SETUP.md)
- [自定义 SSL 配置](docs/CUSTOM_SSL_SETUP.md)

---

## ❓ 常见问题

### Q1: 如何添加新的服务器？

1. 在 `.env` 或 GitHub Secrets 中添加服务器 IP
2. 在 `inventory/hosts.yml` 中添加主机配置
3. 更新 workflow 文件中的环境变量
4. 运行部署：`ansible-playbook -i inventory/hosts.yml playbooks/site.yml`

### Q2: 如何修改默认端口配置？

编辑 `inventory/group_vars/all/main.yml`，修改对应的端口变量（如 `prometheus.port`, `nginx` 配置等）。

### Q3: 如何添加自定义防火墙规则？

修改 `firewall_allowed_ports` 列表，添加需要开放的端口号。

### Q4: 环境变量在哪里生效？

- **本地开发**：在 `.env` 文件中配置，通过 `source .env` 加载
- **GitHub Actions**：在仓库的 Secrets 中配置，自动注入到 workflow 环境
- **Ansible 变量**：在 `inventory/group_vars/all/main.yml` 中定义

---

**最后更新时间**: 2025-10-21  
**项目版本**: 1.0.0  
**维护者**: AnixOps Team
