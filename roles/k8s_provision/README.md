# K8s Provision Role

此 Role 用于自动化部署 Kubernetes 集群，支持本地开发环境（使用 Kind）和生产环境（使用 K3s）。

## 功能特性

- **本地开发**: 自动安装和配置 Kind 集群
- **生产环境**: 自动部署 K3s 轻量级 Kubernetes
- **工具管理**: 自动安装 kubectl、helm 等必需工具
- **验证检查**: 确保集群状态正常后才继续

## 前置要求

- Docker（必需）
- Ansible 2.10+
- Linux 操作系统（Ubuntu/Debian）

## 角色变量

```yaml
# K8s 提供商选择
k8s_provider: kind  # 或 k3s

# Kind 配置（本地开发）
kind_cluster_name: cloudflared-dev
kind_cluster_config: /tmp/kind-config.yaml

# K3s 配置（生产环境）
k3s_version: v1.28.5+k3s1
k3s_server_options: "--disable traefik --write-kubeconfig-mode 644"

# Kubeconfig 路径
kubeconfig_path: "{{ ansible_env.HOME }}/.kube/config"
```

## 使用示例

```yaml
- hosts: localhost
  roles:
    - role: k8s_provision
      vars:
        k8s_provider: kind
        kind_cluster_name: my-dev-cluster
```

## Tags

- `prerequisites`: 只运行前置检查
- `kind`: 只运行 Kind 相关任务
- `k3s`: 只运行 K3s 相关任务
- `verification`: 只运行验证任务
