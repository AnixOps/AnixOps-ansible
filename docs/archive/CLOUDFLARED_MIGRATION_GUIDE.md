# Cloudflare Tunnel 迁移指南

## 📋 迁移概述

本文档说明如何从旧的 YAML manifests 方式迁移到新的 Helm Chart 方式部署 Cloudflare Tunnel。

---

## 🔄 变更对比

### 旧方案 (k8s_manifests/cloudflared/)

```
❌ 问题:
- 手动管理多个 YAML 文件（6+ 个）
- 版本管理困难
- 更新流程复杂
- 无回滚能力
- Token 硬编码风险高
```

### 新方案 (Helm Chart)

```
✅ 优势:
- 使用官方 Helm Chart
- 单一配置文件
- 自动版本管理
- 一键更新和回滚
- 安全的凭据管理
- 符合生产最佳实践
```

---

## 🚀 迁移步骤

### 步骤 1: 清理旧部署

```bash
# 使用自动化脚本（推荐）
./scripts/cleanup_cloudflared.sh

# 或手动清理
kubectl delete namespace cloudflare-tunnel
```

### 步骤 2: 安装依赖

```bash
# 安装 Ansible Collection
ansible-galaxy collection install kubernetes.core

# 安装 Python 依赖
pip install kubernetes openshift PyYAML

# 验证 Helm 安装
helm version
```

### 步骤 3: 准备 Token

选择以下任一方式：

#### 方式 A: 环境变量（开发环境）

```bash
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
```

#### 方式 B: Ansible Vault（生产环境推荐）

```bash
# 创建 vault 密码文件
echo "your-secure-password" > ~/.vault_pass
chmod 600 ~/.vault_pass

# 创建加密的 secrets 文件
ansible-vault create vars/cloudflare_secrets.yml --vault-password-file ~/.vault_pass

# 在编辑器中添加:
cloudflare_tunnel_token: "eyJhIjoiY2FmZS0xMjM0..."
```

### 步骤 4: 部署新方案

#### 方式 A: 使用 Playbook

```bash
# 使用环境变量
ansible-playbook playbooks/cloudflared_k8s_helm.yml

# 或使用 Vault
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  -e @vars/cloudflare_secrets.yml \
  --vault-password-file ~/.vault_pass
```

#### 方式 B: 使用 Makefile

```bash
# 设置环境变量后
export CLOUDFLARE_TUNNEL_TOKEN="your-token"
make cf-k8s-deploy
```

#### 方式 C: 使用 Role

创建自定义 playbook:

```yaml
---
- name: Deploy Cloudflare Tunnel
  hosts: localhost
  gather_facts: no
  
  vars:
    cloudflare_tunnel_token: "{{ lookup('env', 'CLOUDFLARE_TUNNEL_TOKEN') }}"
  
  roles:
    - cloudflared_k8s
```

### 步骤 5: 验证部署

```bash
# 使用 Makefile
make cf-k8s-verify

# 或手动验证
kubectl get pods -n cloudflare-tunnel
kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared
helm list -n cloudflare-tunnel
```

---

## 📊 配置对比

### 旧方案配置

```bash
# 需要编辑多个文件
k8s_manifests/cloudflared/
├── 00-namespace.yaml       # Namespace
├── 01-secret.yaml          # Secret (需手动 base64 编码)
├── 02-configmap.yaml       # ConfigMap
├── 03-deployment.yaml      # Deployment
├── 04-hpa.yaml            # HPA
└── 05-pdb.yaml            # PDB
```

### 新方案配置

```bash
# 单一 Playbook 或 vars 文件
playbooks/cloudflared_k8s_helm.yml

# 可选：自定义配置
vars/custom_config.yml:
  replica_count: 3
  resources:
    requests:
      cpu: "200m"
      memory: "256Mi"
```

---

## 🔧 配置迁移对照表

| 旧方案 (YAML) | 新方案 (Helm) | 说明 |
|---------------|---------------|------|
| `03-deployment.yaml` → replicas | `replica_count: 2` | 副本数 |
| `01-secret.yaml` → token | `cloudflare_tunnel_token` | Token（自动加密） |
| `03-deployment.yaml` → resources | `resources:` | 资源限制 |
| `04-hpa.yaml` | Helm values → autoscaling | HPA 配置 |
| `05-pdb.yaml` | Helm values → podDisruptionBudget | PDB 配置 |

---

## 🎯 日常操作对比

### 更新部署

#### 旧方案
```bash
# 编辑多个 YAML 文件
vim k8s_manifests/cloudflared/03-deployment.yaml
kubectl apply -f k8s_manifests/cloudflared/
```

#### 新方案
```bash
# 重新运行 playbook（自动检测变更）
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX replica_count=3"
```

### 版本升级

#### 旧方案
```bash
# 手动修改镜像版本
vim k8s_manifests/cloudflared/03-deployment.yaml
kubectl apply -f k8s_manifests/cloudflared/03-deployment.yaml
```

#### 新方案
```bash
# 指定 Chart 版本
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX helm_chart_version=0.4.0"
```

### 回滚

#### 旧方案
```bash
# 手动恢复旧版本的 YAML 文件
kubectl apply -f k8s_manifests/cloudflared/03-deployment.yaml
```

#### 新方案
```bash
# Helm 自动回滚
helm rollback cloudflared -n cloudflare-tunnel
```

---

## 🔒 安全性增强

### 旧方案风险

```yaml
# 01-secret.yaml
data:
  token: ZXlKaElqb2lZMkZtWlMweE1qTTBOVFkzT... # base64 编码，容易泄露
```

### 新方案改进

```bash
# 1. 使用 Ansible Vault 加密整个文件
ansible-vault encrypt vars/cloudflare_secrets.yml

# 2. 或使用环境变量（不进入版本控制）
export CLOUDFLARE_TUNNEL_TOKEN="xxx"

# 3. 或 CI/CD secrets
# GitHub Actions: ${{ secrets.CLOUDFLARE_TUNNEL_TOKEN }}
```

---

## 📚 新方案文件结构

```
AnixOps-ansible/
├── playbooks/
│   └── cloudflared_k8s_helm.yml         # 主 Playbook
├── roles/
│   └── cloudflared_k8s/                  # Role (可选使用)
│       ├── README.md
│       ├── defaults/
│       │   └── main.yml                  # 默认变量
│       ├── tasks/
│       │   ├── main.yml                  # 主任务
│       │   ├── validate.yml              # 验证
│       │   ├── namespace.yml             # 命名空间
│       │   ├── helm_repo.yml             # Helm 仓库
│       │   ├── helm_deploy.yml           # 部署
│       │   └── verify.yml                # 验证
│       └── meta/
│           └── main.yml                  # 元信息
├── scripts/
│   └── cleanup_cloudflared.sh            # 清理脚本
├── docs/
│   ├── CLOUDFLARED_K8S_HELM.md          # 完整文档
│   └── CLOUDFLARED_K8S_QUICK_REF.md     # 快速参考
├── examples/
│   ├── cloudflared_simple.yml            # 简单示例
│   ├── cloudflared_advanced.yml          # 高级示例
│   └── cloudflared_multi_env.yml         # 多环境示例
└── vars/
    └── cloudflare_secrets.yml.example    # Secrets 示例
```

---

## ✅ 迁移检查清单

- [ ] 运行 `./scripts/cleanup_cloudflared.sh` 清理旧部署
- [ ] 验证 kind 集群已停止（如果使用）
- [ ] 安装必要依赖（kubectl, helm, ansible collections）
- [ ] 准备 Cloudflare Tunnel Token
- [ ] 选择 Token 管理方式（环境变量/Vault/命令行）
- [ ] 运行新的 Helm Playbook
- [ ] 验证部署状态
- [ ] 测试隧道连接
- [ ] 更新 CI/CD 配置（如果有）
- [ ] 删除旧的 k8s_manifests/cloudflared/ 目录（可选）

---

## 🆘 故障排查

### 问题 1: Token 未设置

```bash
Error: cloudflare_tunnel_token is not set!

解决方法:
export CLOUDFLARE_TUNNEL_TOKEN="your-token"
```

### 问题 2: Helm 未安装

```bash
Error: Helm is not installed

解决方法:
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### 问题 3: kubectl 连接失败

```bash
Error: Cannot connect to Kubernetes cluster

解决方法:
kubectl cluster-info
kubectl config view
```

### 问题 4: 旧资源未清理

```bash
Error: namespace "cloudflare-tunnel" already exists

解决方法:
./scripts/cleanup_cloudflared.sh
```

---

## 📞 获取帮助

- 📖 完整文档: [docs/CLOUDFLARED_K8S_HELM.md](CLOUDFLARED_K8S_HELM.md)
- 🚀 快速参考: [docs/CLOUDFLARED_K8S_QUICK_REF.md](CLOUDFLARED_K8S_QUICK_REF.md)
- 💡 示例: [examples/](../examples/)
- 🐛 Issues: https://github.com/AnixOps/AnixOps-ansible/issues

---

## 🎉 迁移成功后的优势

1. **更简单的管理**：单一 Playbook vs 多个 YAML 文件
2. **更安全**：Token 加密存储，不进入版本控制
3. **更可靠**：自动健康检查和回滚
4. **更灵活**：通过变量轻松定制
5. **更标准**：使用官方 Helm Chart，自动获取更新
6. **更易维护**：清晰的 Role 结构，模块化设计

---

祝您迁移顺利！🚀
