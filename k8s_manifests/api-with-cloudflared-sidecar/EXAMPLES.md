# API Service with Cloudflared Sidecar - 使用示例

## 示例 1: 基础部署

最简单的部署方式，使用默认配置：

```bash
./deploy.sh \
  --token "eyJhIjoiY2FmZS0xMjM0NTY3ODkwYWJjZGVmIiwiYiI6ImRlZmYtNTY3ODkwMTIzNDU2Nzg5MGFiY2RlZiIsImMiOiJodHRwczovL2FwaS5jbG91ZGZsYXJlLmNvbS9jbGllbnQvdjQvem9uZS90dW5uZWwiLCJkIjoiYWJjZGVmMTIzNDU2Nzg5MGFiY2RlZjEyMzQ1Njc4OTAifQ==" \
  --image "myregistry.com/my-api:v1.0.0"
```

这将在 `default` namespace 部署 2 个副本。

---

## 示例 2: 生产环境部署

部署到生产环境，使用 3 个副本：

```bash
./deploy.sh \
  --token "${CLOUDFLARE_TUNNEL_TOKEN}" \
  --image "registry.example.com/api/production:v2.1.5" \
  --namespace production \
  --replicas 3
```

**提示**: 建议使用环境变量存储敏感的 Token。

---

## 示例 3: 自定义健康检查路径

如果你的 API 使用不同的健康检查端点：

```bash
./deploy.sh \
  -t "eyJhIjoiY2FmZS0xMjM0..." \
  -i "myapi:latest" \
  --health-path "/api/health" \
  --ready-path "/api/ready"
```

---

## 示例 4: 开发环境部署

部署到开发环境，只使用 1 个副本：

```bash
./deploy.sh \
  --token "${DEV_TUNNEL_TOKEN}" \
  --image "localhost:5000/api:dev" \
  --namespace dev \
  --replicas 1
```

---

## 示例 5: 模拟运行（Dry Run）

在实际部署前预览生成的配置：

```bash
./deploy.sh \
  --token "test-token-123" \
  --image "test/api:latest" \
  --dry-run
```

这将显示生成的完整 YAML 配置，但不会实际部署。

---

## 示例 6: 使用环境变量

设置环境变量后部署：

```bash
# 导出环境变量
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
export API_IMAGE="registry.example.com/api:v1.2.3"

# 使用环境变量部署
./deploy.sh \
  --token "${CLOUDFLARE_TUNNEL_TOKEN}" \
  --image "${API_IMAGE}" \
  --namespace production
```

---

## 示例 7: 测试环境完整部署

```bash
./deploy.sh \
  --token "eyJhIjoiY2FmZS0xMjM0NTY3ODkwYWJjZGVmIiwiYiI6ImRlZmYtNTY3ODkwMTIz..." \
  --image "docker.io/mycompany/api-service:staging-latest" \
  --namespace staging \
  --replicas 2 \
  --health-path "/healthz" \
  --ready-path "/readyz"
```

---

## 示例 8: 使用私有镜像仓库

如果使用私有镜像仓库，需要先创建 imagePullSecret：

```bash
# 创建镜像拉取 Secret
kubectl create secret docker-registry regcred \
  --docker-server=registry.example.com \
  --docker-username=myuser \
  --docker-password=mypassword \
  --docker-email=myemail@example.com \
  --namespace production

# 然后部署（注意：需要手动编辑生成的配置添加 imagePullSecrets）
./deploy.sh \
  --token "${TUNNEL_TOKEN}" \
  --image "registry.example.com/private/api:v1.0.0" \
  --namespace production
```

---

## 完整工作流示例

### 场景: 从开发到生产的完整部署流程

#### 步骤 1: 开发环境测试

```bash
# 开发环境 - 快速迭代
./deploy.sh \
  -t "${DEV_TUNNEL_TOKEN}" \
  -i "localhost:5000/api:dev-feature-x" \
  -n dev \
  -r 1

# 查看日志
kubectl logs -n dev -l app=api-service -c my-api-service --follow

# 测试功能
kubectl port-forward -n dev deployment/api-service-with-tunnel 8080:8080
curl http://localhost:8080/api/test
```

#### 步骤 2: 测试环境验证

```bash
# 部署到测试环境
./deploy.sh \
  -t "${STAGING_TUNNEL_TOKEN}" \
  -i "registry.example.com/api:v1.2.3-rc1" \
  -n staging \
  -r 2

# 运行集成测试
kubectl exec -n staging deployment/api-service-with-tunnel -c my-api-service -- /tests/integration-test.sh

# 检查健康状态
kubectl get pods -n staging -l app=api-service
```

#### 步骤 3: 生产环境部署

```bash
# 先模拟运行检查配置
./deploy.sh \
  -t "${PROD_TUNNEL_TOKEN}" \
  -i "registry.example.com/api:v1.2.3" \
  -n production \
  -r 3 \
  --dry-run

# 确认无误后正式部署
./deploy.sh \
  -t "${PROD_TUNNEL_TOKEN}" \
  -i "registry.example.com/api:v1.2.3" \
  -n production \
  -r 3

# 监控部署进度
watch kubectl get pods -n production -l app=api-service

# 验证服务状态
kubectl describe deployment -n production api-service-with-tunnel
```

#### 步骤 4: 部署后验证

```bash
# 检查所有 Pod 状态
kubectl get pods -n production -l app=api-service

# 查看 cloudflared 连接状态
kubectl logs -n production -l app=api-service -c cloudflared-sidecar | grep "Registered tunnel connection"

# 查看 API 服务日志
kubectl logs -n production -l app=api-service -c my-api-service --tail=100

# 检查 metrics
kubectl port-forward -n production deployment/api-service-with-tunnel 2000:2000
curl http://localhost:2000/metrics
```

---

## 常见场景脚本

### 回滚到上一个版本

```bash
kubectl rollout undo deployment/api-service-with-tunnel -n production
kubectl rollout status deployment/api-service-with-tunnel -n production
```

### 扩展副本数

```bash
kubectl scale deployment/api-service-with-tunnel -n production --replicas=5
```

### 更新 API 镜像

```bash
kubectl set image deployment/api-service-with-tunnel \
  my-api-service=registry.example.com/api:v1.2.4 \
  -n production
```

### 查看部署历史

```bash
kubectl rollout history deployment/api-service-with-tunnel -n production
```

### 完全清理

```bash
kubectl delete deployment api-service-with-tunnel -n production
kubectl delete service api-service -n production
kubectl delete secret cloudflared-secret -n production
```

---

## 故障排查示例

### 检查 Pod 为什么没有 Ready

```bash
# 查看 Pod 详细信息
kubectl describe pod -n production -l app=api-service

# 查看容器日志
kubectl logs -n production -l app=api-service -c my-api-service --tail=200
kubectl logs -n production -l app=api-service -c cloudflared-sidecar --tail=200

# 进入容器调试
kubectl exec -it -n production deployment/api-service-with-tunnel -c my-api-service -- sh
```

### 测试健康检查端点

```bash
# 端口转发后测试
kubectl port-forward -n production deployment/api-service-with-tunnel 8080:8080

# 在另一个终端测试
curl -v http://localhost:8080/health
curl -v http://localhost:8080/ready
```

### 检查 Secret 是否正确

```bash
# 查看 Secret (base64 解码)
kubectl get secret cloudflared-secret -n production -o jsonpath='{.data.TUNNEL_TOKEN}' | base64 -d
```

---

## 高级配置示例

### 使用 ConfigMap 配置环境变量

```bash
# 创建 ConfigMap
kubectl create configmap api-config \
  --from-literal=LOG_LEVEL=debug \
  --from-literal=MAX_CONNECTIONS=1000 \
  --namespace production

# 然后在 deployment 中引用（需要手动编辑 YAML）
```

### 添加资源配额

```bash
# 创建 ResourceQuota
kubectl create -f - <<EOF
apiVersion: v1
kind: ResourceQuota
metadata:
  name: api-service-quota
  namespace: production
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"
EOF
```

---

## 监控和告警示例

### 使用 kubectl top 查看资源使用

```bash
# 查看 Pod 资源使用
kubectl top pods -n production -l app=api-service

# 查看节点资源使用
kubectl top nodes
```

### 设置资源告警

```bash
# 查看资源使用超过限制的 Pod
kubectl get pods -n production -l app=api-service -o json | \
  jq '.items[] | select(.status.containerStatuses[].restartCount > 3) | .metadata.name'
```

---

## 性能测试示例

### 使用 kubectl run 运行压力测试

```bash
# 在集群内运行压力测试
kubectl run -n production load-test \
  --image=williamyeh/wrk \
  --restart=Never \
  --rm -it -- \
  wrk -t4 -c100 -d30s http://api-service/api/test
```

---

## 总结

这些示例涵盖了：
- ✅ 不同环境的部署配置
- ✅ 常见运维操作
- ✅ 故障排查方法
- ✅ 完整的 CI/CD 工作流
- ✅ 性能测试和监控

根据你的实际需求选择合适的示例进行修改使用。
