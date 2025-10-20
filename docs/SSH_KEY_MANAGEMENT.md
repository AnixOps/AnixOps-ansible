# 多机器 SSH 私钥管理方案

## 🔐 问题分析

在多台机器上管理 Ansible SSH 私钥时，需要考虑：

1. **安全性** - 私钥不能明文存储在代码仓库
2. **便捷性** - 多台机器（开发机、CI/CD、跳板机）都需要访问
3. **可管理性** - 统一管理、轮换、撤销
4. **可审计性** - 知道谁在何时使用了私钥

---

## 📋 推荐方案对比

| 方案 | 安全性 | 便捷性 | 成本 | 适用场景 |
|-----|-------|-------|-----|---------|
| **1. GitHub Secrets** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 免费 | GitHub Actions CI/CD |
| **2. HashiCorp Vault** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 免费/付费 | 企业级、大规模 |
| **3. AWS Secrets Manager** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 按使用付费 | AWS 环境 |
| **4. Azure Key Vault** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 按使用付费 | Azure 环境 |
| **5. 1Password/Bitwarden** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 付费 | 小团队、个人 |
| **6. 加密的 Git 仓库** | ⭐⭐⭐ | ⭐⭐⭐ | 免费 | 简单场景 |
| **7. 集中式密钥服务器** | ⭐⭐⭐⭐ | ⭐⭐⭐ | 免费 | 自建方案 |

---

## 🎯 方案详解

### 方案 1: GitHub Secrets + 本地密钥管理器（推荐 🌟）

**适用场景**: 小到中型团队，主要通过 GitHub Actions 部署

#### 架构

```
┌─────────────────┐
│  开发机 A        │
│  (私钥存储在    │──┐
│   1Password)    │  │
└─────────────────┘  │
                     │  ssh_key_manager.py
┌─────────────────┐  │  ↓ 加密上传
│  开发机 B        │──┼─→ GitHub Secrets
│  (私钥存储在    │  │      (加密存储)
│   Bitwarden)    │  │           │
└─────────────────┘  │           │ 自动注入
                     │           ↓
┌─────────────────┐  │  ┌─────────────────┐
│  开发机 C        │──┘  │ GitHub Actions  │
│  (私钥存储在    │     │  (自动部署)     │
│   本地加密)     │     └─────────────────┘
└─────────────────┘
```

#### 实施步骤

**1. 本地开发机使用密钥管理器**

推荐工具：
- **1Password** (推荐) - 支持 SSH 密钥，CLI 可用
- **Bitwarden** - 开源，支持自托管
- **KeePassXC** - 完全离线，开源

```bash
# 使用 1Password 存储 SSH 密钥
op item create --category "SSH Key" \
  --title "AnixOps Ansible Key" \
  --vault "Infrastructure" \
  private_key=@~/.ssh/anixops_rsa

# 从 1Password 读取
op read "op://Infrastructure/AnixOps Ansible Key/private_key" > ~/.ssh/anixops_rsa
chmod 600 ~/.ssh/anixops_rsa
```

**2. GitHub Actions 使用 Secrets**

已在项目中实现：
```yaml
# .github/workflows/deploy.yml
- name: Setup SSH Key
  run: |
    mkdir -p ~/.ssh
    echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
```

**3. 其他机器通过脚本获取**

创建工具从 GitHub Secrets 读取（需要 GitHub Token）。

---

### 方案 2: HashiCorp Vault（企业级 🏢）

**适用场景**: 大型团队，需要动态密钥、审计日志、细粒度权限控制

#### 架构

```
                  ┌─────────────────┐
    所有机器      │  HashiCorp      │
    ┌────────┐    │     Vault       │
    │ 开发机A │────┤  (集中式密钥    │
    │ 开发机B │────┤   管理系统)     │
    │ CI/CD  │────┤                 │
    │跳板机  │────┤  - 动态密钥      │
    └────────┘    │  - 自动轮换      │
                  │  - 审计日志      │
                  │  - 权限控制      │
                  └─────────────────┘
```

#### 实施步骤

**1. 部署 Vault**

```bash
# Docker 快速启动
docker run -d --name=vault \
  --cap-add=IPC_LOCK \
  -e 'VAULT_DEV_ROOT_TOKEN_ID=myroot' \
  -p 8200:8200 \
  vault:latest

export VAULT_ADDR='http://localhost:8200'
export VAULT_TOKEN='myroot'
```

**2. 存储 SSH 私钥**

```bash
# 启用 KV secrets engine
vault secrets enable -path=anixops kv-v2

# 存储私钥
vault kv put anixops/ssh/ansible \
  private_key=@~/.ssh/anixops_rsa \
  public_key=@~/.ssh/anixops_rsa.pub
```

**3. 在 Ansible 中使用**

创建 `vault_fetch_key.py`:

```python
#!/usr/bin/env python3
import hvac
import os

# 连接到 Vault
client = hvac.Client(
    url=os.environ.get('VAULT_ADDR'),
    token=os.environ.get('VAULT_TOKEN')
)

# 读取密钥
secret = client.secrets.kv.v2.read_secret_version(
    path='ssh/ansible',
    mount_point='anixops'
)

private_key = secret['data']['data']['private_key']

# 写入到临时文件
key_path = '/tmp/ansible_key'
with open(key_path, 'w') as f:
    f.write(private_key)
os.chmod(key_path, 0o600)

print(key_path)
```

**4. Ansible 配置**

```yaml
# inventory/hosts.yml
all:
  vars:
    ansible_ssh_private_key_file: "{{ lookup('pipe', 'python3 tools/vault_fetch_key.py') }}"
```

**优势**:
- ✅ 动态生成 SSH 证书（更安全）
- ✅ 自动密钥轮换
- ✅ 完整的审计日志
- ✅ 细粒度权限控制（谁可以读哪个密钥）
- ✅ 支持多种认证方式（LDAP, GitHub, AWS IAM 等）

---

### 方案 3: AWS Secrets Manager（云原生 ☁️）

**适用场景**: 基础设施在 AWS 上

#### 实施步骤

**1. 存储密钥到 AWS Secrets Manager**

```bash
# 使用 AWS CLI
aws secretsmanager create-secret \
    --name anixops/ssh/ansible-key \
    --description "Ansible SSH Private Key" \
    --secret-string file://~/.ssh/anixops_rsa
```

**2. 创建 IAM 策略**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:anixops/ssh/*"
    }
  ]
}
```

**3. 在机器上使用**

```python
#!/usr/bin/env python3
import boto3
import os

def get_ssh_key():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='anixops/ssh/ansible-key')
    
    key_path = '/tmp/ansible_key'
    with open(key_path, 'w') as f:
        f.write(response['SecretString'])
    os.chmod(key_path, 0o600)
    
    return key_path

if __name__ == '__main__':
    print(get_ssh_key())
```

**优势**:
- ✅ 与 AWS 生态集成
- ✅ 自动密钥轮换
- ✅ 跨区域复制
- ✅ 精细的 IAM 权限控制
- ✅ CloudTrail 审计

**成本**: ~$0.40/月/密钥 + API 调用费用

---

### 方案 4: 1Password + SSH Agent（轻量级 💼）

**适用场景**: 小团队，预算有限，重视易用性

#### 实施步骤

**1. 在 1Password 中存储 SSH 密钥**

- 打开 1Password
- 创建新项目 → SSH Key
- 上传私钥文件

**2. 使用 1Password CLI**

```bash
# 安装 1Password CLI
# Windows: scoop install 1password-cli
# Mac: brew install 1password-cli
# Linux: 从官网下载

# 登录
op signin

# 获取 SSH 密钥并使用
op read "op://Private/AnixOps SSH Key/private key" | \
  ansible-playbook -i inventory/hosts.yml playbooks/site.yml \
  --private-key /dev/stdin
```

**3. 团队共享**

- 在 1Password 中创建共享 Vault
- 邀请团队成员
- 设置权限（只读/读写）

**优势**:
- ✅ 极其简单易用
- ✅ 跨平台（Windows/Mac/Linux）
- ✅ 浏览器插件 + CLI
- ✅ 团队共享和权限管理
- ✅ 审计日志

**成本**: ~$3-8/用户/月

---

### 方案 5: Ansible Vault 加密文件（自包含 📦）

**适用场景**: 简单项目，不想依赖外部服务

#### 实施步骤

**1. 加密私钥文件**

```bash
# 创建加密的密钥文件
ansible-vault encrypt ~/.ssh/anixops_rsa \
  --output inventory/group_vars/all/ssh_key_encrypted.yml
```

**2. 在 playbook 中解密并使用**

```yaml
# playbooks/setup_ssh.yml
---
- name: Setup SSH Key
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Read encrypted SSH key
      set_fact:
        ssh_key_content: "{{ lookup('file', 'inventory/group_vars/all/ssh_key_encrypted.yml') }}"
    
    - name: Write SSH key to temp file
      copy:
        content: "{{ ssh_key_content }}"
        dest: "/tmp/ansible_key"
        mode: '0600'
```

**3. 使用时提供密码**

```bash
# 通过文件
echo "vault_password" > .vault_pass
ansible-playbook playbooks/site.yml --vault-password-file .vault_pass

# 或交互式
ansible-playbook playbooks/site.yml --ask-vault-pass
```

**优势**:
- ✅ 完全自包含，无外部依赖
- ✅ 免费
- ✅ 可以提交到 Git（加密后）

**劣势**:
- ⚠️ 需要管理 vault 密码
- ⚠️ 密钥轮换较麻烦

---

### 方案 6: 自建密钥服务器（完全自主 🛠️）

**适用场景**: 对安全有极高要求，需要完全控制

#### 简单实现

创建 `tools/key_server.py`:

```python
#!/usr/bin/env python3
"""
简单的 SSH 密钥分发服务器
使用 JWT 认证，审计所有访问
"""

from flask import Flask, request, jsonify
from functools import wraps
import jwt
import datetime
import os

app = Flask(__name__)
SECRET_KEY = os.environ.get('JWT_SECRET_KEY')

# 存储的密钥（实际应该用数据库）
KEYS = {
    'ansible': open('/secure/keys/ansible_rsa').read()
}

# 审计日志
AUDIT_LOG = []

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            username = payload['username']
            
            # 记录审计日志
            AUDIT_LOG.append({
                'timestamp': datetime.datetime.now().isoformat(),
                'user': username,
                'key': request.view_args.get('key_name'),
                'ip': request.remote_addr
            })
            
            return f(*args, username=username, **kwargs)
        except:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated

@app.route('/keys/<key_name>', methods=['GET'])
@require_auth
def get_key(key_name, username):
    """获取指定的 SSH 密钥"""
    if key_name in KEYS:
        return jsonify({'key': KEYS[key_name]})
    return jsonify({'error': 'Key not found'}), 404

@app.route('/audit', methods=['GET'])
@require_auth
def get_audit(username):
    """查看审计日志（仅管理员）"""
    return jsonify(AUDIT_LOG)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, ssl_context='adhoc')
```

**客户端使用**:

```python
import requests
import os

def get_ssh_key(key_name, token):
    response = requests.get(
        f'https://keyserver.example.com/keys/{key_name}',
        headers={'Authorization': f'Bearer {token}'},
        verify=True
    )
    
    if response.ok:
        key_content = response.json()['key']
        key_path = '/tmp/ansible_key'
        with open(key_path, 'w') as f:
            f.write(key_content)
        os.chmod(key_path, 0o600)
        return key_path
    else:
        raise Exception(f"Failed to fetch key: {response.text}")
```

---

## 🏆 最佳实践推荐

### 小团队（1-5人）

```
开发机: 1Password + 本地存储
CI/CD:  GitHub Secrets
成本:   $3-5/月/人
```

### 中型团队（5-20人）

```
开发机: 1Password Teams / HashiCorp Vault
CI/CD:  GitHub Secrets / Vault
成本:   $8-20/月/人
```

### 大型企业（20+人）

```
所有:   HashiCorp Vault Enterprise
        或 AWS Secrets Manager
成本:   根据使用量
```

---

## 📝 实施建议

### 立即可用方案（本项目）

1. **开发机**: 使用 `ssh_key_manager.py` 上传到 GitHub Secrets
2. **GitHub Actions**: 自动从 Secrets 注入
3. **其他机器**: 临时使用，从 1Password/Bitwarden 获取

### 迁移到 Vault（可选）

当团队规模扩大后：
```bash
# 1. 部署 Vault
docker-compose up -d vault

# 2. 迁移密钥
vault kv put anixops/ssh/ansible private_key=@~/.ssh/anixops_rsa

# 3. 更新 Ansible 配置使用 Vault
# 4. 删除 GitHub Secrets 中的密钥
```

---

## ✅ 安全检查清单

- [ ] 私钥权限设置为 600
- [ ] 从不将私钥提交到 Git
- [ ] 使用强密码保护密钥管理工具
- [ ] 启用双因素认证（2FA）
- [ ] 定期轮换 SSH 密钥（建议每 90 天）
- [ ] 审计密钥访问日志
- [ ] 设置密钥过期时间
- [ ] 使用 SSH 证书替代长期密钥（更安全）

---

**推荐阅读**:
- [HashiCorp Vault 官方文档](https://www.vaultproject.io/docs)
- [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)
- [1Password for Teams](https://1password.com/teams/)
- [SSH Certificate Authentication](https://www.vaultproject.io/docs/secrets/ssh/signed-ssh-certificates)
