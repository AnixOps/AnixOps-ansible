# Cloudflared Deploy Role

此 Role 用于在 Kubernetes 集群上部署 Cloudflare Tunnel (cloudflared)，支持本地和生产环境。

## 功能特性

- **Helm 部署**: 使用官方 Helm Chart 部署 cloudflared
- **安全管理**: 支持多种方式提供 Cloudflare Tunnel Token
- **环境无关**: 自动适配 local (kind) 和 production (k3s) 环境
- **完整验证**: 部署后自动验证 Pod 状态和日志

## 前置要求

- Kubernetes 集群已部署并可访问
- kubectl 已配置
- Helm 3.x 已安装
- Cloudflare Tunnel Token

## 如何获取 Cloudflare Tunnel Token

1. 登录 Cloudflare Dashboard
2. 进入 Zero Trust > Access > Tunnels
3. 创建新的 Tunnel 或使用现有 Tunnel
4. 复制 Tunnel Token

## 角色变量

```yaml
# Cloudflare Tunnel Token (必需)
cloudflare_tunnel_token: "your-token-here"

# Kubernetes 配置
cloudflared_namespace: cloudflared
cloudflared_release_name: cloudflared

# 副本数量
cloudflared_replica_count: 1  # local环境建议1，production建议2+

# 资源限制
cloudflared_resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

## 使用示例

### 方式 1: 命令行传递 Token

```bash
ansible-playbook playbook-local.yml \
  --extra-vars "cloudflare_tunnel_token=eyJhIjoiY2FmZS0xMjM0..."
```

### 方式 2: 环境变量

```bash
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
ansible-playbook playbook-local.yml
```

### 方式 3: Ansible Vault (推荐用于生产)

```bash
# 创建加密文件
ansible-vault create vars/secrets.yml

# 在文件中添加:
---
cloudflare_tunnel_token: "your-token-here"

# 运行 playbook
ansible-playbook playbook-production.yml \
  --extra-vars "@vars/secrets.yml" \
  --vault-password-file ~/.vault_pass
```

## Tags

- `validation`: 只运行验证任务
- `helm`: 只运行 Helm 相关任务
- `repository`: 只设置 Helm 仓库
- `namespace`: 只创建命名空间
- `secrets`: 只创建 Secret
- `deploy`: 只运行部署任务
- `verification`: 只运行验证任务

## 验证部署

部署完成后，使用以下命令验证：

```bash
# 查看 Pod 状态
kubectl get pods -n cloudflared

# 查看 Pod 日志
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared

# 查看 Helm 发布状态
helm status cloudflared -n cloudflared
```
