# AnixOps Ansible 自动化部署项目

![Version](https://img.shields.io/badge/version-v0.1.0-blue?style=flat-square)
![Kubernetes](https://img.shields.io/badge/kubernetes-ready-326CE5?style=flat-square&logo=kubernetes&logoColor=white)
![Ansible](https://img.shields.io/badge/ansible-2.10+-EE0000?style=flat-square&logo=ansible&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

一个功能完整、结构清晰的 Ansible 自动化部署项目，支持本地开发和生产环境的 Kubernetes 和 Cloudflare Tunnel 部署。

---

## 🚀 快速开始

### 1. 本地部署（最快方式）

```bash
# 使用统一脚本快速部署到本地 Kind 集群
./scripts/anixops.sh deploy-local -t "your-cloudflare-tunnel-token"
```

### 2. 生产部署

```bash
# 配置生产服务器 inventory
vim inventories/production/hosts.ini

# 使用 Vault 安全部署
./scripts/anixops.sh deploy-production --vault-password ~/.vault_pass
```

### 3. 静态网站部署（新功能）

```bash
# 部署静态网站并配置反向代理（支持 SSL）
export CF_SSL_CERT="$(cat cert.pem | base64 -w 0)"
export CF_SSL_KEY="$(cat key.pem | base64 -w 0)"
make deploy-static-web

# 详细文档
# 查看 docs/STATIC_WEB_DEPLOYMENT.md
```

---

## 📁 项目结构

```
AnixOps-ansible/
├── playbooks/                    # 📚 Playbooks（多级目录）
│   ├── deployment/              # 部署相关
│   │   ├── local.yml           # 本地 Kind 部署
│   │   ├── production.yml      # 生产 K3s 部署
│   │   ├── quick-setup.yml     # 快速设置
│   │   ├── site.yml            # 完整站点
│   │   └── web-servers.yml     # Web 服务器
│   ├── cloudflared/            # Cloudflared 专用
│   │   ├── k8s-helm.yml       # Helm 部署
│   │   ├── k8s-local.yml      # 本地部署
│   │   └── standalone.yml      # 独立部署
│   ├── maintenance/            # 维护管理
│   │   ├── health-check.yml
│   │   ├── firewall-setup.yml
│   │   └── observability.yml
│   └── README.md               # Playbooks 详细说明
│
├── inventories/                 # 🗂️ 环境配置（分离）
│   ├── local/                  # 本地环境
│   │   ├── hosts.ini
│   │   └── group_vars/
│   └── production/             # 生产环境
│       ├── hosts.ini
│       └── group_vars/
│
├── roles/                       # 🎭 Ansible Roles
│   ├── k8s_provision/          # K8s 集群部署（Kind/K3s）
│   │   ├── defaults/
│   │   ├── tasks/
│   │   │   ├── main.yml
│   │   │   ├── prerequisites.yml
│   │   │   ├── provision_kind.yml
│   │   │   ├── provision_k3s.yml
│   │   │   └── verify.yml
│   │   └── README.md
│   └── cloudflared_deploy/     # Cloudflared 部署
│       ├── defaults/
│       ├── tasks/
│       │   ├── main.yml
│       │   ├── validate.yml
│       │   ├── helm_repo.yml
│       │   ├── helm_deploy.yml
│       │   └── verify.yml
│       └── README.md
│
├── vars/                        # 🔐 变量和密钥
│   └── secrets.yml.example     # 密钥模板
│
├── scripts/                     # 🔧 管理脚本
│   ├── anixops.sh              # 统一管理脚本（主入口）
│   └── ...（其他工具脚本）
│
├── docs/                        # 📖 文档
│   ├── REFACTORED_DEPLOYMENT_GUIDE.md  # 重构后的详细指南
│   └── ...（其他文档）
│
└── ansible.cfg                  # ⚙️ Ansible 配置
```

---

## 🛠️ scripts/anixops.sh 使用指南

### 所有可用命令

```bash
./scripts/anixops.sh [COMMAND] [OPTIONS]
```

### 命令列表

| 命令 | 说明 |
|------|------|
| `deploy-local` | 部署到本地 Kind 集群 |
| `deploy-production` | 部署到生产 K3s 集群 |
| `cleanup-local` | 清理本地环境 |
| `cleanup-production` | 清理生产环境（危险） |
| `status-local` | 查看本地集群状态 |
| `status-production` | 查看生产集群状态 |
| `test` | 运行语法检查 |
| `help` | 显示帮助信息 |

### 选项参数

| 选项 | 说明 |
|------|------|
| `-t, --token TOKEN` | Cloudflare Tunnel Token |
| `--vault-password FILE` | Vault 密码文件路径 |
| `--ask-vault-pass` | 交互式输入 Vault 密码 |
| `--tags TAGS` | 只运行指定的 tags |
| `--skip-tags TAGS` | 跳过指定的 tags |
| `-v, --verbose` | 详细输出 |
| `--dry-run` | 测试运行（不执行） |

### 使用示例

```bash
# 1. 本地部署（直接传 token）
./scripts/anixops.sh deploy-local -t "eyJhIjoiY2FmZS0xMjM0..."

# 2. 本地部署（使用环境变量）
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
./scripts/anixops.sh deploy-local

# 3. 生产部署（使用 Vault）
./scripts/anixops.sh deploy-production --vault-password ~/.vault_pass

# 4. 查看本地状态
./scripts/anixops.sh status-local

# 5. 清理本地环境
./scripts/anixops.sh cleanup-local

# 6. 只部署 K8s（不部署 cloudflared）
./scripts/anixops.sh deploy-local --tags k8s

# 7. 测试运行（不实际执行）
./scripts/anixops.sh deploy-local --dry-run -v

# 8. 运行语法检查
./scripts/anixops.sh test
```

---

## 📋 详细使用流程

### 场景 1: 本地开发测试

**目标**: 在本地 Kind 集群测试 Cloudflared

```bash
# 步骤 1: 准备 Token
# 从 Cloudflare Dashboard 获取 Tunnel Token

```bash
# 步骤 2: 部署
./scripts/anixops.sh deploy-local -t "your-token"

# 步骤 3: 验证
kubectl get pods -n cloudflared
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared

# 步骤 4: 清理（可选）
./scripts/anixops.sh cleanup-local
```
```

### 场景 2: 生产环境部署

**目标**: 在远程服务器部署 K3s 和 Cloudflared

```bash
# 步骤 1: 配置生产 inventory
vim inventories/production/hosts.ini
# 修改 ansible_host 为你的服务器 IP

# 步骤 2: 创建加密的 secrets 文件
ansible-vault create vars/secrets.yml
# 添加: cloudflare_tunnel_token: "your-token"

# 步骤 3: 创建 Vault 密码文件
echo "your-vault-password" > ~/.vault_pass
chmod 600 ~/.vault_pass

```bash
# 步骤 4: 部署
./scripts/anixops.sh deploy-production --vault-password ~/.vault_pass

# 步骤 5: 验证
./scripts/anixops.sh status-production
# 或 SSH 到服务器
ssh root@your-server-ip
kubectl get pods -n cloudflared
```
```

### 场景 3: 只部署 K8s（不部署应用）

```bash
# 本地
./scripts/anixops.sh deploy-local --tags k8s --skip-tags cloudflared

# 生产
./scripts/anixops.sh deploy-production --tags k8s --skip-tags cloudflared
```

### 场景 4: 只部署 Cloudflared（K8s 已存在）

```bash
# 本地
./scripts/anixops.sh deploy-local --tags cloudflared

# 生产
./scripts/anixops.sh deploy-production --tags cloudflared --vault-password ~/.vault_pass
```

---

## 🔧 配置说明

### 本地环境配置

文件: `inventories/local/hosts.ini`

```ini
[k8s_local]
localhost ansible_connection=local

[k8s_local:vars]
environment=local
k8s_provider=kind
kind_cluster_name=cloudflared-dev
cloudflared_replica_count=1
```

### 生产环境配置

文件: `inventories/production/hosts.ini`

```ini
[k8s_production]
prod-k8s-master ansible_host=YOUR_SERVER_IP  # 修改这里

[k8s_production:vars]
environment=production
k8s_provider=k3s
ansible_user=root
ansible_ssh_private_key_file=~/.ssh/id_rsa
cloudflared_replica_count=2  # 生产环境建议 2+ 副本
```

---

## 🔒 安全管理

### 使用 Ansible Vault（推荐）

```bash
# 创建加密的 secrets 文件
ansible-vault create vars/secrets.yml

# 在编辑器中添加：
---
cloudflare_tunnel_token: "your-token-here"

# 编辑已加密的文件
ansible-vault edit vars/secrets.yml

# 查看加密文件内容
ansible-vault view vars/secrets.yml

# 修改加密密码
ansible-vault rekey vars/secrets.yml
```

### 使用环境变量

```bash
# 设置环境变量
export CLOUDFLARE_TUNNEL_TOKEN="your-token"

# 部署
./anixops.sh deploy-local

# 或在 CI/CD 中
export CLOUDFLARE_TUNNEL_TOKEN="${{ secrets.CLOUDFLARE_TUNNEL_TOKEN }}"
```

---

## 🏷️ 使用 Tags

所有部署 playbooks 支持 tags：

```bash
# 可用的 Tags
--tags k8s              # 只运行 K8s 部署
--tags cloudflared      # 只运行 Cloudflared 部署
--tags helm             # 只运行 Helm 相关任务
--tags validation       # 只运行验证
--tags verification     # 只运行部署后验证
--tags prerequisites    # 只检查前置条件

# 跳过 Tags
--skip-tags verification  # 跳过验证步骤
--skip-tags cloudflared   # 只部署 K8s
```

---

## 📊 验证和监控

### 查看集群状态

```bash
# 本地
./scripts/anixops.sh status-local

# 生产
./scripts/anixops.sh status-production
```

### 手动验证命令

```bash
# 查看 Pod 状态
kubectl get pods -n cloudflared

# 查看 Pod 日志
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared --tail=50

# 查看所有资源
kubectl get all -n cloudflared

# 查看 Helm 发布
helm list -n cloudflared

# 查看节点状态
kubectl get nodes

# 检查 K3s 服务（生产环境）
systemctl status k3s
```

---

## 🐛 故障排除

### 问题 1: Docker 未运行

```bash
# 错误: Cannot connect to Docker daemon
sudo systemctl start docker
sudo systemctl enable docker
```

### 问题 2: Kind 集群创建失败

```bash
# 清理并重新创建
./scripts/anixops.sh cleanup-local
./scripts/anixops.sh deploy-local -t "your-token"
```

### 问题 3: Cloudflared Pod 无法启动

```bash
# 检查日志
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared

# 检查 Secret
kubectl get secret cloudflare-tunnel-token -n cloudflared -o yaml

# 检查 Token 是否正确
kubectl describe pod -n cloudflared
```

### 问题 4: 生产环境 SSH 连接失败

```bash
# 测试 SSH 连接
ssh root@YOUR_SERVER_IP

# 检查 inventory 配置
cat inventories/production/hosts.ini

# 使用 verbose 模式
./anixops.sh deploy-production -v --vault-password ~/.vault_pass
```

### 问题 5: Helm Chart 找不到

```bash
# 手动添加 Helm 仓库
helm repo add cloudflare https://cloudflare.github.io/helm-charts
helm repo update
helm search repo cloudflare
```

---

## 📚 更多文档

- [完整部署指南](docs/REFACTORED_DEPLOYMENT_GUIDE.md) - 详细的部署说明
- [静态网站部署指南](docs/STATIC_WEB_DEPLOYMENT.md) - 静态网站+反向代理部署 ⭐ 新
- [Playbooks 目录说明](playbooks/README.md) - 所有 playbooks 的详细说明
- [K8s Provision Role](roles/k8s_provision/README.md) - K8s 集群部署
- [Cloudflared Deploy Role](roles/cloudflared_deploy/README.md) - Cloudflared 部署
- [Static Web Deploy Role](roles/static_web_deploy/README.md) - 静态网站部署 ⭐ 新

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 🆘 获取帮助

```bash
# 查看帮助
./scripts/anixops.sh help

# 查看 Ansible 版本
ansible --version

# 测试语法
./scripts/anixops.sh test
```

---

**快速链接**:
- [获取 Cloudflare Tunnel Token](https://dash.cloudflare.com/) → Zero Trust → Access → Tunnels
- [Kind 文档](https://kind.sigs.k8s.io/)
- [K3s 文档](https://docs.k3s.io/)
- [Ansible 文档](https://docs.ansible.com/)
