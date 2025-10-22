# Monitoring Firewall Role

## 功能说明

此角色负责管理监控服务的防火墙规则，实现以下功能：

1. **公开端口管理**：配置无需白名单即可访问的端口（SSH, HTTP, HTTPS）
2. **受限端口管理**：配置需要白名单才能访问的监控端口
3. **IP 白名单**：统一管理所有服务器的监控访问权限
4. **防火墙支持**：同时支持 UFW (Debian/Ubuntu) 和 firewalld (RedHat/CentOS)

## 配置说明

### 公开端口（无白名单）

以下端口对所有 IP 开放：
- `22` - SSH
- `80` - HTTP
- `443` - HTTPS

### 受限端口（需要白名单）

以下端口仅对白名单 IP 开放：
- `9100` - Prometheus Node Exporter
- `9080` - Promtail (Loki agent)
- `9090` - Prometheus Server
- `3100` - Loki Server
- `3000` - Grafana

### 白名单配置

在 `inventory/group_vars/all/main.yml` 中配置：

```yaml
monitoring_allowed_ips:
  - "{{ lookup('env', 'DE_1_V4_SSH') | default('') }}"
  - "{{ lookup('env', 'PL_1_V4_SSH') | default('') }}"
```

## 使用方法

### 方式一：独立运行

```bash
ansible-playbook playbooks/firewall-setup.yml
```

### 方式二：集成到其他 playbook

```yaml
roles:
  - monitoring_firewall
```

## 变量说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `firewall_enabled` | `true` | 是否启用防火墙 |
| `firewall_public_ports` | `[22, 80, 443]` | 公开访问端口列表 |
| `firewall_restricted_ports` | `[9100, 9080, 9090, 3100, 3000]` | 受限访问端口列表 |
| `monitoring_allowed_ips` | 见配置文件 | 监控服务白名单 IP 列表 |
| `monitoring_whitelist` | 自动生成 | 过滤后的白名单（移除空值） |

## 安全建议

1. **最小权限原则**：仅将必要的服务器 IP 添加到白名单
2. **定期审计**：定期检查防火墙规则和白名单
3. **监控日志**：启用 UFW/firewalld 日志记录
4. **测试连接**：添加新 IP 后测试监控服务可访问性

## 故障排查

### 查看 UFW 状态
```bash
sudo ufw status verbose
```

### 查看 firewalld 规则
```bash
sudo firewall-cmd --list-all
```

### 测试端口连通性
```bash
# 从白名单服务器测试
curl http://TARGET_SERVER:9100/metrics
```
