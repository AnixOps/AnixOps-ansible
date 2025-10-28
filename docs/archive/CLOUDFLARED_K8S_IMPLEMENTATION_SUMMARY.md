# Cloudflare Tunnel Kubernetes 部署方案 - 实施总结

## 📋 已完成的工作

本次实施为 AnixOps-ansible 项目提供了一个基于 **Ansible + Helm** 的生产级 Cloudflare Tunnel 部署方案。

---

## 🎯 核心成果

### 1. 主 Playbook
**文件**: `playbooks/cloudflared_k8s_helm.yml`

- ✅ 使用 `kubernetes.core.helm` 模块部署官方 Helm Chart
- ✅ 自动管理 Helm 仓库 (https://cloudflare.github.io/helm-charts)
- ✅ 命名空间自动创建和管理
- ✅ 安全的凭据管理（支持 3 种方式）
- ✅ 高可用性配置（默认 2 副本）
- ✅ 完整的验证和错误检查

### 2. Ansible Role
**目录**: `roles/cloudflared_k8s/`

完整的模块化 Role，包含：
- `tasks/validate.yml` - 前置验证（kubectl, helm, token）
- `tasks/namespace.yml` - 命名空间管理
- `tasks/helm_repo.yml` - Helm 仓库管理
- `tasks/helm_deploy.yml` - Helm 部署
- `tasks/verify.yml` - 部署验证
- `defaults/main.yml` - 默认变量配置
- `meta/main.yml` - Role 元信息
- `README.md` - Role 文档

### 3. 清理脚本
**文件**: `scripts/cleanup_cloudflared.sh`

交互式清理脚本，用于：
- ✅ 删除现有 Kubernetes 资源
- ✅ 卸载 Helm releases
- ✅ 清理命名空间
- ✅ 可选：停止 kind 集群
- ✅ 友好的用户交互和确认

### 4. 完整文档

#### 主文档
- `docs/CLOUDFLARED_K8S_HELM.md` - 完整部署指南（包含架构、安装、配置、故障排查）
- `docs/CLOUDFLARED_K8S_QUICK_REF.md` - 快速参考卡片
- `docs/CLOUDFLARED_MIGRATION_GUIDE.md` - 迁移指南（从旧方案到新方案）

#### Role 文档
- `roles/cloudflared_k8s/README.md` - Role 使用文档

### 5. 示例 Playbooks
**目录**: `examples/`

- `cloudflared_simple.yml` - 简单部署示例
- `cloudflared_advanced.yml` - 高级配置示例
- `cloudflared_multi_env.yml` - 多环境部署示例

### 6. Makefile 集成
**文件**: `Makefile`

新增命令：
- `make cf-k8s-deploy` - 部署 Cloudflare Tunnel
- `make cf-k8s-cleanup` - 清理部署
- `make cf-k8s-verify` - 验证部署

### 7. Secrets 管理
**文件**: `vars/cloudflare_secrets.yml.example`

提供 Ansible Vault 使用示例

---

## 🔐 安全特性

### Token 管理方式

本方案支持 3 种安全的 Token 传递方式：

#### 1. 命令行（开发环境）
```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=eyJhIjoiY2FmZS0xMjM0..."
```

#### 2. 环境变量（开发环境）
```bash
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

#### 3. Ansible Vault（生产环境推荐）
```bash
# 创建加密文件
ansible-vault create vars/cloudflare_secrets.yml --vault-password-file ~/.vault_pass

# 使用
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  -e @vars/cloudflare_secrets.yml \
  --vault-password-file ~/.vault_pass
```

**关键点**：Token 永远不会硬编码在代码中！

---

## 🏗️ 架构特点

### 高可用性配置

- **默认 2 副本**：确保至少一个 Pod 始终运行
- **Pod 反亲和性**：副本分散到不同节点
- **健康检查**：Liveness 和 Readiness Probes
- **资源限制**：合理的 CPU 和内存配置

### 配置示例

```yaml
replica_count: 2

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - cloudflared
          topologyKey: kubernetes.io/hostname
```

### 监控集成

- Prometheus metrics 自动启用
- 端口：2000
- 路径：/metrics
- Pod annotations 已配置

---

## 📊 与旧方案对比

| 特性 | 旧方案 (YAML manifests) | 新方案 (Helm) |
|------|------------------------|---------------|
| **部署方式** | kubectl apply | Helm Chart |
| **文件数量** | 6+ YAML 文件 | 1 Playbook |
| **版本管理** | 手动 | Helm 自动 |
| **回滚能力** | ❌ 无 | ✅ helm rollback |
| **Token 管理** | base64 硬编码 | 加密变量 |
| **可维护性** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **升级流程** | 手动编辑 + kubectl | 变量 + 重新运行 |
| **生产就绪** | ⚠️ 需改进 | ✅ 完全就绪 |

---

## 🚀 快速开始

### 最简单的部署

```bash
# 1. 设置 Token
export CLOUDFLARE_TUNNEL_TOKEN="your-token-here"

# 2. 部署
ansible-playbook playbooks/cloudflared_k8s_helm.yml

# 3. 验证
kubectl get pods -n cloudflare-tunnel
```

### 使用 Makefile

```bash
# 1. 设置 Token
export CLOUDFLARE_TUNNEL_TOKEN="your-token-here"

# 2. 部署
make cf-k8s-deploy

# 3. 验证
make cf-k8s-verify

# 4. 清理（如需要）
make cf-k8s-cleanup
```

---

## 📝 使用场景

### 场景 1: 开发环境快速测试

```bash
export CLOUDFLARE_TUNNEL_TOKEN="dev-token"
ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

### 场景 2: 生产环境部署

```bash
# 使用 Ansible Vault
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  -e @vars/cloudflare_secrets.yml \
  --vault-password-file ~/.vault_pass
```

### 场景 3: CI/CD 自动化

```yaml
# .github/workflows/deploy.yml
env:
  CLOUDFLARE_TUNNEL_TOKEN: ${{ secrets.CLOUDFLARE_TUNNEL_TOKEN }}

steps:
  - name: Deploy
    run: ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

### 场景 4: 多环境部署

```bash
# 使用不同的 kubeconfig 上下文
kubectl config use-context dev-cluster
ansible-playbook playbooks/cloudflared_k8s_helm.yml

kubectl config use-context prod-cluster
ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

---

## 🔧 可定制配置

### 修改副本数

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX replica_count=3"
```

### 自定义资源

```yaml
# vars/custom_resources.yml
resources:
  requests:
    cpu: "200m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "1Gi"
```

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX" \
  -e @vars/custom_resources.yml
```

### 使用特定 Chart 版本

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX helm_chart_version=0.3.0"
```

---

## ✅ 验证清单

部署后验证项目：

- [ ] Pod 状态为 Running
- [ ] 副本数量正确
- [ ] Pod 日志无错误
- [ ] Cloudflare Dashboard 显示隧道 Healthy
- [ ] 连接器数量等于副本数
- [ ] Helm release 状态正常
- [ ] Prometheus metrics 可访问

```bash
# 自动验证
make cf-k8s-verify

# 或手动验证
kubectl get pods -n cloudflare-tunnel
kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared
helm list -n cloudflare-tunnel
```

---

## 🆘 故障排查

### 常见问题

#### 1. Token 错误
```bash
Error: cloudflare_tunnel_token is not set!

解决: 确保设置了环境变量或传递了参数
```

#### 2. kubectl 连接失败
```bash
Error: Cannot connect to Kubernetes cluster

解决: 检查 kubeconfig 配置
kubectl cluster-info
```

#### 3. Helm 未安装
```bash
Error: Helm is not installed

解决: 安装 Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

---

## 📚 相关文档

### 内部文档
- [完整部署指南](docs/CLOUDFLARED_K8S_HELM.md)
- [快速参考](docs/CLOUDFLARED_K8S_QUICK_REF.md)
- [迁移指南](docs/CLOUDFLARED_MIGRATION_GUIDE.md)
- [Role 文档](roles/cloudflared_k8s/README.md)

### 外部资源
- [Cloudflare Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Cloudflare Helm Charts](https://github.com/cloudflare/helm-charts)
- [Ansible Kubernetes Collection](https://docs.ansible.com/ansible/latest/collections/kubernetes/core/index.html)

---

## 🎓 关键学习点

### 1. Ansible + Helm 集成

本方案展示了如何在 Ansible 中使用 Helm：
- `kubernetes.core.helm_repository` - 管理 Helm 仓库
- `kubernetes.core.helm` - 部署 Helm Chart
- `kubernetes.core.k8s` - 管理 Kubernetes 资源
- `kubernetes.core.k8s_info` - 查询资源状态

### 2. 安全最佳实践

- ✅ 永不硬编码敏感信息
- ✅ 使用 Ansible Vault 加密
- ✅ 支持多种 Token 传递方式
- ✅ CI/CD 使用 secrets manager

### 3. 高可用性设计

- ✅ 多副本部署
- ✅ Pod 反亲和性
- ✅ 健康检查
- ✅ 资源限制
- ✅ 自动扩缩容支持（HPA）

### 4. 可维护性

- ✅ 模块化 Role 设计
- ✅ 清晰的任务分离
- ✅ 完整的文档
- ✅ 丰富的示例
- ✅ 统一的 Makefile 接口

---

## 🚀 下一步建议

### 可选增强

1. **自动扩缩容 (HPA)**
   - 配置 HorizontalPodAutoscaler
   - 基于 CPU/内存/自定义指标

2. **监控和告警**
   - 集成 Prometheus
   - 配置 Grafana Dashboard
   - 设置告警规则

3. **日志聚合**
   - 集成 Loki/ELK
   - 集中日志管理

4. **GitOps 集成**
   - 集成 ArgoCD/Flux
   - 自动化 CD 流程

5. **多集群部署**
   - 支持多个 Kubernetes 集群
   - 统一配置管理

---

## 📞 支持

如有问题或建议：

1. 查看文档目录 `docs/`
2. 查看示例 `examples/`
3. 提交 Issue: https://github.com/AnixOps/AnixOps-ansible/issues
4. 查看 Role README: `roles/cloudflared_k8s/README.md`

---

## 🎉 总结

本次实施提供了一个**完整、安全、可维护**的 Cloudflare Tunnel Kubernetes 部署方案。

**核心优势**：
- ✅ 使用官方 Helm Chart（可维护性高）
- ✅ 安全的凭据管理（Ansible Vault）
- ✅ 高可用性配置（多副本 + 反亲和性）
- ✅ 完整的文档和示例
- ✅ 生产就绪

**与旧方案相比**：
- 🚀 部署更简单（1 个 Playbook vs 6+ YAML 文件）
- 🔐 更安全（加密 vs 硬编码）
- 🔄 更易维护（Helm 管理 vs 手动管理）
- ✨ 更可靠（自动健康检查 + 回滚能力）

祝使用愉快！🎊
