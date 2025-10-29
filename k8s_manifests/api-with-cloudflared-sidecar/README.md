# API Service with Cloudflared Sidecar - 部署指南

## 📋 概述

此配置使用 **Sidecar 模式** 部署 API 服务，通过 Cloudflare Tunnel 安全地将服务暴露到互联网。

### 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│              Kubernetes Pod                 │
│                                             │
│  ┌──────────────────┐  ┌─────────────────┐ │
│  │                  │  │                 │ │
│  │  my-api-service  │  │  cloudflared    │ │
│  │                  │  │  sidecar        │ │
│  │  监听: :8080      │◄─┤                 │ │
│  │                  │  │  转发到:        │ │
│  │                  │  │  localhost:8080 │ │
│  └──────────────────┘  └─────────────────┘ │
│           │                      ▲          │
│           └──────────────────────┘          │
│            共享 localhost 网络空间           │
└─────────────────────────────────────────────┘
                        ▲
                        │
                Cloudflare Tunnel
                        │
                        ▼
                  Internet 用户
```

### ✨ 核心特性

- **🔒 安全性**: 使用 Cloudflare Tunnel，无需暴露公网 IP
- **🚀 高可用**: 支持多副本部署，自动故障转移
- **📊 可观测**: 集成 Prometheus Metrics
- **⚡ 自动扩缩**: 支持 HPA（水平自动扩缩容）
- **🛡️ 健康检查**: 完善的存活和就绪探针
- **🔄 滚动更新**: 零停机更新部署

## 📦 文件清单

```
api-with-cloudflared-sidecar/
├── README.md                        # 本文件
├── api-deployment-sidecar.yaml      # 主要部署配置
└── deploy.sh                        # 快速部署脚本（待创建）
```

## 🚀 快速开始

### 前置要求

1. ✅ Kubernetes 集群已运行（v1.19+）
2. ✅ kubectl 已配置并能访问集群
3. ✅ 已获取 Cloudflare Tunnel Token
4. ✅ 你的 API 镜像已构建并推送到镜像仓库

### 步骤 1: 准备 Cloudflare Tunnel Token

首先，获取你的 Cloudflare Tunnel Token 并进行 base64 编码：

```bash
# 将你的 Token 进行 base64 编码
echo -n "eyJhIjoiY2FmZS0xMjM0..." | base64

# 输出示例:
# ZXlKaElqb2lZMkZtWlMweE1qTTAuLi4=
```

### 步骤 2: 修改配置文件

编辑 `api-deployment-sidecar.yaml` 文件，替换以下占位符：

#### 2.1 替换 Secret 中的 Token

找到 Secret 部分，将 `TUNNEL_TOKEN` 的值替换为你的 base64 编码的 Token：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cloudflared-secret
  namespace: default  # 修改为你的 namespace
data:
  TUNNEL_TOKEN: ZXlKaElqb2lZMkZtWlMweE1qTTAuLi4=  # 替换这里
```

#### 2.2 替换 API 镜像

找到 Deployment 中的 `my-api-service` 容器，替换镜像：

```yaml
containers:
  - name: my-api-service
    image: your-registry.com/your-api:v1.0.0  # 替换为你的实际镜像
```

#### 2.3 修改健康检查路径（如果需要）

如果你的 API 的健康检查路径不是 `/health` 和 `/ready`，请修改：

```yaml
livenessProbe:
  httpGet:
    path: /health  # 修改为你的健康检查路径
    port: 8080

readinessProbe:
  httpGet:
    path: /ready   # 修改为你的就绪检查路径
    port: 8080
```

### 步骤 3: 部署到 Kubernetes

```bash
# 部署所有资源
kubectl apply -f api-deployment-sidecar.yaml

# 或者，如果你只想部署特定资源：
# kubectl apply -f api-deployment-sidecar.yaml --namespace your-namespace
```

### 步骤 4: 验证部署

```bash
# 查看 Pod 状态
kubectl get pods -l app=api-service

# 查看 Pod 详细信息
kubectl describe pod -l app=api-service

# 查看 cloudflared 日志
kubectl logs -l app=api-service -c cloudflared-sidecar --follow

# 查看 API 服务日志
kubectl logs -l app=api-service -c my-api-service --follow
```

期望输出：

```
NAME                                      READY   STATUS    RESTARTS   AGE
api-service-with-tunnel-xxxx-yyyy         2/2     Running   0          1m
api-service-with-tunnel-xxxx-zzzz         2/2     Running   0          1m
```

✅ `READY` 列显示 `2/2` 表示两个容器都已就绪。

## 🔧 配置说明

### 资源配置

#### API 服务资源

```yaml
resources:
  requests:
    cpu: "100m"      # 请求 0.1 核 CPU
    memory: "128Mi"  # 请求 128MB 内存
  limits:
    cpu: "500m"      # 限制 0.5 核 CPU
    memory: "512Mi"  # 限制 512MB 内存
```

根据你的实际负载调整这些值。

#### Cloudflared Sidecar 资源

```yaml
resources:
  requests:
    cpu: "50m"       # 请求 0.05 核 CPU
    memory: "64Mi"   # 请求 64MB 内存
  limits:
    cpu: "200m"      # 限制 0.2 核 CPU
    memory: "256Mi"  # 限制 256MB 内存
```

通常 cloudflared 资源消耗较低，这些默认值适用于大多数场景。

### 副本配置

默认配置为 2 个副本以实现高可用：

```yaml
replicas: 2
```

如果启用了 HPA（水平自动扩缩容），副本数将在 2-10 之间自动调整。

### 自动扩缩容（HPA）

配置文件包含了 HPA 资源，会根据以下指标自动扩缩容：

- **CPU 使用率**: 达到 70% 时扩容
- **内存使用率**: 达到 80% 时扩容
- **副本范围**: 2-10 个副本

如果不需要 HPA，可以删除配置文件中的 HPA 部分。

## 🔍 故障排查

### 问题 1: Pod 无法启动

```bash
# 查看 Pod 事件
kubectl describe pod -l app=api-service

# 查看容器日志
kubectl logs -l app=api-service -c my-api-service
kubectl logs -l app=api-service -c cloudflared-sidecar
```

常见原因：
- ❌ 镜像拉取失败（检查镜像名称和凭据）
- ❌ Secret 不存在或 Token 错误
- ❌ 资源不足（检查节点资源）

### 问题 2: Cloudflared 连接失败

```bash
# 查看 cloudflared 日志
kubectl logs -l app=api-service -c cloudflared-sidecar --tail=100

# 检查 Secret
kubectl get secret cloudflared-secret -o yaml
```

常见原因：
- ❌ Tunnel Token 无效或已过期
- ❌ Token 未正确 base64 编码
- ❌ 网络连接问题

### 问题 3: 健康检查失败

```bash
# 进入 Pod 测试健康检查端点
kubectl exec -it <pod-name> -c my-api-service -- /bin/sh
# 在容器内运行:
wget -O- http://localhost:8080/health
```

常见原因：
- ❌ 健康检查路径不正确
- ❌ API 服务启动时间过长
- ❌ API 服务监听端口不是 8080

## 📊 监控和指标

### Prometheus 集成

配置文件已包含 Prometheus annotations：

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "2000"
  prometheus.io/path: "/metrics"
```

如果你的集群安装了 Prometheus，它会自动抓取 cloudflared 的指标。

### 查看 Metrics

```bash
# 端口转发到本地
kubectl port-forward deployment/api-service-with-tunnel 2000:2000

# 在浏览器访问或使用 curl
curl http://localhost:2000/metrics
```

## 🔐 安全最佳实践

1. **Secret 管理**: 
   - 使用 Sealed Secrets 或外部 Secret 管理器（如 HashiCorp Vault）
   - 不要将 Secret 提交到版本控制系统

2. **非 root 运行**:
   - 配置文件已包含 `runAsNonRoot: true`
   - 容器以用户 ID 65532 运行

3. **资源限制**:
   - 始终设置资源限制以防止资源耗尽攻击

4. **网络策略**:
   - 考虑添加 NetworkPolicy 限制 Pod 间通信

## 🔄 更新和维护

### 更新 API 镜像

```bash
# 方法 1: 编辑部署配置
kubectl edit deployment api-service-with-tunnel

# 方法 2: 使用 kubectl set image
kubectl set image deployment/api-service-with-tunnel \
  my-api-service=your-registry.com/your-api:v1.0.1

# 查看滚动更新状态
kubectl rollout status deployment/api-service-with-tunnel
```

### 回滚部署

```bash
# 查看历史版本
kubectl rollout history deployment/api-service-with-tunnel

# 回滚到上一个版本
kubectl rollout undo deployment/api-service-with-tunnel

# 回滚到特定版本
kubectl rollout undo deployment/api-service-with-tunnel --to-revision=2
```

### 更新 Cloudflared 镜像

```bash
kubectl set image deployment/api-service-with-tunnel \
  cloudflared-sidecar=cloudflare/cloudflared:2024.11.0
```

## 📚 进阶配置

### 配置 Cloudflare Tunnel 路由

在 Cloudflare Dashboard 中配置你的 Tunnel 路由：

1. 访问 [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. 导航到 **Access** → **Tunnels**
3. 选择你的 Tunnel
4. 配置 **Public Hostname**:
   - **Subdomain**: `api`
   - **Domain**: `yourdomain.com`
   - **Service**: `http://localhost:8080` (已自动配置)

### 多环境部署

如果你有多个环境（开发、测试、生产），可以使用不同的 namespace：

```bash
# 开发环境
kubectl apply -f api-deployment-sidecar.yaml --namespace dev

# 测试环境
kubectl apply -f api-deployment-sidecar.yaml --namespace staging

# 生产环境
kubectl apply -f api-deployment-sidecar.yaml --namespace prod
```

记得为每个环境修改配置文件中的 namespace。

## 🗑️ 清理资源

```bash
# 删除所有资源
kubectl delete -f api-deployment-sidecar.yaml

# 或者删除特定资源
kubectl delete deployment api-service-with-tunnel
kubectl delete service api-service
kubectl delete secret cloudflared-secret
kubectl delete hpa api-service-hpa
kubectl delete pdb api-service-pdb
```

## 📖 参考资源

- [Cloudflare Tunnel 文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Kubernetes Sidecar 模式](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
- [Kubernetes HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Prometheus 监控](https://prometheus.io/docs/introduction/overview/)

## 💬 支持

如有问题或建议，请：
- 📝 提交 Issue
- 💬 查看项目文档
- 🔧 联系 DevOps 团队

---

**维护者**: AnixOps Team  
**最后更新**: 2024-10-29  
**版本**: 1.0.0
