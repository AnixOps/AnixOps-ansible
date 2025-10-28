# Cloudflared Kubernetes Role

[![Ansible](https://img.shields.io/badge/Ansible-2.9+-blue)](https://www.ansible.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.20+-blue)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/Helm-v3+-blue)](https://helm.sh/)

> 使用 Helm Chart 在 Kubernetes 集群上部署 Cloudflare Tunnel 的 Ansible Role

## 📋 目录

- [概述](#概述)
- [前置要求](#前置要求)
- [Role 变量](#role-变量)
- [使用示例](#使用示例)
- [依赖](#依赖)
- [许可](#许可)

## 概述

此 Role 使用 Cloudflare 官方的 Helm Chart 在 Kubernetes 集群上部署 cloudflared。它提供：

- ✅ 使用官方 Helm Chart 部署
- ✅ 自动管理 Helm 仓库
- ✅ 命名空间管理
- ✅ 高可用性配置（多副本）
- ✅ 安全的凭据管理（不硬编码 token）
- ✅ 资源限制和请求
- ✅ Pod 反亲和性配置
- ✅ 健康检查配置

## 前置要求

### 软件要求

- Ansible >= 2.9
- Python >= 3.6
- kubectl 命令行工具
- Helm v3
- 可访问的 Kubernetes 集群

### Ansible Collections

```bash
ansible-galaxy collection install kubernetes.core
```

### Python 依赖

```bash
pip install kubernetes openshift PyYAML
```

### Kubernetes 要求

- Kubernetes 版本 >= 1.20
- 有足够权限创建 namespace、deployment 等资源
- 已配置 kubeconfig（~/.kube/config）

## Role 变量

### 必需变量

| 变量名 | 描述 | 示例 |
|--------|------|------|
| `cloudflare_tunnel_token` | Cloudflare Tunnel Token | `eyJhIjoiY2FmZS0xMjM0...` |

### 可选变量

| 变量名 | 默认值 | 描述 |
|--------|---------|------|
| `k8s_namespace` | `cloudflare-tunnel` | Kubernetes 命名空间 |
| `k8s_release_name` | `cloudflared` | Helm release 名称 |
| `helm_repo_name` | `cloudflare` | Helm 仓库名称 |
| `helm_repo_url` | `https://cloudflare.github.io/helm-charts` | Helm 仓库 URL |
| `helm_chart_name` | `cloudflare/cloudflared` | Helm Chart 名称 |
| `helm_chart_version` | `""` (最新) | Helm Chart 版本 |
| `replica_count` | `2` | Pod 副本数量 |

### 资源配置

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

## 使用示例

### 基本使用

```yaml
---
- name: Deploy Cloudflare Tunnel
  hosts: localhost
  roles:
    - role: cloudflared_k8s
      vars:
        cloudflare_tunnel_token: "{{ lookup('env', 'CLOUDFLARE_TUNNEL_TOKEN') }}"
```

### 自定义配置

```yaml
---
- name: Deploy Cloudflare Tunnel with custom settings
  hosts: localhost
  roles:
    - role: cloudflared_k8s
      vars:
        cloudflare_tunnel_token: "{{ vault_cloudflare_token }}"
        k8s_namespace: "my-tunnel"
        replica_count: 3
        resources:
          requests:
            cpu: "200m"
            memory: "256Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
```

### 使用 Ansible Vault

```bash
# 创建加密的变量文件
ansible-vault create vars/cloudflare_secrets.yml

# 在文件中添加
cloudflare_tunnel_token: "eyJhIjoiY2FmZS0xMjM0..."

# 运行 playbook
ansible-playbook playbook.yml --vault-password-file ~/.vault_pass
```

## 依赖

此 Role 需要以下 Ansible Collections：

```yaml
collections:
  - kubernetes.core
```

安装方法：

```bash
ansible-galaxy collection install kubernetes.core
```

## Tags

此 Role 支持以下 tags：

- `validation` - 仅运行验证任务
- `namespace` - 仅管理命名空间
- `helm` - 仅运行 Helm 相关任务
- `cloudflared` - 运行所有 cloudflared 相关任务
- `deploy` - 仅运行部署任务
- `verification` - 仅运行验证任务

使用示例：

```bash
# 仅运行验证
ansible-playbook playbook.yml --tags validation

# 跳过验证
ansible-playbook playbook.yml --skip-tags verification
```

## 卸载

使用 Helm 卸载：

```bash
helm uninstall cloudflared -n cloudflare-tunnel
kubectl delete namespace cloudflare-tunnel
```

或使用清理脚本：

```bash
./scripts/cleanup_cloudflared.sh
```

## 许可

MIT

## 作者

AnixOps Team
