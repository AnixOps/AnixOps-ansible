# Cloudflare Token 变量名更新说明

## 📋 变更概述

为了更清晰地区分两种不同用途的 Cloudflare Token，我们更新了环境变量命名：

### 旧变量名 → 新变量名

| 旧名称 | 新名称 | 用途 |
|--------|--------|------|
| `CF_TUNNEL_TOKEN` | `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel 连接 Token |
| `CLOUDFLARE_API_TOKEN` | `CLOUDFLARE_API_TOKEN` | Cloudflare API 管理 Token（保持不变） |

---

## 🎯 两种 Token 的区别

### 1. CLOUDFLARE_API_TOKEN（API 管理 Token）

**用途**: 管理 Cloudflare 资源（Tunnel、DNS、Zone 等）

**权限**: 广泛的管理权限

**使用场景**:
- `tunnel_manager.py` - 创建和管理 Tunnel
- `cloudflare_manager.py` - 管理 DNS 记录
- 其他需要管理 Cloudflare 资源的工具

**获取方式**:
```bash
1. 登录 https://dash.cloudflare.com/profile/api-tokens
2. 点击 "Create Token"
3. 选择模板 "Edit Cloudflare Tunnels" 或自定义权限
4. 设置权限:
   - Account > Cloudflare Tunnel > Edit
   - Zone > DNS > Edit (如果需要管理 DNS)
5. 复制生成的 API Token
```

**示例**:
```bash
export CLOUDFLARE_API_TOKEN="your-api-token-with-management-permissions"
```

### 2. CLOUDFLARE_TUNNEL_TOKEN（Tunnel 连接 Token）

**用途**: cloudflared 客户端连接到 Cloudflare 网络

**权限**: 仅限特定 Tunnel 的连接

**使用场景**:
- Ansible Playbooks 部署 cloudflared
- Kubernetes 部署 cloudflared
- Docker 运行 cloudflared
- 任何需要 cloudflared 连接的场景

**获取方式**:

方式 1: 从 Dashboard 手动获取
```bash
1. 登录 https://one.dash.cloudflare.com/
2. 导航到 Access -> Tunnels
3. 创建或选择一个 Tunnel
4. 复制 Tunnel Token (以 eyJ 开头的长字符串)
```

方式 2: 使用 tunnel_manager.py 自动创建
```bash
python tools/tunnel_manager.py create MyTunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --save-env
```

**示例**:
```bash
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
```

---

## 🔄 迁移指南

### 1. 更新 .env 文件

**旧的 .env**:
```bash
export CF_TUNNEL_TOKEN="your-tunnel-token"
export CLOUDFLARE_API_TOKEN="your-api-token"
```

**新的 .env**:
```bash
# Cloudflare API Token (用于管理资源)
export CLOUDFLARE_API_TOKEN="your-api-token"

# Cloudflare Tunnel Token (用于 cloudflared 连接)
export CLOUDFLARE_TUNNEL_TOKEN="your-tunnel-token"
```

### 2. 更新 CI/CD Secrets

如果您在 GitHub Actions 或其他 CI/CD 中使用：

**GitHub Actions**:
```yaml
# 旧配置
env:
  CF_TUNNEL_TOKEN: ${{ secrets.CF_TUNNEL_TOKEN }}

# 新配置
env:
  CLOUDFLARE_TUNNEL_TOKEN: ${{ secrets.CLOUDFLARE_TUNNEL_TOKEN }}
  CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}  # 如果需要
```

### 3. 更新脚本和命令

**旧命令**:
```bash
export CF_TUNNEL_TOKEN="your-token"
ansible-playbook playbooks/cloudflared_playbook.yml
```

**新命令**:
```bash
export CLOUDFLARE_TUNNEL_TOKEN="your-token"
ansible-playbook playbooks/cloudflared_playbook.yml
```

---

## ✅ 向后兼容性

为了确保平滑过渡，我们保持了向后兼容：

### Playbooks

旧的 `CF_TUNNEL_TOKEN` 仍然可以使用，但会显示弃用警告：

```yaml
# 优先使用新变量名，如果未找到则尝试旧变量名
cf_tunnel_token: "{{ lookup('env', 'CLOUDFLARE_TUNNEL_TOKEN') | default(lookup('env', 'CF_TUNNEL_TOKEN'), true) | default('') }}"
```

### 验证任务

错误消息会提示使用新变量名：
```
⚠️  Note: CF_TUNNEL_TOKEN is deprecated, please use CLOUDFLARE_TUNNEL_TOKEN
```

---

## 📝 使用示例

### 完整的工作流程

```bash
# 1. 加载环境变量
source .env

# 2. 使用 API Token 创建 Tunnel（获得 Tunnel Token）
python tools/tunnel_manager.py create MyTunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --save-env

# 3. 使用 Tunnel Token 部署 cloudflared
# tunnel_manager.py 已经自动设置了 CLOUDFLARE_TUNNEL_TOKEN
ansible-playbook playbooks/cloudflared_playbook.yml

# 或部署到 Kubernetes
ansible-playbook playbooks/cloudflared_k8s_helm.yml
```

### 手动设置两种 Token

```bash
# API Token (用于管理)
export CLOUDFLARE_API_TOKEN="your-api-token-here"

# Tunnel Token (用于连接)
export CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."

# Account ID
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
```

---

## 🔍 检查当前配置

```bash
# 检查环境变量是否设置
echo "API Token: ${CLOUDFLARE_API_TOKEN:0:10}..."
echo "Tunnel Token: ${CLOUDFLARE_TUNNEL_TOKEN:0:10}..."
echo "Account ID: $CLOUDFLARE_ACCOUNT_ID"

# 验证 .env 文件
cat .env | grep -E 'CLOUDFLARE_.*TOKEN'
```

---

## ⚠️ 重要提示

1. **不要混淆两种 Token**:
   - API Token 用于**管理**（创建、删除、配置）
   - Tunnel Token 用于**连接**（cloudflared 客户端）

2. **权限范围不同**:
   - API Token 权限广泛，可以管理多个资源
   - Tunnel Token 权限有限，仅用于特定 Tunnel 连接

3. **安全性**:
   - API Token 更敏感，需要更严格的保护
   - Tunnel Token 相对安全，仅用于连接

4. **获取方式**:
   - API Token: 从 Dashboard 手动创建
   - Tunnel Token: 可以通过 API Token 自动获取

---

## 📚 相关文档

- [Cloudflare API Token 文档](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Cloudflare Tunnel 文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [secrets_management.md](SECRETS_MANAGEMENT.md)

---

## 🆘 故障排查

### 问题 1: "cf_tunnel_token is not set"

```bash
# 检查环境变量
echo $CLOUDFLARE_TUNNEL_TOKEN

# 如果为空，设置它
export CLOUDFLARE_TUNNEL_TOKEN="your-tunnel-token"

# 或加载 .env
source .env
```

### 问题 2: "API Token 无效"

```bash
# 确保使用的是 API Token 而不是 Tunnel Token
# API Token 通常更短，不以 eyJ 开头
export CLOUDFLARE_API_TOKEN="your-api-token"

# 验证权限设置是否正确
```

### 问题 3: 旧脚本不工作

```bash
# 临时兼容：同时设置两个变量
export CF_TUNNEL_TOKEN="$CLOUDFLARE_TUNNEL_TOKEN"
export CLOUDFLARE_TUNNEL_TOKEN="your-token"
```

---

## 📅 更新时间线

- **2025-10-28**: 引入新变量名 `CLOUDFLARE_TUNNEL_TOKEN`
- **未来版本**: 将完全移除 `CF_TUNNEL_TOKEN` 支持

请尽快更新您的配置以使用新变量名！
