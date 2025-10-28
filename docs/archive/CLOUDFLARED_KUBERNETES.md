# 🚀 Cloudflare Tunnel for Kubernetes 部署指南

[![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.25+-blue)](https://kubernetes.io/)
[![Security](https://img.shields.io/badge/Security-Zero_Trust-success)](https://www.cloudflare.com/zero-trust/)

> 将 Cloudflare Tunnel 部署为 Kubernetes Deployment，实现零公网 IP 暴露的安全入口流量管理

---

## 📋 目录

- [架构概览](#架构概览)
- [前置要求](#前置要求)
- [步骤 1: 创建 Cloudflare Tunnel](#步骤-1-创建-cloudflare-tunnel)
- [步骤 2: 创建 Kubernetes Namespace](#步骤-2-创建-kubernetes-namespace)
- [步骤 3: 创建 Secret 存储 Token](#步骤-3-创建-secret-存储-token)
- [步骤 4: 创建 ConfigMap 配置 Tunnel](#步骤-4-创建-configmap-配置-tunnel)
- [步骤 5: 部署 Cloudflared Deployment](#步骤-5-部署-cloudflared-deployment)
- [步骤 6: 验证部署](#步骤-6-验证部署)
- [步骤 7: 配置域名路由](#步骤-7-配置域名路由)
- [高可用配置](#高可用配置)
- [故障排查](#故障排查)
- [完整示例](#完整示例)

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    外部用户 (Internet)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Cloudflare Edge Network (Global CDN)               │
│          *.anixops.com → Cloudflare Tunnel (cloudflared)       │
└─────────────────────────────────────────────────────────────────┘
                              │ (加密连接)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes 集群 (内网)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Namespace: cloudflare-tunnel                           │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  Deployment: cloudflared (3 replicas)          │    │   │
│  │  │  - Pod 1: cloudflared                           │    │   │
│  │  │  - Pod 2: cloudflared                           │    │   │
│  │  │  - Pod 3: cloudflared                           │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Namespace: ingress-nginx                               │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  Service: ingress-nginx-controller (ClusterIP)  │    │   │
│  │  │  Endpoint: ingress-nginx-controller.ingress-    │    │   │
│  │  │            nginx.svc.cluster.local:80/443       │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  你的应用 Pods (通过 Ingress 路由)                       │   │
│  │  - app1.anixops.com → Service: app1                     │   │
│  │  - app2.anixops.com → Service: app2                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

✅ 优势：
  - 无需公网 IP / LoadBalancer / NodePort
  - 自动 DDoS 防护 (Cloudflare)
  - 全球 CDN 加速
  - 零信任安全架构
```

---

## ✅ 前置要求

### 1. Cloudflare 账户
- [ ] 已注册 Cloudflare 账户
- [ ] 已添加域名（例如 `anixops.com`）
- [ ] 已启用 Cloudflare Zero Trust

### 2. Kubernetes 集群
- [ ] Kubernetes 版本 ≥ 1.20
- [ ] 已安装 `kubectl` 并配置访问权限
- [ ] 已部署 Ingress Controller（例如 Nginx Ingress）

### 3. 验证 Ingress Controller
```bash
# 检查 Ingress Controller Service
kubectl get svc -n ingress-nginx

# 应该看到类似输出：
# NAME                       TYPE        CLUSTER-IP      PORT(S)
# ingress-nginx-controller   ClusterIP   10.96.123.45    80/TCP,443/TCP
```

---

## 📝 步骤 1: 创建 Cloudflare Tunnel

### 方法 1: 使用自动化工具（推荐）⭐

使用 AnixOps 提供的 `tunnel_manager.py` 工具，自动创建 Tunnel 并获取 Token：

```bash
# 设置认证信息
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_API_TOKEN="your-api-token"

# 创建 Tunnel 并自动部署到 Kubernetes
./tools/tunnel_manager.py create k8s-ingress-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --deploy-type kubernetes \
  --auto-deploy
```

**优势**:
- ✅ 自动创建 Tunnel
- ✅ 自动获取 Token
- ✅ 自动创建 Kubernetes Secret
- ✅ 自动部署所有资源
- ✅ 零手动操作

完整文档: [tools/README_TUNNEL_MANAGER.md](../../tools/README_TUNNEL_MANAGER.md)

---

### 方法 2: 手动创建（传统方式）

#### 1.1 登录 Cloudflare Zero Trust Dashboard

访问: https://one.dash.cloudflare.com/

#### 1.2 创建 Tunnel

1. 导航到 **Access** → **Tunnels**
2. 点击 **Create a tunnel**
3. 选择 **Cloudflared**
4. 输入 Tunnel 名称: `k8s-ingress-tunnel`
5. 点击 **Save tunnel**

#### 1.3 获取 Tunnel Token

创建后，你会看到类似这样的安装命令：

```bash
cloudflared service install eyJhIjoiY2FmZS0xMjM0NTY3ODkwYWJjZGVmIiwidCI6IjEyMzQ1Njc4LTkwYWItY2RlZi0xMjM0LTU2Nzg5MGFiY2RlZiIsInMiOiJhYmNkZWYxMjM0NTY3ODkwIn0=
```

**复制 `eyJ...` 开头的 Token**，这就是你的 `tunnel-token`。

⚠️ **重要**: 妥善保管此 Token，它是连接到你的 Cloudflare 账户的凭证。

### 1.4 暂时跳过域名配置

现在先不要配置路由，我们将在后续步骤中完成。

---

### 方法 3: 使用 Cloudflare API（高级）

如果你熟悉 API，可以直接调用：

```bash
# 创建 Tunnel
curl https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "k8s-ingress-tunnel", "config_src": "cloudflare"}' \
  | jq '.result.id'

# 获取 Token
curl https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/token \
  -H "Authorization: Bearer $API_TOKEN" \
  | jq -r '.result'
```

---

## 📦 步骤 2: 创建 Kubernetes Namespace

创建专用的 Namespace 来组织 Cloudflare Tunnel 资源：

```bash
kubectl create namespace cloudflare-tunnel
```

或使用 YAML:

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: cloudflare-tunnel
  labels:
    name: cloudflare-tunnel
    purpose: ingress-tunnel
```

```bash
kubectl apply -f namespace.yaml
```

---

## 🔐 步骤 3: 创建 Secret 存储 Token

### 方法 1: 使用 kubectl (推荐)

```bash
# 替换为你的实际 Token
export CF_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0NTY3ODkwYWJjZGVmIiwidCI6IjEyMzQ1Njc4LTkwYWItY2RlZi0xMjM0LTU2Nzg5MGFiY2RlZiIsInMiOiJhYmNkZWYxMjM0NTY3ODkwIn0="

kubectl create secret generic cloudflared-token \
  --from-literal=token=$CF_TUNNEL_TOKEN \
  --namespace=cloudflare-tunnel
```

### 方法 2: 使用 YAML (不推荐，Token 会以 base64 可见)

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: cloudflared-token
  namespace: cloudflare-tunnel
type: Opaque
stringData:
  token: "eyJhIjoiY2FmZS0xMjM0NTY3ODkwYWJjZGVmIiwidCI6IjEyMzQ1Njc4LTkwYWItY2RlZi0xMjM0LTU2Nzg5MGFiY2RlZiIsInMiOiJhYmNkZWYxMjM0NTY3ODkwIn0="
```

⚠️ **安全提示**: 如果使用 YAML 文件，请确保：
- 将 `secret.yaml` 添加到 `.gitignore`
- 或使用 Sealed Secrets / External Secrets Operator 等工具
- 绝不将包含真实 Token 的 YAML 提交到 Git

### 验证 Secret

```bash
kubectl get secret cloudflared-token -n cloudflare-tunnel
```

---

## ⚙️ 步骤 4: 创建 ConfigMap 配置 Tunnel

创建 `cloudflared` 的配置文件，指向你的 Ingress Controller：

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cloudflared-config
  namespace: cloudflare-tunnel
data:
  config.yaml: |
    # =============================================================================
    # Cloudflare Tunnel 配置文件 | Cloudflare Tunnel Configuration
    # =============================================================================
    
    # Tunnel 不会自动更新（在 K8s 中由镜像版本管理）
    no-autoupdate: true
    
    # 日志级别 | Log level: debug, info, warn, error
    loglevel: info
    
    # 传输协议 | Transport protocol
    protocol: quic
    
    # Ingress 规则 | Ingress rules
    # 所有流量转发到内部 Ingress Controller
    ingress:
      # 捕获所有域名的 HTTP 流量
      - hostname: "*.anixops.com"
        service: http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
      
      # 可选：如果需要 HTTPS 到 Ingress Controller
      # - hostname: "*.anixops.com"
      #   service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
      #   originServerName: "*.anixops.com"
      
      # 捕获特定子域名（如果需要更细粒度控制）
      # - hostname: app1.anixops.com
      #   service: http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
      
      # - hostname: app2.anixops.com
      #   service: http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
      
      # 默认规则（必需）：捕获所有未匹配的流量
      - service: http_status:404
```

**配置说明**:

| 字段                | 说明                                                      |
|---------------------|-----------------------------------------------------------|
| `hostname`          | 要路由的域名（支持通配符 `*.anixops.com`）                |
| `service`           | 目标服务（这里指向内部 Ingress Controller）                |
| `http://...`        | 使用 HTTP 协议连接到 Ingress                               |
| `https://...`       | 使用 HTTPS 协议连接到 Ingress（如果 Ingress 启用 TLS）    |
| `http_status:404`   | 默认规则，返回 404 给未匹配的请求                          |

应用 ConfigMap:

```bash
kubectl apply -f configmap.yaml
```

---

## 🚀 步骤 5: 部署 Cloudflared Deployment

创建高可用的 Cloudflared Deployment（3 个副本）：

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudflared
  namespace: cloudflare-tunnel
  labels:
    app: cloudflared
    component: ingress-tunnel
spec:
  # 高可用：3 个副本
  replicas: 3
  
  # 滚动更新策略
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  
  selector:
    matchLabels:
      app: cloudflared
  
  template:
    metadata:
      labels:
        app: cloudflared
      annotations:
        # 自动重启 Pod 当 ConfigMap 变更时
        checksum/config: "{{ include (print $.Template.BasePath '/configmap.yaml') . | sha256sum }}"
    spec:
      # 容器配置
      containers:
        - name: cloudflared
          # 使用官方镜像（建议固定版本）
          image: cloudflare/cloudflared:2024.10.0
          
          # 启动参数
          args:
            - tunnel
            - --config
            - /etc/cloudflared/config.yaml
            - run
          
          # 环境变量：从 Secret 读取 Token
          env:
            - name: TUNNEL_TOKEN
              valueFrom:
                secretKeyRef:
                  name: cloudflared-token
                  key: token
          
          # 挂载配置文件
          volumeMounts:
            - name: config
              mountPath: /etc/cloudflared
              readOnly: true
          
          # 资源限制
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          
          # 存活探测
          livenessProbe:
            httpGet:
              path: /ready
              port: 2000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          
          # 就绪探测
          readinessProbe:
            httpGet:
              path: /ready
              port: 2000
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 2
      
      # 挂载 ConfigMap
      volumes:
        - name: config
          configMap:
            name: cloudflared-config
            items:
              - key: config.yaml
                path: config.yaml
      
      # Pod 调度策略：尽量分散到不同节点
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - cloudflared
                topologyKey: kubernetes.io/hostname
      
      # 容忍节点污点（可选）
      # tolerations:
      #   - key: "node-role.kubernetes.io/master"
      #     operator: "Exists"
      #     effect: "NoSchedule"
```

应用 Deployment:

```bash
kubectl apply -f deployment.yaml
```

---

## ✅ 步骤 6: 验证部署

### 6.1 检查 Pod 状态

```bash
kubectl get pods -n cloudflare-tunnel

# 期望输出：
# NAME                          READY   STATUS    RESTARTS   AGE
# cloudflared-xxxxxxxxxx-xxxxx  1/1     Running   0          30s
# cloudflared-xxxxxxxxxx-xxxxx  1/1     Running   0          30s
# cloudflared-xxxxxxxxxx-xxxxx  1/1     Running   0          30s
```

### 6.2 查看 Pod 日志

```bash
# 查看第一个 Pod 的日志
kubectl logs -n cloudflare-tunnel -l app=cloudflared --tail=50

# 期望看到：
# 2025-10-27T10:00:00Z INF Starting tunnel connection...
# 2025-10-27T10:00:01Z INF Connection established
# 2025-10-27T10:00:01Z INF Registered tunnel connection
```

### 6.3 查看详细信息

```bash
kubectl describe deployment cloudflared -n cloudflare-tunnel
```

### 6.4 验证 Tunnel 连接（在 Cloudflare Dashboard）

1. 访问 https://one.dash.cloudflare.com/
2. 进入 **Access** → **Tunnels**
3. 找到你的 Tunnel (`k8s-ingress-tunnel`)
4. 状态应该显示为 **HEALTHY** 或 **Active**
5. 应该看到 3 个连接器（Connectors）在线

---

## 🌐 步骤 7: 配置域名路由

### 7.1 在 Cloudflare Dashboard 配置路由

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

### 7.2 或使用通配符 DNS 记录（推荐）

在 Cloudflare DNS 设置中添加：

```
Type: CNAME
Name: *
Target: <tunnel-id>.cfargotunnel.com
Proxied: Yes (橙色云朵)
```

> Tunnel ID 可以在 Tunnel 详情页找到

---

## 🏆 高可用配置

### 扩展副本数

```bash
# 扩展到 5 个副本
kubectl scale deployment cloudflared --replicas=5 -n cloudflare-tunnel
```

### 启用 Horizontal Pod Autoscaler (HPA)

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cloudflared-hpa
  namespace: cloudflare-tunnel
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cloudflared
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

```bash
kubectl apply -f hpa.yaml
```

### 配置 Pod Disruption Budget (PDB)

```yaml
# pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: cloudflared-pdb
  namespace: cloudflare-tunnel
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: cloudflared
```

```bash
kubectl apply -f pdb.yaml
```

---

## 🐛 故障排查

### 问题 1: Pod 无法启动

**症状**:
```bash
kubectl get pods -n cloudflare-tunnel
# STATUS: CrashLoopBackOff
```

**诊断**:
```bash
kubectl logs -n cloudflare-tunnel -l app=cloudflared --tail=100
```

**可能原因**:
1. Token 无效或过期
2. ConfigMap 配置错误
3. 无法连接到 Cloudflare

**解决方案**:
```bash
# 验证 Secret
kubectl get secret cloudflared-token -n cloudflare-tunnel -o yaml

# 验证 ConfigMap
kubectl get configmap cloudflared-config -n cloudflare-tunnel -o yaml

# 重新创建 Secret
kubectl delete secret cloudflared-token -n cloudflare-tunnel
kubectl create secret generic cloudflared-token \
  --from-literal=token=$CF_TUNNEL_TOKEN \
  --namespace=cloudflare-tunnel
```

---

### 问题 2: 无法连接到 Ingress Controller

**症状**:
Cloudflare Tunnel 显示在线，但访问域名返回 502 Bad Gateway

**诊断**:
```bash
# 测试从 cloudflared Pod 到 Ingress Controller 的连接
kubectl exec -it -n cloudflare-tunnel deployment/cloudflared -- \
  wget -O- http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
```

**可能原因**:
1. Ingress Controller Service 名称或 Namespace 错误
2. Ingress Controller 未运行
3. 网络策略阻止流量

**解决方案**:
```bash
# 验证 Ingress Controller Service
kubectl get svc -n ingress-nginx

# 验证 DNS 解析
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup ingress-nginx-controller.ingress-nginx.svc.cluster.local
```

---

### 问题 3: 健康检查失败

**症状**:
```bash
kubectl get pods -n cloudflare-tunnel
# READY: 0/1
```

**解决方案**:

如果你的 cloudflared 版本不支持健康检查端点，移除探测配置：

```bash
kubectl edit deployment cloudflared -n cloudflare-tunnel

# 删除或注释掉 livenessProbe 和 readinessProbe 部分
```

---

## 📦 完整示例：一键部署

创建一个包含所有资源的单一 YAML 文件：

```yaml
# cloudflared-complete.yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: cloudflare-tunnel
  labels:
    name: cloudflare-tunnel

---
# ⚠️ 注意：实际使用时，请用 kubectl create secret 命令创建，不要将 Token 提交到 Git
apiVersion: v1
kind: Secret
metadata:
  name: cloudflared-token
  namespace: cloudflare-tunnel
type: Opaque
stringData:
  token: "YOUR_TUNNEL_TOKEN_HERE"  # 替换为你的实际 Token

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: cloudflared-config
  namespace: cloudflare-tunnel
data:
  config.yaml: |
    no-autoupdate: true
    loglevel: info
    protocol: quic
    ingress:
      - hostname: "*.anixops.com"
        service: http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
      - service: http_status:404

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudflared
  namespace: cloudflare-tunnel
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  selector:
    matchLabels:
      app: cloudflared
  template:
    metadata:
      labels:
        app: cloudflared
    spec:
      containers:
        - name: cloudflared
          image: cloudflare/cloudflared:2024.10.0
          args:
            - tunnel
            - --config
            - /etc/cloudflared/config.yaml
            - run
          env:
            - name: TUNNEL_TOKEN
              valueFrom:
                secretKeyRef:
                  name: cloudflared-token
                  key: token
          volumeMounts:
            - name: config
              mountPath: /etc/cloudflared
              readOnly: true
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
      volumes:
        - name: config
          configMap:
            name: cloudflared-config
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - cloudflared
                topologyKey: kubernetes.io/hostname
```

**部署**:
```bash
# 1. 先创建 Secret（推荐方式）
export CF_TUNNEL_TOKEN="your-actual-token"
kubectl create secret generic cloudflared-token \
  --from-literal=token=$CF_TUNNEL_TOKEN \
  --namespace=cloudflare-tunnel --dry-run=client -o yaml | \
  kubectl apply -f -

# 2. 部署其他资源（注释掉 YAML 中的 Secret 部分）
kubectl apply -f cloudflared-complete.yaml
```

---

## 🎯 下一步

1. **配置你的应用 Ingress**:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: my-app
     namespace: default
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

2. **启用 TLS**:
   - 在 Cloudflare Dashboard 中启用 SSL/TLS (Full 或 Full Strict 模式)
   - 在 Ingress 中配置 cert-manager 自动获取证书

3. **监控 Tunnel 健康状态**:
   - 集成 Prometheus 和 Grafana
   - 配置 Cloudflare 的日志推送

4. **实施访问策略**:
   - 在 Cloudflare Zero Trust 中配置访问策略
   - 启用身份验证（如 OAuth、SAML）

---

## 📚 参考资料

- [Cloudflare Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Kubernetes Deployment 最佳实践](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Nginx Ingress Controller 文档](https://kubernetes.github.io/ingress-nginx/)

---

## 🙋 获取帮助

- **GitHub Issues**: https://github.com/AnixOps/AnixOps-ansible/issues
- **Cloudflare Community**: https://community.cloudflare.com/

---

**AnixOps Team**  
Last Updated: 2025-10-27
