# Cloudflare Tunnel for Kubernetes

[![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.25+-blue)](https://kubernetes.io/)
[![Cloudflare](https://img.shields.io/badge/Cloudflare-Tunnel-orange)](https://www.cloudflare.com/products/tunnel/)

> 将 Cloudflare Tunnel 部署为 Kubernetes Deployment，实现零公网 IP 暴露的安全入口流量管理

---

## 📁 文件结构

```
cloudflared/
├── 00-namespace.yaml       # Namespace 定义
├── 01-secret.yaml          # Secret 模板（Token 存储）
├── 02-configmap.yaml       # ConfigMap（cloudflared 配置）
├── 03-deployment.yaml      # Deployment（cloudflared Pods）
├── 04-hpa.yaml             # HorizontalPodAutoscaler（自动扩缩容）
├── 05-pdb.yaml             # PodDisruptionBudget（高可用保障）
├── deploy.sh               # 一键部署脚本
└── README.md               # 本文档
```

---

## 🚀 快速开始

### 方法 1: 使用一键部署脚本（推荐）

```bash
# 1. 进入目录
cd k8s_manifests/cloudflared

# 2. 运行部署脚本
./deploy.sh

# 3. 按照提示输入你的 Cloudflare Tunnel Token
```

### 方法 2: 手动部署

```bash
# 1. 创建 Namespace
kubectl apply -f 00-namespace.yaml

# 2. 创建 Secret（替换为你的实际 Token）
export CF_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
kubectl create secret generic cloudflared-token \
  --from-literal=token=$CF_TUNNEL_TOKEN \
  --namespace=cloudflare-tunnel

# 3. 创建 ConfigMap
kubectl apply -f 02-configmap.yaml

# 4. 部署 Deployment
kubectl apply -f 03-deployment.yaml

# 5. (可选) 部署 HPA
kubectl apply -f 04-hpa.yaml

# 6. (可选) 部署 PDB
kubectl apply -f 05-pdb.yaml

# 7. 验证部署
kubectl get pods -n cloudflare-tunnel
```

---

## 📋 前置要求

### 1. Cloudflare 账户配置

- [ ] 已注册 Cloudflare 账户
- [ ] 已添加域名（例如 `anixops.com`）
- [ ] 已创建 Tunnel 并获取 Token

**获取 Token 步骤**:
1. 访问 https://one.dash.cloudflare.com/
2. 进入 **Access** → **Tunnels**
3. 点击 **Create a tunnel**
4. 复制 Token（以 `eyJ` 开头）

### 2. Kubernetes 集群

- [ ] Kubernetes 版本 ≥ 1.20
- [ ] 已安装并配置 `kubectl`
- [ ] 已部署 Ingress Controller（例如 Nginx Ingress）

**验证 Ingress Controller**:
```bash
kubectl get svc -n ingress-nginx

# 应该看到 ClusterIP Service:
# NAME                       TYPE        CLUSTER-IP      PORT(S)
# ingress-nginx-controller   ClusterIP   10.96.123.45    80/TCP,443/TCP
```

### 3. (可选) Metrics Server

如果要使用 HPA 自动扩缩容：

```bash
# 验证 Metrics Server
kubectl top nodes

# 如果未安装，参考: https://github.com/kubernetes-sigs/metrics-server
```

---

## ⚙️ 配置说明

### ConfigMap 配置 (02-configmap.yaml)

关键配置项：

```yaml
ingress:
  # 捕获所有 *.anixops.com 的流量
  - hostname: "*.anixops.com"
    service: http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
  
  # 默认规则（必需）
  - service: http_status:404
```

**自定义配置**:

1. **修改域名**:
   ```yaml
   - hostname: "*.yourdomain.com"  # 替换为你的域名
   ```

2. **指向 HTTPS Ingress**:
   ```yaml
   - hostname: "*.anixops.com"
     service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
     originRequest:
       noTLSVerify: true  # 如果使用自签名证书
   ```

3. **特定子域名路由**:
   ```yaml
   - hostname: api.anixops.com
     service: http://api-service.default.svc.cluster.local:8080
   
   - hostname: grafana.anixops.com
     service: http://grafana.observability.svc.cluster.local:3000
   ```

**应用配置变更**:
```bash
kubectl apply -f 02-configmap.yaml
kubectl rollout restart deployment cloudflared -n cloudflare-tunnel
```

---

## 🔧 Deployment 配置 (03-deployment.yaml)

### 副本数调整

```bash
# 手动扩缩容
kubectl scale deployment cloudflared --replicas=5 -n cloudflare-tunnel

# 或修改 YAML 文件中的 replicas 值
```

### 资源限制

```yaml
resources:
  requests:
    cpu: 50m       # 最小资源
    memory: 64Mi
  limits:
    cpu: 200m      # 最大资源
    memory: 128Mi
```

### 镜像版本更新

```bash
# 更新到新版本
kubectl set image deployment/cloudflared \
  cloudflared=cloudflare/cloudflared:2024.11.0 \
  -n cloudflare-tunnel

# 查看更新进度
kubectl rollout status deployment/cloudflared -n cloudflare-tunnel

# 如果出现问题，回滚
kubectl rollout undo deployment/cloudflared -n cloudflare-tunnel
```

---

## 📊 HPA 配置 (04-hpa.yaml)

**自动扩缩容策略**:

- **最小副本数**: 3
- **最大副本数**: 10
- **扩容条件**: CPU 使用率 > 70% 或内存使用率 > 80%
- **缩容条件**: 稳定 5 分钟后，CPU/内存低于阈值

**查看 HPA 状态**:
```bash
kubectl get hpa -n cloudflare-tunnel
kubectl describe hpa cloudflared-hpa -n cloudflare-tunnel
```

**自定义扩缩容阈值**:

编辑 `04-hpa.yaml`:
```yaml
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60  # 修改为 60%
```

---

## 🛡️ PDB 配置 (05-pdb.yaml)

**Pod 中断预算**:

- 在节点维护期间，至少保持 2 个 Pod 可用
- 防止同时驱逐太多 Pod

**测试 PDB**:
```bash
# 标记节点为不可调度
kubectl cordon <node-name>

# 驱逐节点上的 Pods（PDB 会生效）
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# 观察 Pod 驱逐过程
kubectl get pods -n cloudflare-tunnel -w

# 恢复节点
kubectl uncordon <node-name>
```

---

## ✅ 验证部署

### 1. 检查 Pods 状态

```bash
kubectl get pods -n cloudflare-tunnel

# 期望输出：
# NAME                          READY   STATUS    RESTARTS   AGE
# cloudflared-xxxxxxxxxx-xxxxx  1/1     Running   0          30s
# cloudflared-xxxxxxxxxx-xxxxx  1/1     Running   0          30s
# cloudflared-xxxxxxxxxx-xxxxx  1/1     Running   0          30s
```

### 2. 查看 Pods 日志

```bash
kubectl logs -n cloudflare-tunnel -l app=cloudflared --tail=50

# 期望看到：
# 2025-10-27T10:00:00Z INF Starting tunnel connection...
# 2025-10-27T10:00:01Z INF Connection established
# 2025-10-27T10:00:01Z INF Registered tunnel connection
```

### 3. 验证 Tunnel 连接

1. 访问 Cloudflare Dashboard: https://one.dash.cloudflare.com/
2. 进入 **Access** → **Tunnels**
3. 找到你的 Tunnel
4. 状态应该显示为 **HEALTHY**
5. 应该看到 3 个连接器（Connectors）在线

### 4. 测试连接到 Ingress Controller

```bash
# 从 cloudflared Pod 测试连接
kubectl exec -it -n cloudflare-tunnel deployment/cloudflared -- \
  wget -O- http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80

# 应该返回 Ingress 的默认后端响应
```

---

## 🌐 配置域名路由

### 在 Cloudflare Dashboard 中配置

1. 在 Tunnel 详情页，点击 **Public Hostname** 标签
2. 点击 **Add a public hostname**
3. 配置：
   ```
   Subdomain: *
   Domain: anixops.com
   Type: HTTP
   URL: http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
   ```
4. 点击 **Save**

### 或使用通配符 DNS 记录

在 Cloudflare DNS 设置中添加：

```
Type: CNAME
Name: *
Target: <tunnel-id>.cfargotunnel.com
Proxied: Yes (橙色云朵)
```

---

## 🎯 创建应用 Ingress

示例 Ingress 资源：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  namespace: default
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: app.anixops.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app-service
                port:
                  number: 80
```

应用：
```bash
kubectl apply -f my-app-ingress.yaml
```

测试：
```bash
curl https://app.anixops.com
```

---

## 🐛 故障排查

### 问题 1: Pods 无法启动 (CrashLoopBackOff)

**诊断**:
```bash
kubectl logs -n cloudflare-tunnel -l app=cloudflared --tail=100
```

**可能原因**:
- Token 无效或过期
- ConfigMap 配置错误
- 无法连接到 Cloudflare

**解决方案**:
```bash
# 重新创建 Secret
kubectl delete secret cloudflared-token -n cloudflare-tunnel
export CF_TUNNEL_TOKEN="your-new-token"
kubectl create secret generic cloudflared-token \
  --from-literal=token=$CF_TUNNEL_TOKEN \
  --namespace=cloudflare-tunnel

# 重启 Deployment
kubectl rollout restart deployment cloudflared -n cloudflare-tunnel
```

---

### 问题 2: 502 Bad Gateway

**诊断**:
```bash
# 测试从 cloudflared 到 Ingress 的连接
kubectl exec -it -n cloudflare-tunnel deployment/cloudflared -- \
  wget -O- http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
```

**可能原因**:
- Ingress Controller Service 名称或 Namespace 错误
- Ingress Controller 未运行
- 网络策略阻止流量

**解决方案**:
```bash
# 验证 Ingress Controller Service
kubectl get svc -n ingress-nginx

# 更新 ConfigMap 中的 Service 地址
kubectl edit configmap cloudflared-config -n cloudflare-tunnel

# 重启 Deployment
kubectl rollout restart deployment cloudflared -n cloudflare-tunnel
```

---

### 问题 3: HPA 不工作

**诊断**:
```bash
kubectl describe hpa cloudflared-hpa -n cloudflare-tunnel
kubectl top pods -n cloudflare-tunnel
```

**可能原因**:
- Metrics Server 未安装
- Pod 资源请求未设置

**解决方案**:
```bash
# 安装 Metrics Server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# 验证
kubectl top nodes
```

---

## 🗑️ 卸载

```bash
# 删除所有资源
kubectl delete namespace cloudflare-tunnel

# 或逐个删除
kubectl delete -f 05-pdb.yaml
kubectl delete -f 04-hpa.yaml
kubectl delete -f 03-deployment.yaml
kubectl delete -f 02-configmap.yaml
kubectl delete secret cloudflared-token -n cloudflare-tunnel
kubectl delete -f 00-namespace.yaml
```

---

## 📚 参考资料

- [完整部署指南](../../docs/CLOUDFLARED_KUBERNETES.md)
- [Cloudflare Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Kubernetes Deployment 最佳实践](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Nginx Ingress Controller](https://kubernetes.github.io/ingress-nginx/)

---

## 🙋 获取帮助

- **GitHub Issues**: https://github.com/AnixOps/AnixOps-ansible/issues
- **Cloudflare Community**: https://community.cloudflare.com/

---

**AnixOps Team**  
Last Updated: 2025-10-27
