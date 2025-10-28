# Cloudflare Token 快速参考

## 📋 Token 类型

### 🔑 CLOUDFLARE_API_TOKEN
- **用途**: 管理 Cloudflare 资源（创建 Tunnel、管理 DNS 等）
- **权限**: 广泛的管理权限
- **使用工具**: `tunnel_manager.py`, `cloudflare_manager.py`
- **获取**: Dashboard → Profile → API Tokens → Create Token

### 🔐 CLOUDFLARE_TUNNEL_TOKEN
- **用途**: cloudflared 客户端连接认证
- **权限**: 特定 Tunnel 连接权限
- **使用场景**: Ansible/Kubernetes 部署 cloudflared
- **获取**: Dashboard → Tunnels → 选择 Tunnel → Copy Token

---

## 🚀 快速命令

```bash
# 设置 API Token (用于管理)
export CLOUDFLARE_API_TOKEN="your-api-token"
export CLOUDFLARE_ACCOUNT_ID="your-account-id"

# 创建 Tunnel 并获取 Tunnel Token
python tools/tunnel_manager.py create MyTunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --save-env

# 部署到 Ansible (使用 Tunnel Token)
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS..."
ansible-playbook playbooks/cloudflared_playbook.yml

# 部署到 Kubernetes (使用 Tunnel Token)
ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

---

## 🔄 变量名变更

| 旧名称 | 新名称 | 状态 |
|--------|--------|------|
| `CF_TUNNEL_TOKEN` | `CLOUDFLARE_TUNNEL_TOKEN` | ⚠️ 已弃用 |
| `CLOUDFLARE_API_TOKEN` | `CLOUDFLARE_API_TOKEN` | ✅ 保持不变 |

---

## ⚡ 工作流程

```
CLOUDFLARE_API_TOKEN (管理)
         ↓
  创建 Tunnel (tunnel_manager.py)
         ↓
  获得 CLOUDFLARE_TUNNEL_TOKEN (连接)
         ↓
  部署 cloudflared (Ansible/K8s)
```

---

## 📖 完整文档

详见: [CLOUDFLARE_TOKEN_MIGRATION.md](CLOUDFLARE_TOKEN_MIGRATION.md)
