# Zero Trust 网络架构方案
# Zero Trust Network Architecture

> 本文档说明 AnixOps 项目中 Cloudflared 和 WARP Connector 的使用场景和架构设计

## 📋 目录

- [架构概述](#架构概述)
- [组件说明](#组件说明)
- [使用场景](#使用场景)
- [部署策略](#部署策略)
- [最佳实践](#最佳实践)

---

## 🏗️ 架构概述

AnixOps 项目采用 **双轨制 Zero Trust 网络架构**，通过 Cloudflare 的两个核心产品实现不同的网络需求：

```
┌─────────────────────────────────────────────────────────────────┐
│                      Cloudflare Zero Trust                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐         ┌─────────────────────┐      │
│  │  Cloudflared Tunnel │         │   WARP Connector    │      │
│  │   (入站流量/Inbound) │         │ (内网互联/Internal)  │      │
│  └─────────────────────┘         └─────────────────────┘      │
│           ↓                                ↓                   │
└───────────┼────────────────────────────────┼───────────────────┘
            ↓                                ↓
    ┌───────────────┐                ┌──────────────┐
    │  公网访问      │                │  服务器内网   │
    │  Public Web   │                │  Private Net │
    └───────────────┘                └──────────────┘
```

---

## 🔧 组件说明

### 1. Cloudflared Tunnel（入站代理）

**用途：** 将 K8s 集群内的 HTTP/HTTPS 服务安全地暴露到公网

**特点：**
- ✅ 无需开放入站端口（No inbound ports）
- ✅ 自动 HTTPS/TLS 终止
- ✅ DDoS 防护
- ✅ 访问控制和身份验证
- ✅ 全球 CDN 加速

**适用场景：**
- Web 应用和网站
- RESTful API 服务
- Webhook 接收端点
- 需要公网访问的任何 HTTP(S) 服务

**部署位置：**
```yaml
K8s Pod Sidecar 模式
├── 主容器（Application Container）
│   └── 你的应用服务（如 nginx, API server）
└── Sidecar 容器（Cloudflared Container）
    └── cloudflared tunnel run
```

**配置示例：**
```yaml
# k8s_manifests/api-with-cloudflared-sidecar/deployment.yaml
containers:
  - name: api-service
    image: your-api:latest
    ports:
      - containerPort: 8080
  
  - name: cloudflared
    image: cloudflare/cloudflared:latest
    args:
      - tunnel
      - --no-autoupdate
      - run
      - --token
      - $(TUNNEL_TOKEN)
    env:
      - name: TUNNEL_TOKEN
        valueFrom:
          secretKeyRef:
            name: cloudflared-secret
            key: TUNNEL_TOKEN
```

---

### 2. WARP Connector（内网互联）

**用途：** 在 Cloudflare 的 Zero Trust 网络中建立服务器间的双向安全连接

**特点：**
- ✅ 服务器之间的直接通信（无需公网暴露）
- ✅ 基于 WireGuard 的加密隧道
- ✅ 零信任访问控制
- ✅ 双向通信（Bidirectional）
- ✅ 支持所有协议（TCP/UDP/ICMP）

**适用场景：**
- 数据库访问（MySQL, PostgreSQL, Redis）
- SSH 远程管理
- 服务器间 RPC 调用
- 内部 API 调用
- 监控和日志采集（Prometheus, Loki）
- Kubernetes 节点间通信

**部署位置：**
```yaml
K8s DaemonSet 或 Deployment
└── WARP Connector Container
    └── cloudflared warp-routing
```

**网络模型：**
```
服务器 A (pl-1)          Cloudflare WARP          服务器 B (de-1)
├── K8s Cluster         ←→ Zero Trust Network ←→   ├── K8s Cluster
│   └── WARP Connector                              │   └── WARP Connector
│                                                   │
└── Internal Services                               └── Internal Services
    ├── Database                                        ├── Database
    ├── Redis                                           ├── Prometheus
    └── Internal APIs                                   └── Grafana
```

---

## 🎯 使用场景对比

| 场景 | Cloudflared Tunnel | WARP Connector | 说明 |
|-----|-------------------|----------------|-----|
| **Web 应用暴露** | ✅ 推荐 | ❌ 不适用 | 需要公网访问的 Web 应用 |
| **API 服务暴露** | ✅ 推荐 | ❌ 不适用 | RESTful API、GraphQL 等 |
| **数据库连接** | ❌ 不推荐 | ✅ 推荐 | 服务器间数据库访问 |
| **SSH 管理** | ⚠️ 可用* | ✅ 推荐 | *需要配置 SSH over HTTP |
| **Prometheus 采集** | ❌ 不适用 | ✅ 推荐 | 监控数据采集 |
| **服务间 RPC** | ❌ 不适用 | ✅ 推荐 | gRPC、Thrift 等 |
| **文件传输** | ⚠️ 可用 | ✅ 推荐 | SFTP、rsync 等 |
| **Webhook 接收** | ✅ 推荐 | ❌ 不适用 | GitHub、GitLab webhooks |

---

## 🚀 部署策略

### 场景 1：单个 Web 应用 + API

```yaml
部署方案：
├── Cloudflared Tunnel (Sidecar)
│   └── 用于暴露 API 到公网
└── WARP Connector (DaemonSet)
    └── 用于访问后端数据库和 Redis
```

**Playbook：**
```bash
# 1. 部署应用（包含 Cloudflared Sidecar）
bash anixops.sh deploy-app-remote -g nginx_test

# 2. 部署 WARP Connector（建立内网连接）
bash anixops.sh deploy-warp -g nginx_test
```

---

### 场景 2：微服务架构

```yaml
部署方案：
├── 前端服务
│   └── Cloudflared Tunnel (Sidecar)
│       └── 暴露前端应用到公网
├── API 网关
│   └── Cloudflared Tunnel (Sidecar)
│       └── 暴露 API 到公网
├── 内部服务 (无 Cloudflared)
│   ├── User Service
│   ├── Order Service
│   └── Payment Service
└── WARP Connector (DaemonSet)
    └── 统一管理所有服务间通信
```

---

### 场景 3：多集群监控（PLG Stack）

```yaml
架构：
┌─────────────────────────────────────────────────────────────┐
│  Monitoring Cluster (pl-1)                                  │
│  ├── Grafana (Cloudflared Tunnel) ← 公网访问 Dashboard      │
│  ├── Prometheus                                             │
│  ├── Loki                                                   │
│  └── WARP Connector ← 通过 WARP 采集其他服务器指标          │
└─────────────────────────────────────────────────────────────┘
                      ↑ WARP Network ↑
         ┌────────────┴────────────┬────────────┐
         │                         │            │
┌────────┴────────┐    ┌───────────┴──────┐   ┌┴──────────┐
│ App Cluster 1   │    │ App Cluster 2    │   │ Servers   │
│ └── WARP        │    │ └── WARP         │   │ └── WARP  │
│ └── Node Exp.   │    │ └── Promtail     │   │ └── Exporter│
└─────────────────┘    └──────────────────┘   └───────────┘
```

**Playbook：**
```bash
# 1. 部署监控集群（pl-1）
ansible-playbook playbooks/deployment/deploy_monitoring.yml

# 2. 在所有服务器部署 WARP Connector（宿主机方式）
ansible-playbook playbooks/deployment/deploy_warp_host.yml -e "warp_token=YOUR_TOKEN"

# 注: 使用 ansible.cfg 中配置的默认 inventory (inventory/hosts.yml)
```

---

## 📚 最佳实践

### 1. 安全策略

**Cloudflared Tunnel：**
- ✅ 使用 Cloudflare Access 进行身份验证
- ✅ 启用 WAF 规则保护应用
- ✅ 限制 IP 白名单（如需要）
- ✅ 定期轮换 Tunnel Token

**WARP Connector：**
- ✅ 使用 Zero Trust Gateway 策略控制访问
- ✅ 启用设备态势检查（Device Posture）
- ✅ 配置网络隔离策略
- ✅ 定期审计访问日志

---

### 2. 性能优化

**Cloudflared：**
```yaml
# 建议配置
resources:
  requests:
    memory: "64Mi"
    cpu: "100m"
  limits:
    memory: "128Mi"
    cpu: "200m"

# 多副本提高可用性
replicas: 2
```

**WARP Connector：**
```yaml
# DaemonSet 模式（每个节点一个）
kind: DaemonSet
# 或者 Deployment 模式（集中式）
kind: Deployment
replicas: 1  # 通常一个足够
```

---

### 3. 故障排除

**Cloudflared 连接问题：**
```bash
# 查看 cloudflared 日志
kubectl logs -n <namespace> <pod-name> -c cloudflared

# 检查 Tunnel 状态
kubectl exec -it <pod-name> -c cloudflared -- cloudflared tunnel info
```

**WARP Connector 连接问题：**
```bash
# 查看 WARP 日志
kubectl logs -n warp-connector <pod-name>

# 检查路由表
kubectl exec -it <warp-pod> -- ip route

# 测试连接
kubectl exec -it <warp-pod> -- ping <internal-ip>
```

---

## 🔗 相关文档

- [Cloudflared 快速开始](./CLOUDFLARED_QUICKSTART.md)
- [零信任网络配置](./ZERO_TRUST_NETWORK.md)
- [监控系统部署](./OBSERVABILITY_SETUP.md)

---

## 📞 架构决策记录

### 为什么选择双轨制？

**传统单一方案的问题：**
- ❌ 只用 Cloudflared：无法实现服务器间高效通信
- ❌ 只用 VPN：缺少现代化的访问控制和 DDoS 防护
- ❌ 只用公网暴露：安全风险高，管理复杂

**双轨制的优势：**
- ✅ **职责分离**：公网访问和内网互联各司其职
- ✅ **灵活性**：可独立扩展和配置
- ✅ **安全性**：多层防护，最小权限原则
- ✅ **性能**：针对不同场景优化
- ✅ **可观测性**：统一的日志和监控

---

## 📝 版本历史

| 版本 | 日期 | 说明 |
|-----|------|-----|
| 1.0 | 2025-10-29 | 初始版本，定义双轨制架构 |

---

**维护者：** AnixOps Team  
**最后更新：** 2025-10-29
