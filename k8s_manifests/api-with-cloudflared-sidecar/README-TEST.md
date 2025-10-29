# 测试环境部署指南 - API with Cloudflared Sidecar

## 概述

本测试环境使用 **httpbin** 作为测试 API，结合 **cloudflared sidecar** 模式，快速验证 Cloudflare Tunnel 的功能。

## 架构说明

```
┌─────────────────────────────────────────┐
│           Kubernetes Pod                │
│                                         │
│  ┌─────────────┐    ┌──────────────┐  │
│  │   httpbin   │    │ cloudflared  │  │
│  │   (API)     │◄───┤  (Sidecar)   │  │
│  │  Port: 80   │    │              │  │
│  └─────────────┘    └──────────────┘  │
│        │                    │          │
│        │                    │          │
└────────┼────────────────────┼──────────┘
         │                    │
    localhost:80              │
                              │
                    Cloudflare Tunnel
                              │
                              ▼
                        Internet 🌐
```

## 快速开始

### 前置要求

1. **Kubernetes 集群**：确保有可用的 K8s 集群
2. **kubectl**：已安装并配置好集群访问
3. **Cloudflare Tunnel Token**：在 Cloudflare Zero Trust Dashboard 中创建隧道并获取 Token

### 方法 1: 使用部署脚本（推荐）

```bash
cd /root/code/AnixOps-ansible/k8s_manifests/api-with-cloudflared-sidecar

# 执行部署脚本
./deploy-test.sh --token "your-cloudflare-tunnel-token"

# 指定命名空间
./deploy-test.sh --token "your-token" --namespace test
```

### 方法 2: 手动部署

```bash
# 1. 更新 deployment.yaml 中的 TUNNEL_TOKEN
vim deployment.yaml

# 2. 应用配置
kubectl apply -f deployment.yaml

# 3. 查看状态
kubectl get pods -l app=test-api-service
```

## 验证部署

### 1. 检查 Pod 状态

```bash
kubectl get pods -l app=test-api-service
```

期望输出：
```
NAME                                      READY   STATUS    RESTARTS   AGE
test-api-with-cloudflared-xxxxxxxxx-xxxxx   2/2     Running   0          2m
```

### 2. 查看日志

**Cloudflared Sidecar 日志：**
```bash
kubectl logs -f <pod-name> -c cloudflared-sidecar
```

**API 服务日志：**
```bash
kubectl logs -f <pod-name> -c test-api-service
```

### 3. 测试 API（集群内部）

```bash
# 获取 Pod 名称
POD_NAME=$(kubectl get pods -l app=test-api-service -o jsonpath='{.items[0].metadata.name}')

# 测试健康检查端点
kubectl exec -it $POD_NAME -c test-api-service -- curl http://localhost/status/200

# 测试其他端点
kubectl exec -it $POD_NAME -c test-api-service -- curl http://localhost/get
kubectl exec -it $POD_NAME -c test-api-service -- curl http://localhost/headers
```

### 4. 外部访问测试

1. 登录 Cloudflare Zero Trust Dashboard
2. 找到您的隧道，查看分配的 URL（如：`https://xxx.trycloudflare.com`）
3. 使用浏览器或 curl 访问：

```bash
# 测试基本端点
curl https://your-tunnel-url.trycloudflare.com/get

# 测试 POST
curl -X POST https://your-tunnel-url.trycloudflare.com/post -d '{"test": "data"}'

# 查看头信息
curl https://your-tunnel-url.trycloudflare.com/headers

# 获取 IP
curl https://your-tunnel-url.trycloudflare.com/ip
```

## httpbin API 测试端点

httpbin 提供了丰富的测试端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/get` | GET | 返回 GET 请求信息 |
| `/post` | POST | 返回 POST 请求信息 |
| `/status/{code}` | GET | 返回指定 HTTP 状态码 |
| `/headers` | GET | 返回请求头信息 |
| `/ip` | GET | 返回客户端 IP |
| `/user-agent` | GET | 返回 User-Agent |
| `/delay/{seconds}` | GET | 延迟指定秒数后响应 |
| `/json` | GET | 返回 JSON 数据 |
| `/html` | GET | 返回 HTML 页面 |

更多端点请访问：https://httpbin.org/

## 故障排查

### Pod 无法启动

```bash
# 查看 Pod 详细信息
kubectl describe pod <pod-name>

# 查看事件
kubectl get events --sort-by=.metadata.creationTimestamp
```

### Cloudflared 连接失败

```bash
# 检查 Secret 是否正确
kubectl get secret cloudflared-secret -o yaml

# 查看 cloudflared 日志
kubectl logs <pod-name> -c cloudflared-sidecar
```

常见错误：
- **Token 无效**：检查 Token 是否正确，是否已过期
- **网络问题**：确保集群可以访问 Cloudflare 服务
- **资源不足**：检查节点资源是否充足

### API 无法访问

```bash
# 测试 API 容器是否正常
kubectl exec -it <pod-name> -c test-api-service -- curl http://localhost/status/200

# 检查容器日志
kubectl logs <pod-name> -c test-api-service
```

## 清理资源

```bash
# 删除 Deployment 和 Service
kubectl delete deployment test-api-with-cloudflared
kubectl delete service test-api-service

# 删除 Secret
kubectl delete secret cloudflared-secret

# 或者删除整个命名空间（如果是测试命名空间）
kubectl delete namespace test
```

## 从测试环境迁移到生产环境

当测试成功后，可以按以下步骤迁移到生产环境：

1. **替换 API 镜像**：
   - 将 `kennethreitz/httpbin:latest` 替换为您的实际 API 镜像
   - 修改 `containerPort` 为您的 API 端口（如 8080）

2. **调整资源配置**：
   - 根据实际负载调整 CPU 和内存限制
   - 增加副本数以提高可用性

3. **更新健康检查**：
   - 修改 `livenessProbe` 和 `readinessProbe` 的路径
   - 根据您的 API 调整超时和间隔参数

4. **生产环境配置**：
   - 使用专用命名空间（如 `production`）
   - 配置合适的资源配额和限制
   - 添加监控和告警

5. **使用原始部署脚本**：
   ```bash
   # 恢复备份的完整部署脚本
   ./deploy.sh --token "token" --image "your-api:version" --namespace production
   ```

## 相关文件

- `deployment.yaml` - 测试环境的 Kubernetes 部署配置
- `deploy-test.sh` - 快速部署脚本
- `deploy.sh.bak` - 原始的完整部署脚本（备份）

## 注意事项

⚠️ **安全提醒**：
- 测试 Token 不要暴露到公共仓库
- 生产环境建议使用 Kubernetes Secrets 管理敏感信息
- 定期轮换 Tunnel Token

📝 **最佳实践**：
- 测试环境使用独立的命名空间
- 生产环境配置适当的资源限制和请求
- 启用监控和日志收集
- 配置自动扩缩容（HPA）

## 支持

如有问题，请查看：
- Cloudflare Tunnel 文档：https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- httpbin 文档：https://httpbin.org/
- Kubernetes 文档：https://kubernetes.io/docs/
