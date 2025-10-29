# Headscale 快速参考 | Headscale Quick Reference

本文档提供 Headscale 部署和管理的快速参考指南。

This document provides a quick reference guide for Headscale deployment and management.

---

## 📋 目录 | Table of Contents

- [什么是 Headscale](#什么是-headscale)
- [架构概览](#架构概览)
- [快速开始](#快速开始)
- [环境变量配置](#环境变量配置)
- [部署步骤](#部署步骤)
- [常用命令](#常用命令)
- [故障排查](#故障排查)
- [与 Netmaker 的区别](#与-netmaker-的区别)

---

## 什么是 Headscale

Headscale 是 Tailscale 控制服务器的开源实现，允许你在自己的服务器上部署完整的 VPN mesh 网络。

**主要特性:**
- ✅ 完全开源，无商业许可限制
- ✅ 基于 WireGuard，性能优异
- ✅ 自动 NAT 穿透
- ✅ MagicDNS 支持
- ✅ ACL (访问控制列表) 支持
- ✅ 支持 iOS、Android、Windows、macOS、Linux

**与 Tailscale 的关系:**
- Headscale = 自托管的 Tailscale 协调服务器
- 客户端使用标准的 Tailscale 客户端
- 数据流量不经过 Headscale 服务器 (点对点加密)

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Headscale Server (PL-1)                   │
│                    145.239.90.226:8080                       │
│                                                               │
│  - 协调节点注册 | Coordinate node registration              │
│  - 管理网络拓扑 | Manage network topology                   │
│  - 分配 IP 地址 | Assign IP addresses                       │
│  - ACL 策略管理 | ACL policy management                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼──────┐   ┌───────▼──────┐   ┌───────▼──────┐
│   DE-1       │   │   JP-1       │   │   UK-1       │
│ (Germany)    │◄──┤  (Japan)     │◄──┤    (UK)      │
│ Tailscale    │   │  Tailscale   │   │  Tailscale   │
└──────────────┘   └──────────────┘   └──────┬───────┘
                                              │
                                     ┌────────▼────────┐
                                     │     SG-1        │
                                     │  (Singapore)    │
                                     │   Tailscale     │
                                     └─────────────────┘

IP 分配范围 | IP Allocation Range:
  IPv4: 100.64.0.0/10
  IPv6: fd7a:115c:a1e0::/48
```

**数据流:**
1. **控制平面 (Control Plane):** 所有客户端连接到 Headscale 服务器注册
2. **数据平面 (Data Plane):** 客户端之间直接点对点通信 (P2P)
3. **DERP 中继:** 当 P2P 不可用时，通过 DERP 服务器中继

---

## 快速开始

### 前提条件

- Ansible 2.9+
- Python 3.6+
- 所有目标服务器运行 Debian/Ubuntu
- 服务器之间可以通过 SSH 访问
- `.env` 文件已配置

### 一键部署

```bash
# 1. 配置环境变量
cp .env.example .env
vim .env  # 配置服务器 IP

# 2. 运行部署脚本
./scripts/deploy_headscale.sh

# 3. 选择部署模式
# 选项 3: 完整部署 (服务器 + 客户端)
```

---

## 环境变量配置

### 必需变量

在 `.env` 文件中配置:

```bash
# ===========================================
# 服务器 IP 配置
# ===========================================
PL_1_V4_SSH=145.239.90.226    # Headscale 服务器
DE_1_V4_SSH=205.198.92.139    # 客户端 1
JP_1_V4_SSH=141.147.188.180   # 客户端 2
UK_1_V4_SSH=130.162.179.124   # 客户端 3
SG_1_V4_SSH=8.219.200.105     # 客户端 4

# ===========================================
# Headscale 配置
# ===========================================
# HEADSCALE_SERVER_URL="http://145.239.90.226:8080"  # 可选，默认使用 PL_1_V4_SSH
# HEADSCALE_PREAUTH_KEY=""                           # 自动生成，或手动设置
HEADSCALE_NAMESPACE="default"                       # 默认命名空间
```

### GitHub Actions 配置

在 GitHub Repository Settings -> Secrets 中添加:

```
PL_1_V4_SSH=145.239.90.226
DE_1_V4_SSH=205.198.92.139
JP_1_V4_SSH=141.147.188.180
UK_1_V4_SSH=130.162.179.124
SG_1_V4_SSH=8.219.200.105
```

---

## 部署步骤

### 方式 1: 完整自动化部署 (推荐)

```bash
./scripts/deploy_headscale.sh
# 选择选项 3: 完整部署
```

**流程:**
1. 部署 Headscale 服务器到 PL-1
2. 自动生成 pre-auth key
3. 部署 Tailscale 客户端到所有节点
4. 自动注册所有客户端

---

### 方式 2: 分步部署

#### Step 1: 部署 Headscale 服务器

```bash
ansible-playbook playbooks/headscale/deploy_server.yml
```

**验证:**
```bash
ssh root@145.239.90.226
systemctl status headscale
curl http://localhost:8080/health
```

#### Step 2: 生成 Pre-Auth Key

```bash
ssh root@145.239.90.226
headscale preauthkeys create --namespace default --reusable --expiration 24h
```

**输出示例:**
```json
{
  "id": "1",
  "key": "preauthkey-abcdefghijklmnopqrstuvwxyz123456",
  "reusable": true,
  "ephemeral": false,
  "used": false,
  "expiration": "2024-11-01T00:00:00Z",
  "created_at": "2024-10-31T00:00:00Z",
  "acl_tags": []
}
```

复制 `key` 字段的值。

#### Step 3: 设置环境变量

```bash
export HEADSCALE_PREAUTH_KEY="preauthkey-abcdefghijklmnopqrstuvwxyz123456"
```

#### Step 4: 部署客户端

```bash
ansible-playbook playbooks/headscale/deploy_clients.yml
```

#### Step 5: 验证网络

```bash
ssh root@145.239.90.226
headscale nodes list
```

**输出示例:**
```
ID | Hostname | Name    | NodeKey | Namespace | IP addresses        | Online | Last seen
1  | de-1     | de-1    | ...     | default   | 100.64.0.1          | online | 2024-10-31 00:00:00
2  | jp-1     | jp-1    | ...     | default   | 100.64.0.2          | online | 2024-10-31 00:00:00
3  | uk-1     | uk-1    | ...     | default   | 100.64.0.3          | online | 2024-10-31 00:00:00
4  | sg-1     | sg-1    | ...     | default   | 100.64.0.4          | online | 2024-10-31 00:00:00
```

---

## 常用命令

### Headscale 服务器管理

```bash
# 查看服务状态
systemctl status headscale

# 启动/停止/重启服务
systemctl start headscale
systemctl stop headscale
systemctl restart headscale

# 查看日志
journalctl -u headscale -f

# 查看配置
cat /etc/headscale/config.yaml
```

### 节点管理

```bash
# 列出所有节点
headscale nodes list

# 查看特定节点详情
headscale nodes show 1

# 删除节点
headscale nodes delete 1

# 重命名节点
headscale nodes rename 1 new-name
```

### 命名空间管理

```bash
# 列出所有命名空间
headscale namespaces list

# 创建命名空间
headscale namespaces create production

# 删除命名空间
headscale namespaces destroy production
```

### Pre-Auth Key 管理

```bash
# 创建 pre-auth key (一次性)
headscale preauthkeys create --namespace default --expiration 1h

# 创建可重复使用的 key
headscale preauthkeys create --namespace default --reusable --expiration 24h

# 创建 ephemeral (临时) key
headscale preauthkeys create --namespace default --ephemeral

# 列出所有 keys
headscale preauthkeys list --namespace default

# 删除 key
headscale preauthkeys expire --namespace default <key-id>
```

### 路由管理

```bash
# 列出所有路由
headscale routes list

# 启用子网路由
headscale routes enable -i <node-id> -r <route>

# 禁用路由
headscale routes disable -i <node-id> -r <route>
```

### ACL 管理

```bash
# 验证 ACL 配置
headscale acl check

# 重新加载 ACL
systemctl reload headscale
```

---

## Tailscale 客户端命令

在客户端节点上执行:

```bash
# 查看连接状态
tailscale status

# 查看 IP 地址
tailscale ip -4
tailscale ip -6

# Ping 其他节点
tailscale ping de-1
tailscale ping 100.64.0.1

# 查看详细状态
tailscale status --json

# 断开连接
tailscale down

# 重新连接
tailscale up --login-server=http://145.239.90.226:8080

# 查看日志
journalctl -u tailscaled -f
```

---

## 故障排查

### 问题 1: 客户端无法连接到 Headscale 服务器

**症状:**
```
Failed to connect to http://145.239.90.226:8080
```

**解决方案:**
1. 检查 Headscale 服务状态:
   ```bash
   ssh root@145.239.90.226
   systemctl status headscale
   ```

2. 检查防火墙:
   ```bash
   sudo ufw allow 8080/tcp
   sudo ufw allow 50443/tcp
   ```

3. 测试连接:
   ```bash
   curl http://145.239.90.226:8080/health
   ```

---

### 问题 2: Pre-Auth Key 过期

**症状:**
```
Error: preauthkey expired
```

**解决方案:**
```bash
# 生成新的 key
ssh root@145.239.90.226
headscale preauthkeys create --namespace default --reusable --expiration 24h

# 更新环境变量
export HEADSCALE_PREAUTH_KEY="new-key-here"

# 重新部署客户端
ansible-playbook playbooks/headscale/deploy_clients.yml
```

---

### 问题 3: 节点之间无法通信

**症状:**
```bash
tailscale ping 100.64.0.2
# Timeout
```

**解决方案:**

1. 检查节点状态:
   ```bash
   ssh root@145.239.90.226
   headscale nodes list
   ```

2. 检查路由:
   ```bash
   headscale routes list
   ```

3. 在客户端重启 Tailscale:
   ```bash
   systemctl restart tailscaled
   tailscale up --login-server=http://145.239.90.226:8080
   ```

4. 检查 ACL 配置:
   ```bash
   cat /etc/headscale/acl.yaml
   ```

---

### 问题 4: DNS 解析失败

**症状:**
```bash
ping de-1
# Name or service not known
```

**解决方案:**

1. 检查 MagicDNS 配置:
   ```bash
   cat /etc/headscale/config.yaml | grep -A 10 dns
   ```

2. 确认配置:
   ```yaml
   dns_config:
     magic_dns: true
     base_domain: anixops.internal
   ```

3. 重启 Headscale:
   ```bash
   systemctl restart headscale
   ```

4. 在客户端重新连接:
   ```bash
   tailscale down
   tailscale up --login-server=http://145.239.90.226:8080 --accept-dns
   ```

---

## 与 Netmaker 的区别

| 特性 | Headscale | Netmaker |
|------|-----------|----------|
| **开源协议** | BSD-3 | SSPL (商业限制) |
| **客户端** | Tailscale (官方) | 自定义客户端 |
| **安装复杂度** | 简单 | 中等 |
| **NAT 穿透** | 优秀 | 良好 |
| **性能** | 优秀 (WireGuard) | 优秀 (WireGuard) |
| **Web UI** | 无 (命令行) | 有 |
| **移动端支持** | iOS/Android (官方) | 有限 |
| **维护活跃度** | 高 | 中 |
| **社区支持** | 活跃 | 中等 |
| **商业支持** | 无 (自托管) | 有 (付费) |

**选择建议:**
- ✅ **Headscale:** 适合技术团队，追求稳定性和开源
- ⚠️ **Netmaker:** 需要 Web UI，可能有商业需求

---

## 高级配置

### 1. 配置自定义 DERP 服务器

编辑 `/etc/headscale/config.yaml`:

```yaml
derp:
  server:
    enabled: true
    region_id: 999
    region_code: "custom"
    region_name: "Custom DERP"
    stun_listen_addr: "0.0.0.0:3478"
```

重启服务:
```bash
systemctl restart headscale
```

---

### 2. 配置 ACL (访问控制)

编辑 `/etc/headscale/acl.yaml`:

```yaml
acls:
  - action: accept
    src:
      - "default:*"
    dst:
      - "default:*:*"

# 只允许特定节点访问
  - action: accept
    src:
      - "default:de-1"
    dst:
      - "default:pl-1:22"  # 只能 SSH 到 pl-1
```

重新加载:
```bash
systemctl reload headscale
```

---

### 3. 启用子网路由

**在路由节点上:**
```bash
# 启用 IP 转发
echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.conf
echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# 配置 Tailscale 路由
tailscale up --advertise-routes=192.168.1.0/24
```

**在 Headscale 服务器上:**
```bash
headscale routes list
headscale routes enable -i <node-id> -r 192.168.1.0/24
```

---

## 安全最佳实践

1. **使用 HTTPS:**
   - 配置 Nginx/Caddy 作为反向代理
   - 使用 Let's Encrypt SSL 证书

2. **限制 API 访问:**
   - 只监听内网地址: `listen_addr: 127.0.0.1:8080`
   - 使用防火墙限制访问

3. **Pre-Auth Key 管理:**
   - 使用短期 key (1-24h)
   - 不要重复使用 key (除非必要)
   - 定期轮换 key

4. **ACL 策略:**
   - 遵循最小权限原则
   - 定期审查 ACL 规则
   - 记录所有访问

5. **日志监控:**
   - 配置 Prometheus metrics
   - 集成到 Grafana
   - 设置告警

---

## 相关文档

- [Headscale 部署总结](./HEADSCALE_DEPLOYMENT_SUMMARY.md)
- [Headscale 快速入门](./HEADSCALE_QUICK_START.md)
- [GitHub Actions 配置](./GITHUB_ACTIONS_SETUP.md)
- [环境变量参考](./PARAMETERS.md)

---

## 技术支持

- **官方文档:** https://headscale.net/
- **GitHub:** https://github.com/juanfont/headscale
- **Discord:** https://discord.gg/headscale
- **项目 Issues:** https://github.com/juanfont/headscale/issues

---

**最后更新:** 2024-10-31  
**版本:** 1.0.0  
**维护者:** AnixOps Team
