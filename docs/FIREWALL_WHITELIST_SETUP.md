# 防火墙和监控白名单配置指南

## 📋 概述

本项目实现了统一的防火墙白名单管理机制，用于保护监控服务端口，同时保持公开服务（SSH、HTTP、HTTPS）的可访问性。

## 🎯 设计原则

### 1. 端口分类

**公开端口**（无白名单限制）：
- `22` - SSH
- `80` - HTTP
- `443` - HTTPS

**受限端口**（白名单限制）：
- `9100` - Prometheus Node Exporter
- `9080` - Promtail (Loki agent)
- `9090` - Prometheus Server
- `3100` - Loki Server
- `3000` - Grafana

### 2. 白名单策略

- 所有服务器的 IP 自动加入白名单
- 白名单统一应用到所有服务器
- 新增服务器时，其 IP 自动加入白名单
- 白名单服务器之间可以互相访问监控端口

## 🔧 配置方法

### 步骤 1：配置服务器 IP

在 `.env` 文件中配置所有服务器 IP：

```bash
# 服务器 IP 配置
DE_1_V4_SSH=203.0.113.10
PL_1_V4_SSH=203.0.113.20
# 添加更多服务器...
```

或在 GitHub Secrets 中配置相应的环境变量。

### 步骤 2：验证白名单配置

白名单配置位于 `inventory/group_vars/all/main.yml`：

```yaml
monitoring_allowed_ips:
  - "{{ lookup('env', 'DE_1_V4_SSH') | default('') }}"
  - "{{ lookup('env', 'PL_1_V4_SSH') | default('') }}"
  # 添加新服务器时，在此处添加对应的环境变量
```

### 步骤 3：部署防火墙规则

#### 方式一：使用 quick-setup（推荐新服务器）

```bash
# 初始化新服务器，包含基础配置、监控和防火墙
./scripts/anixops.sh quick-setup

# 或使用 Makefile
make quick-setup
```

#### 方式二：单独配置防火墙（更新现有服务器）

```bash
# 只更新防火墙规则
./scripts/anixops.sh firewall-setup

# 或使用 Makefile
make firewall-setup
```

#### 方式三：完整部署

```bash
# 完整部署包含防火墙配置
./scripts/anixops.sh deploy
```

## 📊 验证配置

### 1. 检查防火墙状态

```bash
# 在目标服务器上查看 UFW 状态
ssh user@server "sudo ufw status verbose"
```

### 2. 测试端口访问

**从白名单服务器测试**（应该成功）：

```bash
# 测试 Node Exporter
curl http://TARGET_IP:9100/metrics

# 测试 Promtail
curl http://TARGET_IP:9080/metrics
```

**从非白名单 IP 测试**（应该失败）：

```bash
# 应该被拒绝
curl http://TARGET_IP:9100/metrics
# Connection refused 或 timeout
```

**测试公开端口**（从任何 IP 都应该成功）：

```bash
# SSH 应该可以连接
ssh user@TARGET_IP

# HTTP 应该可以访问
curl http://TARGET_IP
```

## 🔄 添加新服务器

### 步骤 1：在 .env 或 GitHub Secrets 中添加新服务器 IP

```bash
# .env 文件
NEW_SERVER_V4_SSH=203.0.113.30
```

### 步骤 2：更新白名单配置

编辑 `inventory/group_vars/all/main.yml`：

```yaml
monitoring_allowed_ips:
  - "{{ lookup('env', 'DE_1_V4_SSH') | default('') }}"
  - "{{ lookup('env', 'PL_1_V4_SSH') | default('') }}"
  - "{{ lookup('env', 'NEW_SERVER_V4_SSH') | default('') }}"  # 新增
```

### 步骤 3：更新所有服务器的防火墙规则

```bash
# 在所有服务器上更新防火墙规则
./scripts/anixops.sh firewall-setup
```

### 步骤 4：在新服务器上配置 hosts.yml

编辑 `inventory/hosts.yml`：

```yaml
all:
  children:
    web_servers:
      hosts:
        new-server:
          ansible_host: "{{ lookup('env', 'NEW_SERVER_V4_SSH') }}"
```

### 步骤 5：初始化新服务器

```bash
# 在新服务器上运行 quick-setup
./scripts/anixops.sh quick-setup --limit new-server
```

## 🛡️ 安全建议

### 1. 最小权限原则

只将必要的服务器 IP 添加到白名单。不要添加不需要访问监控服务的 IP。

### 2. 定期审计

```bash
# 定期检查防火墙规则
ansible all -m shell -a "ufw status numbered"

# 检查活动连接
ansible all -m shell -a "netstat -tunlp | grep -E '9100|9080|9090|3100|3000'"
```

### 3. 日志监控

启用防火墙日志：

```bash
# 在目标服务器上启用 UFW 日志
sudo ufw logging on

# 查看日志
sudo tail -f /var/log/ufw.log
```

### 4. 测试隔离

在生产环境应用前，先在测试服务器上验证规则：

```bash
# 只在测试服务器上应用
./scripts/anixops.sh firewall-setup --limit test-server
```

## 🚨 故障排查

### 问题 1：白名单服务器无法访问监控端口

**检查步骤**：

1. 确认 IP 在白名单中：
```bash
# 查看生成的白名单
ansible all -m debug -a "var=monitoring_whitelist"
```

2. 检查防火墙规则：
```bash
ssh user@server "sudo ufw status numbered"
```

3. 验证端口监听：
```bash
ssh user@server "sudo netstat -tunlp | grep 9100"
```

### 问题 2：防火墙规则未生效

**解决方法**：

```bash
# 重新运行防火墙配置
./scripts/anixops.sh firewall-setup --limit TARGET_SERVER

# 手动重启 UFW
ssh user@server "sudo ufw reload"
```

### 问题 3：公开端口被阻止

**检查步骤**：

1. 确认公开端口配置：
```yaml
# 应该在 group_vars/all/main.yml 中
firewall_public_ports:
  - 22
  - 80
  - 443
```

2. 手动添加规则：
```bash
ssh user@server "sudo ufw allow 22/tcp"
ssh user@server "sudo ufw allow 80/tcp"
ssh user@server "sudo ufw allow 443/tcp"
```

## 📚 相关文档

- [PARAMETERS.md](../PARAMETERS.md) - 完整参数配置说明
- [monitoring_firewall Role README](../roles/monitoring_firewall/README.md) - Role 详细文档
- [QUICKSTART.md](../QUICKSTART.md) - 快速开始指南

## 🔗 相关 Playbooks

- `playbooks/firewall-setup.yml` - 独立的防火墙配置 playbook
- `playbooks/quick-setup.yml` - 快速初始化（包含防火墙）
- `playbooks/site.yml` - 完整部署（包含防火墙）

## 💡 最佳实践

1. **新服务器初始化**：使用 `quick-setup` 一次性完成所有配置
2. **更新白名单**：修改白名单后运行 `firewall-setup` 更新所有服务器
3. **定期审计**：每月检查一次防火墙规则和白名单
4. **文档同步**：添加新服务器时同步更新文档
5. **测试验证**：每次修改后进行连接测试

---

**最后更新时间**: 2025-10-21  
**维护者**: AnixOps Team
