# 🔐 AnixOps 秘密管理指南

[![Security: No Secrets Committed](https://img.shields.io/badge/Security-No_Secrets_Committed-success)](https://github.com/AnixOps/AnixOps-ansible)
[![Zero Trust](https://img.shields.io/badge/Architecture-Zero_Trust-blue)](https://github.com/AnixOps/AnixOps-ansible)

---

## 📋 目录

- [核心原则](#核心原则)
- [架构概览](#架构概览)
- [本地开发](#本地开发)
- [CI/CD (GitHub Actions)](#cicd-github-actions)
- [秘密类型](#秘密类型)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)
- [安全审计清单](#安全审计清单)

---

## 🎯 核心原则

### ❌ 绝对禁止 (NEVER DO)

```bash
# ❌ 永远不要这样做！
git add vault_password.txt
git commit -m "Add secrets"
git push

# ❌ 永远不要在代码中硬编码秘密
vars:
  api_token: "sk-1234567890abcdef"  # ❌ 错误！
```

### ✅ 正确的做法 (ALWAYS DO)

```yaml
# ✅ 从环境变量读取
vars:
  api_token: "{{ lookup('env', 'API_TOKEN') }}"

# ✅ 或使用 Ansible Vault (用于非敏感但需加密的配置)
vars:
  database_password: "{{ vault_database_password }}"
```

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    AnixOps Secrets Management                    │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐          ┌──────────────────────┐
│   本地开发环境        │          │   CI/CD 环境          │
│   Local Development  │          │   GitHub Actions     │
└──────────────────────┘          └──────────────────────┘
         │                                   │
         │                                   │
    .env 文件                          GitHub Secrets
  (已在 .gitignore)                 (Settings -> Secrets)
         │                                   │
         │                                   │
         ├───────────────┬───────────────────┤
         │               │                   │
         ▼               ▼                   ▼
   ┌─────────────────────────────────────────────┐
   │         环境变量 (Environment Variables)     │
   │   CF_TUNNEL_TOKEN, ANSIBLE_VAULT_PASSWORD   │
   └─────────────────────────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────┐
   │          Ansible Playbook                    │
   │   lookup('env', 'CF_TUNNEL_TOKEN')          │
   └─────────────────────────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────┐
   │          Ansible Role                        │
   │   roles/anix_cloudflared/tasks/main.yml     │
   └─────────────────────────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────┐
   │          目标服务器 (Target Server)          │
   │   Systemd Service (内存中，不写入磁盘)       │
   └─────────────────────────────────────────────┘
```

---

## 💻 本地开发

### 步骤 1: 复制环境变量模板

```bash
cp .env.example .env
```

### 步骤 2: 编辑 `.env` 文件

```bash
vim .env
```

填入真实值：

```bash
# Cloudflare Tunnel Token
export CF_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."

# 其他秘密
export ANSIBLE_VAULT_PASSWORD="my-secure-vault-password"
```

### 步骤 3: 加载环境变量

```bash
source .env
```

### 步骤 4: 验证

```bash
# 验证环境变量已加载
echo $CF_TUNNEL_TOKEN

# 应该输出: eyJhIjoiY2FmZS0xMjM0...
```

### 步骤 5: 运行 Playbook

```bash
ansible-playbook playbooks/cloudflared_playbook.yml
```

### 步骤 6: 清理 (可选)

```bash
# 从当前 shell 会话中移除环境变量
unset CF_TUNNEL_TOKEN
unset ANSIBLE_VAULT_PASSWORD
```

---

## 🤖 CI/CD (GitHub Actions)

### 步骤 1: 添加 GitHub Secrets

1. 进入仓库的 **Settings** 页面
2. 点击 **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 添加以下 Secrets:

| Secret 名称               | 说明                              | 示例值                        |
|--------------------------|-----------------------------------|------------------------------|
| `CF_TUNNEL_TOKEN`        | Cloudflare Tunnel Token           | `eyJhIjoiY2FmZS0xMjM0...`     |
| `SSH_PRIVATE_KEY`        | SSH 私钥（用于连接目标服务器）      | `-----BEGIN OPENSSH...`      |
| `ANSIBLE_VAULT_PASSWORD` | Ansible Vault 密码 (可选)         | `my-vault-password`          |

### 步骤 2: 在 Workflow 中引用 Secrets

```yaml
# .github/workflows/deploy-cloudflared.yml

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Deploy Cloudflare Tunnel
        env:
          # 🔐 关键：从 GitHub Secrets 读取并设置为环境变量
          CF_TUNNEL_TOKEN: ${{ secrets.CF_TUNNEL_TOKEN }}
        run: |
          ansible-playbook playbooks/cloudflared_playbook.yml
```

### 步骤 3: 触发 Workflow

```bash
# 手动触发 (workflow_dispatch)
# 在 GitHub UI 中: Actions -> Deploy Cloudflare Tunnel -> Run workflow

# 或通过推送代码触发 (如果配置了 push trigger)
git push origin main
```

---

## 🔑 秘密类型

### 1. Cloudflare Tunnel Token

**使用场景**: 部署 Cloudflare Tunnel (`anix_cloudflared` Role)

**获取方式**:
1. 登录 [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. 进入 **Access** → **Tunnels**
3. 创建或选择一个 Tunnel
4. 复制 Token (以 `eyJ` 开头的长字符串)

**使用方式**:
```yaml
# Playbook 中
vars:
  cf_tunnel_token: "{{ lookup('env', 'CF_TUNNEL_TOKEN') }}"
```

**本地开发**:
```bash
export CF_TUNNEL_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
```

**CI/CD**:
- 添加到 GitHub Secrets: `CF_TUNNEL_TOKEN`

---

### 2. SSH 私钥

**使用场景**: GitHub Actions 需要 SSH 连接到目标服务器

**获取方式**:
```bash
# 生成新的 SSH 密钥对 (如果没有)
ssh-keygen -t ed25519 -C "github-actions@anixops.com" -f ~/.ssh/anixops_deploy

# 查看私钥
cat ~/.ssh/anixops_deploy

# 部署公钥到目标服务器
ssh-copy-id -i ~/.ssh/anixops_deploy.pub root@your-server.com
```

**使用方式**:
```yaml
# Workflow 中
- name: Configure SSH key
  run: |
    mkdir -p ~/.ssh
    echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
```

**CI/CD**:
- 添加到 GitHub Secrets: `SSH_PRIVATE_KEY`
- 内容: 完整的私钥（包括 `-----BEGIN OPENSSH PRIVATE KEY-----`）

---

### 3. Ansible Vault 密码 (可选)

**使用场景**: 用于加密/解密 Ansible Vault 文件

**使用方式**:
```bash
# 加密文件
ansible-vault encrypt group_vars/all/vault.yml

# 解密文件 (使用环境变量中的密码)
export ANSIBLE_VAULT_PASSWORD="my-password"
ansible-playbook site.yml --vault-password-file <(echo $ANSIBLE_VAULT_PASSWORD)
```

**CI/CD**:
- 添加到 GitHub Secrets: `ANSIBLE_VAULT_PASSWORD`

---

## 📚 最佳实践

### ✅ DO (推荐做法)

1. **使用环境变量**
   ```bash
   export CF_TUNNEL_TOKEN="your-token"
   ansible-playbook playbooks/cloudflared_playbook.yml
   ```

2. **使用 `.env` 文件 (本地开发)**
   ```bash
   echo 'export CF_TUNNEL_TOKEN="your-token"' > .env
   source .env
   ```

3. **使用 GitHub Secrets (CI/CD)**
   ```yaml
   env:
     CF_TUNNEL_TOKEN: ${{ secrets.CF_TUNNEL_TOKEN }}
   ```

4. **使用 Ansible Vault (非敏感但需加密的配置)**
   ```bash
   ansible-vault encrypt group_vars/all/vault.yml
   ```

5. **定期轮换秘密**
   - Cloudflare Tunnel Token: 每 90 天
   - SSH 密钥: 每 180 天
   - 密码: 每 60 天

6. **最小权限原则**
   - 每个 Token 只授予必要的权限
   - 使用专用的 SSH 密钥对进行部署

---

### ❌ DON'T (避免的做法)

1. **不要硬编码秘密**
   ```yaml
   # ❌ 错误！
   vars:
     api_key: "sk-1234567890"
   ```

2. **不要提交 `.env` 文件**
   ```bash
   # ❌ 错误！
   git add .env
   git commit -m "Add config"
   ```

3. **不要在日志中打印秘密**
   ```yaml
   # ❌ 错误！
   - name: Debug token
     debug:
       msg: "Token is {{ cf_tunnel_token }}"
   ```

4. **不要在 README 中包含真实秘密**
   ```markdown
   ❌ 错误！
   Token: eyJhIjoiY2FmZS0xMjM0...
   ```

5. **不要使用弱密码**
   ```bash
   # ❌ 错误！
   export ANSIBLE_VAULT_PASSWORD="123456"
   ```

---

## 🔍 常见问题

### Q1: 如何检查环境变量是否已设置？

```bash
# 方法 1: 使用 echo
echo $CF_TUNNEL_TOKEN

# 方法 2: 使用 env
env | grep CF_TUNNEL_TOKEN

# 方法 3: 使用 printenv
printenv CF_TUNNEL_TOKEN
```

---

### Q2: Playbook 运行失败，提示 "cf_tunnel_token is not set"？

**原因**: 环境变量未设置或未加载

**解决方案**:
```bash
# 1. 检查环境变量
echo $CF_TUNNEL_TOKEN

# 2. 如果为空，重新加载 .env
source .env

# 3. 再次验证
echo $CF_TUNNEL_TOKEN

# 4. 重新运行 Playbook
ansible-playbook playbooks/cloudflared_playbook.yml
```

---

### Q3: GitHub Actions 失败，提示 "Token is not set"？

**原因**: GitHub Secret 未配置或名称错误

**解决方案**:
1. 检查 Secret 名称是否为 `CF_TUNNEL_TOKEN` (区分大小写)
2. 检查 Workflow 中的引用: `${{ secrets.CF_TUNNEL_TOKEN }}`
3. 确保 Secret 的值不为空

---

### Q4: 如何在 Playbook 中打印部分 Token 用于调试 (不泄露完整值)？

```yaml
- name: Debug token (first 10 chars only)
  debug:
    msg: "Token starts with: {{ cf_tunnel_token[:10] }}..."
  when: cf_tunnel_token is defined
```

---

### Q5: 如何从当前 Shell 中移除环境变量？

```bash
# 移除单个变量
unset CF_TUNNEL_TOKEN

# 移除多个变量
unset CF_TUNNEL_TOKEN ANSIBLE_VAULT_PASSWORD

# 或退出当前 Shell 会话
exit
```

---

## 🛡️ 安全审计清单

在提交代码前，请确保:

- [ ] `.gitignore` 中包含 `.env`
- [ ] `.gitignore` 中包含 `*.pem` (SSL 证书)
- [ ] `.gitignore` 中包含 `.vault_password.txt`
- [ ] 所有敏感变量都通过环境变量传递
- [ ] Playbook 中使用 `lookup('env', 'VAR_NAME')`
- [ ] GitHub Secrets 已正确配置
- [ ] Workflow 中通过 `env:` 传递 Secrets
- [ ] 没有在代码中硬编码任何秘密
- [ ] 没有在日志中打印完整的秘密值
- [ ] `.env.example` 中只包含占位符，不包含真实值

---

## 🔗 相关文档

- [Cloudflare Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [GitHub Actions Secrets 文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Ansible Vault 文档](https://docs.ansible.com/ansible/latest/user_guide/vault.html)
- [AnixOps Cloudflared Role README](../roles/anix_cloudflared/README.md)
- [AnixOps Quick Start Guide](./QUICKSTART.md)

---

## 🙋 支持

如有问题，请在 [GitHub Issues](https://github.com/AnixOps/AnixOps-ansible/issues) 中提交。

---

**⚠️ 最后提醒**: 安全是一个持续的过程。定期审查你的秘密管理实践，确保符合最新的安全标准。

**🔐 Remember**: Trust, but verify. Never commit secrets.

---

**AnixOps Team**  
Last Updated: 2025-10-27
