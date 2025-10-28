# 🔧 Cloudflare Tunnel Manager

> 自动化管理 Cloudflare Tunnel 的 Python 工具

---

## 📋 功能特性

- ✅ **自动创建 Tunnel** - 通过 API 创建新的 Tunnel
- ✅ **自动获取 Token** - 无需手动复制粘贴
- ✅ **一键部署** - 集成 Ansible 和 Kubernetes 部署
- ✅ **批量管理** - 列出、更新、删除 Tunnel
- ✅ **零秘密入库** - Token 只存储在环境变量/Secret 中

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 获取 Cloudflare 认证信息

#### 方法 1: API Token (推荐)

1. 访问 https://dash.cloudflare.com/profile/api-tokens
2. 点击 **Create Token**
3. 使用 **Edit Cloudflare Zero Trust** 模板
4. 或自定义权限:
   - Account → Cloudflare Tunnel → Edit

```bash
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_API_TOKEN="your-api-token"
```

#### 方法 2: Global API Key (不推荐)

```bash
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_EMAIL="your-email"
export CLOUDFLARE_API_KEY="your-global-api-key"
```

### 3. 基本使用

```bash
# 创建 Tunnel 并自动部署到 Kubernetes
./tools/tunnel_manager.py create my-k8s-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --deploy-type kubernetes \
  --auto-deploy

# 创建 Tunnel 并部署到 Ansible
./tools/tunnel_manager.py create my-ansible-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --deploy-type ansible \
  --auto-deploy \
  --save-env

# 只创建 Tunnel，不部署
./tools/tunnel_manager.py create my-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN
```

---

## 📚 命令参考

### `create` - 创建 Tunnel

创建新的 Cloudflare Tunnel 并可选自动部署。

```bash
./tools/tunnel_manager.py create <tunnel-name> [OPTIONS]
```

**参数**:

| 参数 | 说明 | 必需 |
|------|------|------|
| `tunnel-name` | Tunnel 名称 | ✅ |
| `--account-id` | Cloudflare Account ID | ✅ |
| `--api-token` | API Token | ✅ (或使用 email+api-key) |
| `--deploy-type` | 部署类型: `ansible`, `kubernetes`, `none` | ❌ (默认: none) |
| `--auto-deploy` | 自动执行部署 | ❌ |
| `--save-env` | 保存 Token 到 .env 文件 | ❌ |
| `--limit` | Ansible: 限制目标主机 | ❌ |

**示例**:

```bash
# 创建并自动部署到 Kubernetes
./tools/tunnel_manager.py create k8s-prod-tunnel \
  --account-id abc123 \
  --api-token xyz789 \
  --deploy-type kubernetes \
  --auto-deploy

# 创建并保存到 .env (用于本地开发)
./tools/tunnel_manager.py create dev-tunnel \
  --account-id abc123 \
  --api-token xyz789 \
  --deploy-type ansible \
  --save-env

# 只创建，稍后手动部署
./tools/tunnel_manager.py create staging-tunnel \
  --account-id abc123 \
  --api-token xyz789
```

---

### `list` - 列出所有 Tunnel

列出账户下的所有 Tunnel 及其状态。

```bash
./tools/tunnel_manager.py list [OPTIONS]
```

**示例**:

```bash
./tools/tunnel_manager.py list \
  --account-id abc123 \
  --api-token xyz789

# 输出示例:
# ℹ️  找到 3 个 Tunnel:
#
#   • Name: k8s-prod-tunnel
#     ID: f70ff985-a4ef-4643-bbbc-4a0ed4fc8415
#     Status: healthy
#     Created: 2025-10-27T10:00:00Z
#     Connections: 3
#
#   • Name: dev-tunnel
#     ID: a1b2c3d4-e5f6-7890-1234-567890abcdef
#     Status: healthy
#     Created: 2025-10-25T15:30:00Z
#     Connections: 1
```

---

### `get-token` - 获取 Tunnel Token

获取已存在的 Tunnel 的 Token（用于重新部署或迁移）。

```bash
./tools/tunnel_manager.py get-token <tunnel-id> [OPTIONS]
```

**示例**:

```bash
./tools/tunnel_manager.py get-token f70ff985-a4ef-4643-bbbc-4a0ed4fc8415 \
  --account-id abc123 \
  --api-token xyz789

# 输出: eyJhIjoiNWFiNGU5Z...
```

---

### `delete` - 删除 Tunnel

删除指定的 Tunnel（会删除所有连接）。

```bash
./tools/tunnel_manager.py delete <tunnel-id> [OPTIONS]
```

**参数**:

| 参数 | 说明 |
|------|------|
| `--force` | 不确认直接删除 |

**示例**:

```bash
# 交互式删除
./tools/tunnel_manager.py delete f70ff985-a4ef-4643-bbbc-4a0ed4fc8415 \
  --account-id abc123 \
  --api-token xyz789

# 强制删除（不确认）
./tools/tunnel_manager.py delete f70ff985-a4ef-4643-bbbc-4a0ed4fc8415 \
  --account-id abc123 \
  --api-token xyz789 \
  --force
```

---

## 🔐 在 CI/CD 中使用

### GitHub Actions

```yaml
name: Deploy Cloudflare Tunnel

on:
  workflow_dispatch:
    inputs:
      tunnel_name:
        description: 'Tunnel Name'
        required: true
        default: 'k8s-prod-tunnel'

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install requests
      
      - name: Create Tunnel and Deploy
        env:
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
        run: |
          ./tools/tunnel_manager.py create ${{ inputs.tunnel_name }} \
            --account-id $CLOUDFLARE_ACCOUNT_ID \
            --api-token $CLOUDFLARE_API_TOKEN \
            --deploy-type kubernetes \
            --auto-deploy
```

### GitLab CI

```yaml
deploy-tunnel:
  stage: deploy
  image: python:3.11
  before_script:
    - pip install requests kubectl
  script:
    - ./tools/tunnel_manager.py create $CI_ENVIRONMENT_NAME-tunnel
      --account-id $CLOUDFLARE_ACCOUNT_ID
      --api-token $CLOUDFLARE_API_TOKEN
      --deploy-type kubernetes
      --auto-deploy
  only:
    - main
```

---

## 🎯 使用场景

### 场景 1: 本地开发

```bash
# 创建开发环境 Tunnel
./tools/tunnel_manager.py create dev-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --save-env

# .env 文件会自动更新
source .env

# 部署
ansible-playbook playbooks/cloudflared_playbook.yml
```

---

### 场景 2: 多环境部署

```bash
# 开发环境
./tools/tunnel_manager.py create dev-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --deploy-type kubernetes \
  --auto-deploy

# 预发布环境
./tools/tunnel_manager.py create staging-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --deploy-type kubernetes \
  --auto-deploy

# 生产环境
./tools/tunnel_manager.py create prod-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --deploy-type kubernetes \
  --auto-deploy
```

---

### 场景 3: Tunnel 迁移

```bash
# 1. 获取旧 Tunnel 的 Token
OLD_TOKEN=$(./tools/tunnel_manager.py get-token <old-tunnel-id> \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN)

# 2. 创建新 Tunnel
./tools/tunnel_manager.py create new-tunnel \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --deploy-type kubernetes \
  --auto-deploy

# 3. 验证新 Tunnel 工作正常后，删除旧 Tunnel
./tools/tunnel_manager.py delete <old-tunnel-id> \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN \
  --force
```

---

### 场景 4: 批量清理

```bash
# 列出所有 Tunnel
./tools/tunnel_manager.py list \
  --account-id $CLOUDFLARE_ACCOUNT_ID \
  --api-token $CLOUDFLARE_API_TOKEN

# 删除不需要的 Tunnel
for tunnel_id in tunnel-id-1 tunnel-id-2 tunnel-id-3; do
  ./tools/tunnel_manager.py delete $tunnel_id \
    --account-id $CLOUDFLARE_ACCOUNT_ID \
    --api-token $CLOUDFLARE_API_TOKEN \
    --force
done
```

---

## 🔍 故障排查

### 问题 1: "API 错误: Unauthorized"

**原因**: API Token 无效或权限不足

**解决方案**:
1. 验证 Token: https://dash.cloudflare.com/profile/api-tokens
2. 确保 Token 有以下权限:
   - Account → Cloudflare Tunnel → Edit

---

### 问题 2: "kubectl: command not found"

**原因**: Kubernetes 部署时 kubectl 未安装

**解决方案**:
```bash
# 安装 kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

---

### 问题 3: "账户 ID 不正确"

**原因**: CLOUDFLARE_ACCOUNT_ID 错误

**解决方案**:
1. 登录 Cloudflare Dashboard
2. 在 URL 中找到 Account ID: `dash.cloudflare.com/<account-id>/...`
3. 或在 **Account Settings** 中查看

---

## 📖 API 参考

此工具基于 Cloudflare API v4:
- [Tunnel API 文档](https://developers.cloudflare.com/api/operations/cloudflare-tunnel-get-a-cloudflare-tunnel-token)
- [认证方式](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)

---

## 🙋 获取帮助

```bash
# 查看帮助
./tools/tunnel_manager.py --help

# 查看子命令帮助
./tools/tunnel_manager.py create --help
./tools/tunnel_manager.py list --help
```

---

**AnixOps Team**  
Last Updated: 2025-10-27
