# Cloudflare Mesh Role

部署 Cloudflare Mesh 节点，实现服务器间原生 IP 路由（替代 Headscale/Tailscale 和旧的 WARP Connector）。

## 功能

- 安装 `cloudflare-warp` 包（Debian/Ubuntu 和 RHEL/CentOS）
- 使用 enrollment token 注册节点到 Mesh 网络
- 配置 sysctl（IPv4/IPv6 forwarding）
- 设置 MTU 1381（Mesh 接口）
- 验证连接状态

## 架构

Cloudflare Mesh 提供：
- **原生 IP 路由**：TCP、UDP、ICMP 全协议支持
- **地址空间**：`100.96.0.0/12`（Carrier-grade NAT，避免与 RFC 1918 冲突）
- **零信任安全**：Dashboard 端集中管理访问控制和设备验证
- **高可用**：支持 active-passive replica 配置

## 使用方法

### 1. 获取 Mesh Token

从 Cloudflare Dashboard 获取 enrollment token：

1. 登录 https://one.dash.cloudflare.com/
2. 导航到 **Networking > Mesh**
3. 点击 **Add node**
4. 复制 enrollment token（CLI enrollment string）

### 2. 配置环境变量

```bash
# .env 或 GitHub Secrets
CLOUDFLARE_MESH_TOKEN=eyJh...your-enrollment-token
CLOUDFLARE_MESH_NODE_NAME=server-jp-1   # 可选
CLOUDFLARE_MESH_ADVERTISE_SUBNETS=10.0.0.0/24  # 可选
```

### 3. 部署

```bash
# 部署 Mesh 节点
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/site.yml --tags cloudflare_mesh

# 或限制到 mesh_nodes 组
ansible-playbook -i inventories/production/hosts.yml playbooks/provision/site.yml --limit mesh_nodes
```

### 4. 配置路由

部署完成后，在 Dashboard 配置路由：

1. **Networking > Mesh > Routes**
2. 为每个节点配置要广播的子网
3. 配置访问策略（哪些节点可以访问哪些子网）

## 变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `cloudflare_mesh_token` | `{{ lookup('env', 'CLOUDFLARE_MESH_TOKEN') }}` | Enrollment token |
| `cloudflare_mesh_node_name` | `{{ inventory_hostname }}` | 节点显示名称 |
| `cloudflare_mesh_mtu` | `1381` | Mesh 接口 MTU |
| `cloudflare_mesh_advertise_subnets` | `{{ lookup('env', 'CLOUDFLARE_MESH_ADVERTISE_SUBNETS') }}` | 要广播的子网 |
| `cloudflare_mesh_service_name` | `warp-svc` | systemd 服务名 |

## 验证

```bash
# 检查节点状态
warp-cli status

# 查看 Mesh 接口
ip addr show CloudflareMesh

# 测试连通性（假设另一节点地址为 100.96.1.2）
ping 100.96.1.2
```

## 与旧方案对比

| 特性 | Headscale/Tailscale | Cloudflare Tunnel | Cloudflare Mesh |
|------|--------------------|------------------|-----------------|
| 路由方式 | WireGuard overlay | HTTP proxy | 原生 IP (L3) |
| 协议支持 | TCP/UDP | HTTP/WebSocket | TCP/UDP/ICMP |
| 地址空间 | 100.64.0.0/10 | 无 | 100.96.0.0/12 |
| 管理界面 | Headscale CLI | Dashboard | Dashboard |
| 部署复杂度 | 中 | 低 | 低 |

## 回滚

Mesh 节点配置不生成备份文件。回滚需要：

1. Dashboard 端移除节点：Networking > Mesh > Nodes > Delete
2. 服务器端取消注册：`warp-cli disconnect && warp-cli registration delete`
3. 停止服务：`systemctl stop warp-svc`

## 参考

- [Cloudflare Mesh Documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-mesh/)
- [Get Started with Cloudflare Mesh](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-mesh/get-started/)