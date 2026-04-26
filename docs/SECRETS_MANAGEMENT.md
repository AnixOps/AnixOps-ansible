# 🔐 AnixOps 秘密管理指南

[![Security: No Secrets Committed](https://img.shields.io/badge/Security-No_Secrets_Committed-success)](https://github.com/AnixOps/AnixOps-ansible)

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
   │   CLOUDFLARE_MESH_TOKEN, SSH_KEY_PATH, etc. │
   └─────────────────────────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────┐
   │          Ansible Playbook                    │
   │   lookup('env', 'CLOUDFLARE_MESH_TOKEN')    │
   └─────────────────────────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────┐
   │          Ansible Role                        │
   │   roles/cloudflare_mesh/tasks/main.yml     │
   └─────────────────────────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────┐
   │          目标服务器 (Target Server)          │
   │   warp-svc Service (内存中，不写入磁盘)      │
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
# Cloudflare Mesh Token
CLOUDFLARE_MESH_TOKEN=eyJhIjoiY2FmZS0xMjM0...

# 其他秘密
ANSIBLE_VAULT_PASSWORD=my-secure-vault-password
```

### 步骤 3: 加载环境变量

```bash
source .env
```

### 步骤 4: 运行 Playbook

```bash
ansible-playbook playbooks/provision/site.yml --tags cloudflare_mesh
```

---

## 🤖 CI/CD (GitHub Actions)

### 步骤 1: 添加 GitHub Secrets

1. 进入仓库的 **Settings** 页面
2. 点击 **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 添加以下 Secrets:

| Secret 名称                | 说明                              | 示例值                        |
|--------------------------|-----------------------------------|------------------------------|
| `CLOUDFLARE_MESH_TOKEN`  | Cloudflare Mesh enrollment token  | `eyJhIjoiY2FmZS0xMjM0...`     |
| `SSH_PRIVATE_KEY`        | SSH 私钥（用于连接目标服务器）      | `-----BEGIN OPENSSH...`      |
| `ANSIBLE_VAULT_PASSWORD` | Ansible Vault 密码 (可选)         | `my-vault-password`          |

### 步骤 2: 在 Workflow 中引用 Secrets

```yaml
# .github/workflows/deploy.yml

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Deploy Cloudflare Mesh
        env:
          CLOUDFLARE_MESH_TOKEN: ${{ secrets.CLOUDFLARE_MESH_TOKEN }}
        run: |
          ansible-playbook playbooks/provision/site.yml --tags cloudflare_mesh
```

---

## 🔑 秘密类型

### 1. Cloudflare Mesh Token

**使用场景**: 部署 Cloudflare Mesh 节点 (`cloudflare_mesh` Role)

**获取方式**:
1. 登录 [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. 进入 **Networking** → **Mesh**
3. 点击 **Add node**
4. 复制 enrollment token

**使用方式**:
```yaml
# Playbook 中
vars:
  cloudflare_mesh_token: "{{ lookup('env', 'CLOUDFLARE_MESH_TOKEN') }}"
```

**本地开发**:
```bash
export CLOUDFLARE_MESH_TOKEN="eyJhIjoiY2FmZS0xMjM0..."
```

**CI/CD**:
- 添加到 GitHub Secrets: `CLOUDFLARE_MESH_TOKEN`

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

---

### 4. Cloudflare DNS API Token

**使用场景**: ACME SSL 证书获取 (DNS 验证)

**获取方式**:
1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
2. Create Token → Edit Zone DNS
3. 复制生成的 API Token

**变量**: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID`

---

## 📚 最佳实践

### ✅ DO (推荐做法)

1. **使用环境变量**
2. **使用 `.env` 文件 (本地开发，已加入 .gitignore)**
3. **使用 GitHub Secrets (CI/CD)**
4. **使用 Ansible Vault (非敏感但需加密的配置)**
5. **定期轮换秘密**
6. **最小权限原则**

### ❌ DON'T (避免的做法)

1. 不要硬编码秘密
2. 不要提交 `.env` 文件
3. 不要在日志中打印秘密
4. 不要使用弱密码

---

## 🔍 常见问题

### Q1: Playbook 运行失败，提示 token is not set？

**原因**: 环境变量未设置或未加载

**解决方案**:
```bash
source .env
ansible-playbook playbooks/provision/site.yml --tags cloudflare_mesh
```

---

### Q2: 如何检查环境变量是否已设置？

```bash
echo $CLOUDFLARE_MESH_TOKEN
```

---

## 🛡️ 安全审计清单

- [ ] `.gitignore` 中包含 `.env`
- [ ] `.gitignore` 中包含 `*.pem`
- [ ] `.gitignore` 中包含 `.vault_password.txt`
- [ ] 所有敏感变量都通过环境变量传递
- [ ] GitHub Secrets 已正确配置
- [ ] 没有在代码中硬编码任何秘密

---

## 🔗 相关文档

- [Cloudflare Mesh 官方文档](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-mesh/)
- [GitHub Actions Secrets 文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Ansible Vault 文档](https://docs.ansible.com/ansible/latest/user_guide/vault.html)
- [AnixOps Quick Start Guide](./QUICKSTART.md)

---

**AnixOps Team**
Last Updated: 2026-04-27