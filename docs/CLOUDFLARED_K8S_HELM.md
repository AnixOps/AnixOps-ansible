# Cloudflare Tunnel Kubernetes 部署指南 (Helm 方式)

[![Ansible](https://img.shields.io/badge/Ansible-2.9+-blue)](https://www.ansible.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.20+-blue)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/Helm-v3+-blue)](https://helm.sh/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> 使用 Ansible + Helm 在 Kubernetes 集群上部署 Cloudflare Tunnel (cloudflared) 的最佳实践指南

---

## 📋 目录

- [概述](#概述)
- [架构说明](#架构说明)
- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [详细使用方法](#详细使用方法)
- [安全最佳实践](#安全最佳实践)
- [故障排查](#故障排查)
- [常见问题](#常见问题)

---

## 概述

本方案提供了一个生产级别的 Ansible Playbook，用于在 Kubernetes 集群上部署 Cloudflare Tunnel。

### 🎯 核心特性

- ✅ **使用官方 Helm Chart**：利用 Cloudflare 官方维护的 Helm Chart
- ✅ **安全凭据管理**：支持多种安全的 token 传递方式（Ansible Vault、环境变量、命令行）
- ✅ **高可用性配置**：默认 2 副本，支持自动扩缩容
- ✅ **资源管理**：合理的 CPU 和内存限制
- ✅ **健康检查**：配置了 liveness 和 readiness probe
- ✅ **Pod 反亲和性**：确保副本分散到不同节点
- ✅ **Prometheus 监控**：内置 metrics 端点

### 🆚 与旧方案的对比

| 特性 | 旧方案 (YAML manifests) | 新方案 (Helm) |
|------|------------------------|---------------|
| 部署方式 | kubectl apply | Helm Chart |
| 版本管理 | 手动 | Helm 自动管理 |
| 可维护性 | 低（需手动更新多个文件） | 高（单一 values 配置） |
| 回滚能力 | 无 | helm rollback |
| 配置管理 | 分散在多个文件 | 集中在 values |
| 升级流程 | 手动 | helm upgrade |

---

## 架构说明

```
┌─────────────────────────────────────────────────────────────┐
│                    Ansible Control Node                     │
│  (运行 ansible-playbook 的机器)                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ kubectl/helm API calls
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Namespace: cloudflare-tunnel                          │ │
│  │                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ cloudflared  │  │ cloudflared  │                  │ │
│  │  │   Pod 1      │  │   Pod 2      │  (2+ replicas)   │ │
│  │  └──────┬───────┘  └──────┬───────┘                  │ │
│  │         │                 │                           │ │
│  │         └────────┬────────┘                           │ │
│  │                  │                                     │ │
│  │         ┌────────▼────────┐                           │ │
│  │         │  Cloudflare     │                           │ │
│  │         │   Tunnel Token  │ (Secret)                  │ │
│  │         └─────────────────┘                           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Encrypted tunnel
                            ▼
                  ┌─────────────────────┐
                  │ Cloudflare Network  │
                  └─────────────────────┘
```

---

## 前置要求

### 1. 软件要求

#### Ansible Control Node（运行 playbook 的机器）

```bash
# 检查 Ansible 版本
ansible --version  # >= 2.9

# 检查 Python 版本
python3 --version  # >= 3.6

# 检查 kubectl
kubectl version --client

# 检查 Helm
helm version  # >= 3.0
```

#### 安装依赖

```bash
# 安装 Ansible Collections
ansible-galaxy collection install kubernetes.core

# 安装 Python 依赖
pip install kubernetes openshift PyYAML

# 安装 kubectl (如果未安装)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# 安装 Helm (如果未安装)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### 2. Kubernetes 集群

- Kubernetes 版本 >= 1.20
- 已配置 kubeconfig（`~/.kube/config`）
- 有足够权限创建 namespace、deployment 等资源

验证集群连接：

```bash
kubectl cluster-info
kubectl get nodes
```

### 3. Cloudflare 账户配置

1. 登录 Cloudflare Dashboard: https://dash.cloudflare.com/
2. 进入 **Zero Trust** → **Access** → **Tunnels**
3. 点击 **Create a tunnel**
4. 选择 **Cloudflared**
5. 复制 Tunnel Token（以 `eyJ` 开头的长字符串）

---

## 快速开始

### 方法 1: 使用命令行传递 Token（开发环境）

```bash
# 进入项目目录
cd /root/code/AnixOps-ansible

# 运行 playbook
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=eyJhIjoiY2FmZS0xMjM0..."
```

### 方法 2: 使用环境变量（开发环境）

```bash
# 设置环境变量
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."

# 运行 playbook
ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

### 方法 3: 使用 Ansible Vault（生产环境推荐）

```bash
# 步骤 1: 创建 vault 密码文件
echo "your-vault-password" > ~/.vault_pass
chmod 600 ~/.vault_pass

# 步骤 2: 创建加密的变量文件
ansible-vault create vars/cloudflare_secrets.yml --vault-password-file ~/.vault_pass

# 在编辑器中添加（文件会自动加密）:
cloudflare_tunnel_token: "eyJhIjoiY2FmZS0xMjM0..."

# 步骤 3: 运行 playbook
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  -e @vars/cloudflare_secrets.yml \
  --vault-password-file ~/.vault_pass
```

---

## 详细使用方法

### 使用 Role 方式部署

创建一个自定义 playbook：

```yaml
---
# my_cloudflared_deployment.yml
- name: Deploy Cloudflare Tunnel with custom settings
  hosts: localhost
  gather_facts: no
  
  vars:
    # Token 从 Vault 读取
    cloudflare_tunnel_token: "{{ vault_cloudflare_token }}"
    
    # 自定义配置
    k8s_namespace: "my-tunnel"
    replica_count: 3
    
    resources:
      requests:
        cpu: "200m"
        memory: "256Mi"
      limits:
        cpu: "1000m"
        memory: "1Gi"
  
  roles:
    - cloudflared_k8s
```

运行：

```bash
ansible-playbook my_cloudflared_deployment.yml \
  -e @vars/cloudflare_secrets.yml \
  --vault-password-file ~/.vault_pass
```

### 高级配置选项

#### 1. 修改副本数量

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX replica_count=3"
```

#### 2. 自定义命名空间

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX k8s_namespace=my-tunnel"
```

#### 3. 调整资源限制

创建变量文件 `vars/custom_resources.yml`:

```yaml
resources:
  requests:
    cpu: "200m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "1Gi"
```

运行：

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX" \
  -e @vars/custom_resources.yml
```

#### 4. 使用特定 Helm Chart 版本

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX helm_chart_version=0.3.0"
```

---

## 安全最佳实践

### 1. 永远不要硬编码 Token

❌ **错误做法**：

```yaml
vars:
  cloudflare_tunnel_token: "eyJhIjoiY2FmZS0xMjM0..."  # 不要这样做！
```

✅ **正确做法**：

```yaml
vars:
  cloudflare_tunnel_token: "{{ lookup('env', 'CLOUDFLARE_TUNNEL_TOKEN') }}"
```

### 2. 使用 Ansible Vault 加密敏感信息

```bash
# 创建加密文件
ansible-vault create vars/secrets.yml

# 编辑加密文件
ansible-vault edit vars/secrets.yml

# 查看加密文件
ansible-vault view vars/secrets.yml

# 重新加密（更改密码）
ansible-vault rekey vars/secrets.yml
```

### 3. 保护 Vault 密码文件

```bash
# 设置严格的文件权限
chmod 600 ~/.vault_pass

# 添加到 .gitignore
echo ".vault_pass" >> .gitignore
echo "vars/secrets.yml" >> .gitignore
```

### 4. CI/CD 中使用 GitHub Secrets

在 GitHub Actions 中：

```yaml
# .github/workflows/deploy.yml
env:
  CLOUDFLARE_TUNNEL_TOKEN: ${{ secrets.CLOUDFLARE_TUNNEL_TOKEN }}

steps:
  - name: Deploy Cloudflare Tunnel
    run: |
      ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

---

## 验证部署

### 检查 Pod 状态

```bash
# 查看 Pod
kubectl get pods -n cloudflare-tunnel

# 查看 Pod 详情
kubectl describe pods -n cloudflare-tunnel

# 查看 Pod 日志
kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared

# 实时查看日志
kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared -f
```

### 检查 Helm Release

```bash
# 查看 Helm releases
helm list -n cloudflare-tunnel

# 查看 Helm release 详情
helm status cloudflared -n cloudflare-tunnel

# 查看 Helm values
helm get values cloudflared -n cloudflare-tunnel
```

### 验证隧道连接

1. 登录 Cloudflare Dashboard
2. 进入 **Zero Trust** → **Access** → **Tunnels**
3. 确认隧道状态为 **Healthy**
4. 检查连接器数量（应该等于副本数）

---

## 更新和维护

### 更新 Helm Chart

```bash
# 方法 1: 重新运行 playbook（推荐）
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX helm_chart_version=0.4.0"

# 方法 2: 直接使用 Helm
helm repo update
helm upgrade cloudflared cloudflare/cloudflared \
  -n cloudflare-tunnel \
  --reuse-values
```

### 更新 Token

```bash
# 更新 Vault 文件
ansible-vault edit vars/cloudflare_secrets.yml

# 重新部署
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  -e @vars/cloudflare_secrets.yml \
  --vault-password-file ~/.vault_pass
```

### 扩容/缩容

```bash
# 扩容到 3 个副本
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX replica_count=3"

# 或直接使用 kubectl
kubectl scale deployment cloudflared -n cloudflare-tunnel --replicas=3
```

---

## 卸载

### 方法 1: 使用清理脚本（推荐）

```bash
./scripts/cleanup_cloudflared.sh
```

### 方法 2: 手动卸载

```bash
# 卸载 Helm release
helm uninstall cloudflared -n cloudflare-tunnel

# 删除命名空间
kubectl delete namespace cloudflare-tunnel

# 如果使用 kind 集群，可以删除整个集群
kind delete cluster --name your-cluster-name
```

---

## 故障排查

### Pod 无法启动

```bash
# 查看 Pod 事件
kubectl describe pod <pod-name> -n cloudflare-tunnel

# 常见原因:
# 1. Token 无效或过期
# 2. 资源不足
# 3. 镜像拉取失败
```

### Token 相关错误

```bash
# 错误信息: "cloudflare_tunnel_token is not set"
# 解决方法: 确保通过以下方式之一提供 token:
# 1. --extra-vars
# 2. 环境变量 CLOUDFLARE_TUNNEL_TOKEN
# 3. Ansible Vault 文件
```

### Helm 安装失败

```bash
# 查看 Helm 日志
helm history cloudflared -n cloudflare-tunnel

# 回滚到上一个版本
helm rollback cloudflared -n cloudflare-tunnel

# 强制重新安装
helm uninstall cloudflared -n cloudflare-tunnel
ansible-playbook playbooks/cloudflared_k8s_helm.yml --extra-vars "cloudflare_tunnel_token=XXX"
```

### 隧道连接不稳定

```bash
# 检查 Pod 日志
kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared

# 可能的原因:
# 1. 网络问题（检查出站连接）
# 2. 资源不足（增加 CPU/内存限制）
# 3. Pod 频繁重启（检查健康检查配置）
```

---

## 常见问题

### Q1: 如何查看 Helm values？

```bash
helm get values cloudflared -n cloudflare-tunnel
```

### Q2: 如何查看完整的 Kubernetes manifests？

```bash
helm get manifest cloudflared -n cloudflare-tunnel
```

### Q3: 如何启用 debug 日志？

修改 `log_level` 变量：

```bash
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX log_level=debug"
```

### Q4: 如何在多个集群中部署？

创建不同的 inventory 文件，针对每个集群的 kubeconfig：

```bash
# 切换 kubeconfig 上下文
kubectl config use-context cluster-1
ansible-playbook playbooks/cloudflared_k8s_helm.yml --extra-vars "cloudflare_tunnel_token=XXX"

kubectl config use-context cluster-2
ansible-playbook playbooks/cloudflared_k8s_helm.yml --extra-vars "cloudflare_tunnel_token=XXX"
```

### Q5: 如何监控 cloudflared？

Prometheus metrics 已启用，默认在端口 2000：

```bash
# Port-forward 到本地
kubectl port-forward -n cloudflare-tunnel deployment/cloudflared 2000:2000

# 访问 metrics
curl http://localhost:2000/metrics
```

---

## 进一步阅读

- [Cloudflare Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Cloudflare Helm Chart](https://github.com/cloudflare/helm-charts)
- [Ansible Kubernetes Collection](https://docs.ansible.com/ansible/latest/collections/kubernetes/core/index.html)
- [Helm 官方文档](https://helm.sh/docs/)

---

## 支持

如有问题，请：

1. 查看本文档的故障排查部分
2. 查看项目 Issues: https://github.com/AnixOps/AnixOps-ansible/issues
3. 提交新 Issue（附上详细的错误信息和环境描述）

---

## 许可

MIT License

## 作者

AnixOps Team
