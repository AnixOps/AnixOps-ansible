# Ansible Cloudflared 自动化部署 - 重构版

## 📖 项目概述

这是一个经过重构的 Ansible 项目，用于自动化部署 Cloudflare Tunnel (cloudflared) 到 Kubernetes 集群。

**核心特性：**
- 🔄 支持本地开发（Kind）和生产环境（K3s）
- 🎯 清晰的角色分离和模块化设计
- 🔒 安全的密钥管理（支持 Ansible Vault）
- ✅ 完整的部署验证和错误处理
- 📊 详细的部署日志和状态展示

---

## 📁 项目结构

```
.
├── playbook-local.yml                    # 本地部署入口
├── playbook-production.yml               # 生产部署入口
├── inventories/                          # 环境配置
│   ├── local/                           # 本地环境
│   │   ├── hosts.ini                    # 本地 inventory
│   │   └── group_vars/
│   │       └── all.yml                  # 全局变量
│   └── production/                      # 生产环境
│       ├── hosts.ini                    # 生产 inventory
│       └── group_vars/
│           └── all.yml                  # 全局变量
├── roles/                               # Ansible Roles
│   ├── k8s_provision/                   # K8s 集群部署
│   │   ├── defaults/
│   │   │   └── main.yml                 # 默认变量
│   │   ├── tasks/
│   │   │   ├── main.yml                 # 主任务
│   │   │   ├── prerequisites.yml        # 前置检查
│   │   │   ├── provision_kind.yml       # Kind 部署
│   │   │   ├── provision_k3s.yml        # K3s 部署
│   │   │   └── verify.yml               # 验证
│   │   ├── meta/
│   │   │   └── main.yml                 # Role 元数据
│   │   └── README.md
│   └── cloudflared_deploy/              # Cloudflared 部署
│       ├── defaults/
│       │   └── main.yml                 # 默认变量
│       ├── tasks/
│       │   ├── main.yml                 # 主任务
│       │   ├── validate.yml             # 变量验证
│       │   ├── helm_repo.yml            # Helm 仓库
│       │   ├── namespace.yml            # 命名空间
│       │   ├── secrets.yml              # Secret 管理
│       │   ├── helm_deploy.yml          # Helm 部署
│       │   └── verify.yml               # 验证
│       ├── meta/
│       │   └── main.yml                 # Role 元数据
│       └── README.md
└── vars/                                # 变量文件
    └── secrets.yml.example              # 密钥示例文件
```

---

## 🚀 快速开始

### 前置要求

1. **本地环境**：
   - Docker（必需）
   - Ansible 2.10+
   - Python 3.8+

2. **生产环境**：
   - 远程服务器（已安装 Docker）
   - SSH 访问权限
   - Cloudflare Tunnel Token

### 步骤 1: 克隆项目

```bash
git clone <your-repo>
cd AnixOps-ansible
```

### 步骤 2: 配置 Inventory

#### 本地环境（已配置完成）

本地环境使用 `inventories/local/hosts.ini`，默认配置已就绪。

#### 生产环境（需要配置）

编辑 `inventories/production/hosts.ini`：

```ini
[k8s_production]
prod-k8s-master ansible_host=YOUR_SERVER_IP

[k8s_production:vars]
environment=production
ansible_user=root
ansible_ssh_private_key_file=~/.ssh/id_rsa
```

### 步骤 3: 获取 Cloudflare Tunnel Token

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 **Zero Trust** > **Access** > **Tunnels**
3. 创建新的 Tunnel 或选择现有 Tunnel
4. 复制 **Tunnel Token**（以 `eyJ` 开头的长字符串）

### 步骤 4: 部署

#### 本地部署（Kind）

```bash
# 方式 1: 直接传递 Token
ansible-playbook playbook-local.yml \
  -i inventories/local/hosts.ini \
  --extra-vars "cloudflare_tunnel_token=YOUR_TOKEN_HERE"

# 方式 2: 使用环境变量
export CLOUDFLARE_TUNNEL_TOKEN="YOUR_TOKEN_HERE"
ansible-playbook playbook-local.yml -i inventories/local/hosts.ini
```

#### 生产部署（K3s）

```bash
# 使用 Ansible Vault（推荐）
# 1. 创建加密的 secrets 文件
ansible-vault create vars/secrets.yml

# 2. 在打开的编辑器中添加：
---
cloudflare_tunnel_token: "YOUR_TOKEN_HERE"

# 3. 保存并退出，运行 playbook
ansible-playbook playbook-production.yml \
  -i inventories/production/hosts.ini \
  --extra-vars "@vars/secrets.yml" \
  --ask-vault-pass
```

---

## 🔧 配置说明

### K8s Provision Role 变量

在 inventory 文件中配置：

```ini
# Kind（本地）
k8s_provider=kind
kind_cluster_name=cloudflared-dev
kind_api_server_port=6443

# K3s（生产）
k8s_provider=k3s
k3s_version=v1.28.5+k3s1
k3s_server_options="--disable traefik --write-kubeconfig-mode 644"
```

### Cloudflared Deploy Role 变量

```yaml
# 基础配置
cloudflared_namespace: cloudflared
cloudflared_release_name: cloudflared

# 副本数（生产建议 2+）
cloudflared_replica_count: 1

# 资源限制
cloudflared_resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

---

## 📊 验证部署

### 本地环境

```bash
# 查看集群状态
kubectl cluster-info --context kind-cloudflared-dev

# 查看 Pod
kubectl get pods -n cloudflared

# 查看日志
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared

# 删除集群
kind delete cluster --name cloudflared-dev
```

### 生产环境

```bash
# SSH 到服务器
ssh root@YOUR_SERVER_IP

# 查看节点
kubectl get nodes

# 查看 Pod
kubectl get pods -n cloudflared

# 查看日志
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared

# 检查 K3s 状态
systemctl status k3s
```

---

## 🏷️ Ansible Tags

使用 tags 来运行特定任务：

```bash
# 只运行 K8s 部署
ansible-playbook playbook-local.yml -i inventories/local/hosts.ini --tags "k8s"

# 只运行 Cloudflared 部署
ansible-playbook playbook-local.yml -i inventories/local/hosts.ini --tags "cloudflared"

# 只运行验证
ansible-playbook playbook-local.yml -i inventories/local/hosts.ini --tags "verification"

# 跳过验证
ansible-playbook playbook-local.yml -i inventories/local/hosts.ini --skip-tags "verification"
```

---

## 🔒 安全最佳实践

### 1. 使用 Ansible Vault

```bash
# 创建加密文件
ansible-vault create vars/secrets.yml

# 编辑加密文件
ansible-vault edit vars/secrets.yml

# 查看加密文件
ansible-vault view vars/secrets.yml

# 修改密码
ansible-vault rekey vars/secrets.yml
```

### 2. 使用密码文件

```bash
# 创建密码文件（不要提交到 Git）
echo "your-vault-password" > ~/.vault_pass
chmod 600 ~/.vault_pass

# 使用密码文件
ansible-playbook playbook-production.yml \
  -i inventories/production/hosts.ini \
  --extra-vars "@vars/secrets.yml" \
  --vault-password-file ~/.vault_pass
```

### 3. 使用环境变量

```bash
# 在 CI/CD 中
export CLOUDFLARE_TUNNEL_TOKEN="${{ secrets.CLOUDFLARE_TUNNEL_TOKEN }}"
ansible-playbook playbook-production.yml -i inventories/production/hosts.ini
```

---

## 🐛 故障排除

### 1. Kind 集群无法创建

```bash
# 检查 Docker 是否运行
docker ps

# 删除旧集群
kind delete cluster --name cloudflared-dev

# 重新运行
ansible-playbook playbook-local.yml -i inventories/local/hosts.ini
```

### 2. K3s 安装失败

```bash
# SSH 到服务器检查
ssh root@YOUR_SERVER_IP

# 查看 K3s 日志
journalctl -u k3s -f

# 卸载 K3s
/usr/local/bin/k3s-uninstall.sh
```

### 3. Cloudflared Pod 不健康

```bash
# 查看 Pod 详情
kubectl describe pod -n cloudflared -l app.kubernetes.io/name=cloudflared

# 查看日志
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared --tail=100

# 检查 Secret
kubectl get secret cloudflare-tunnel-token -n cloudflared -o yaml
```

### 4. Helm 部署失败

```bash
# 查看 Helm 版本
helm version

# 列出所有 releases
helm list -n cloudflared

# 删除 release 重新部署
helm uninstall cloudflared -n cloudflared
```

---

## 🔄 更新和维护

### 更新 Cloudflared

```bash
# 本地环境
ansible-playbook playbook-local.yml \
  -i inventories/local/hosts.ini \
  --tags "cloudflared" \
  --extra-vars "cloudflare_tunnel_token=YOUR_TOKEN"

# 生产环境
ansible-playbook playbook-production.yml \
  -i inventories/production/hosts.ini \
  --tags "cloudflared" \
  --extra-vars "@vars/secrets.yml" \
  --vault-password-file ~/.vault_pass
```

### 更新 Helm Chart 版本

编辑 inventory 文件：

```ini
helm_chart_version=0.4.0  # 更新版本
```

然后重新运行 playbook。

---

## 📚 进阶使用

### 多环境部署

```bash
# 创建更多环境
inventories/
  ├── local/
  ├── staging/
  └── production/

# 部署到不同环境
ansible-playbook playbook-production.yml -i inventories/staging/hosts.ini
```

### 自定义 Kind 配置

编辑 `roles/k8s_provision/tasks/provision_kind.yml` 中的配置：

```yaml
- name: Create kind cluster configuration
  ansible.builtin.copy:
    content: |
      kind: Cluster
      apiVersion: kind.x-k8s.io/v1alpha4
      name: {{ kind_cluster_name }}
      nodes:
        - role: control-plane
          extraPortMappings:
            - containerPort: 80
              hostPort: 80
            - containerPort: 443
              hostPort: 443
        - role: worker  # 添加 worker 节点
```

### 自定义 K3s 选项

在 inventory 中配置：

```ini
k3s_server_options="--disable traefik --disable servicelb --write-kubeconfig-mode 644"
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 📞 支持

如有问题，请创建 GitHub Issue 或查看以下文档：

- [Ansible 文档](https://docs.ansible.com/)
- [Kind 文档](https://kind.sigs.k8s.io/)
- [K3s 文档](https://docs.k3s.io/)
- [Cloudflare Tunnel 文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
