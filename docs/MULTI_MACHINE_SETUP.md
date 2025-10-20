# 多机器操作快速实施指南

## 🎯 您的需求

在多台机器（开发机、服务器、CI/CD）上使用同一个 SSH 私钥来管理 Ansible 部署。

---

## 🏆 推荐方案：1Password + GitHub Secrets（最简单）

### 为什么选这个？

✅ **安全** - 私钥加密存储  
✅ **便捷** - 一次配置，处处使用  
✅ **便宜** - 个人版 $3/月，团队版 $8/月  
✅ **跨平台** - Windows/Mac/Linux 都支持  
✅ **团队协作** - 可以共享给团队成员  

---

## 📋 实施步骤（30 分钟完成）

### 第 1 步：准备 SSH 密钥（如果还没有）

```powershell
# Windows PowerShell
ssh-keygen -t ed25519 -C "ansible@anixops" -f $HOME\.ssh\anixops_ed25519

# 将公钥复制到目标服务器
Get-Content $HOME\.ssh\anixops_ed25519.pub | ssh root@YOUR_SERVER_IP "cat >> ~/.ssh/authorized_keys"
```

### 第 2 步：安装 1Password（可选但推荐）

1. 下载 1Password：https://1password.com/downloads/windows
2. 安装 1Password CLI：
   ```powershell
   # 使用 Scoop（推荐）
   scoop install 1password-cli
   
   # 或下载 .exe 安装包
   # https://1password.com/downloads/command-line/
   ```

3. 登录 1Password：
   ```powershell
   op signin
   ```

### 第 3 步：存储私钥到 1Password

**方法 A：通过 1Password GUI**
1. 打开 1Password 应用
2. 点击 "+" → "SSH Key"
3. 拖拽 `anixops_ed25519` 文件
4. 命名为 "AnixOps Ansible SSH Key"
5. 保存

**方法 B：通过 CLI**
```powershell
# 创建新的 SSH Key 项
op item create `
  --category "SSH Key" `
  --title "AnixOps Ansible SSH Key" `
  --vault "Private" `
  "private key[file]=$HOME\.ssh\anixops_ed25519"
```

### 第 4 步：上传私钥到 GitHub Secrets

使用我们的工具：

```powershell
# Windows PowerShell
python tools/ssh_key_manager.py `
  --key-file $HOME\.ssh\anixops_ed25519 `
  --repo AnixOps/AnixOps-ansible `
  --token YOUR_GITHUB_TOKEN `
  --secret-name SSH_PRIVATE_KEY
```

或交互式：
```powershell
python tools/ssh_key_manager.py
```

### 第 5 步：在不同机器上使用

#### 机器 A（开发机 - Windows）

```powershell
# 从 1Password 获取密钥
op read "op://Private/AnixOps Ansible SSH Key/private key" | `
  Out-File -FilePath $HOME\.ssh\anixops_temp -Encoding ASCII

# 使用 Ansible
ansible-playbook -i inventory/hosts.yml playbooks/site.yml `
  --private-key $HOME\.ssh\anixops_temp

# 使用完毕后删除
Remove-Item $HOME\.ssh\anixops_temp
```

#### 机器 B（开发机 - Linux/Mac）

```bash
# 从 1Password 获取密钥
op read "op://Private/AnixOps Ansible SSH Key/private key" > /tmp/ansible_key
chmod 600 /tmp/ansible_key

# 使用 Ansible
ansible-playbook -i inventory/hosts.yml playbooks/site.yml \
  --private-key /tmp/ansible_key

# 使用完毕后删除
rm /tmp/ansible_key
```

#### 机器 C（GitHub Actions - 自动）

已自动配置！密钥会从 GitHub Secrets 自动注入：

```yaml
# .github/workflows/deploy.yml（已包含）
- name: Setup SSH Key
  run: |
    mkdir -p ~/.ssh
    echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
```

#### 机器 D（跳板机/堡垒机）

```bash
# 一次性从 1Password 获取并永久保存
op read "op://Private/AnixOps Ansible SSH Key/private key" > ~/.ssh/anixops_key
chmod 600 ~/.ssh/anixops_key

# 在 SSH 配置中使用
cat >> ~/.ssh/config << EOF
Host anixops-*
    IdentityFile ~/.ssh/anixops_key
    User root
EOF
```

---

## 🚀 使用 PowerShell 脚本简化操作（Windows）

我为您创建了 `run.ps1` 脚本：

```powershell
# 查看帮助
.\run.ps1 help

# 安装依赖
.\run.ps1 install

# 上传 SSH 密钥
.\run.ps1 upload-key

# 测试连接
.\run.ps1 ping

# 部署
.\run.ps1 deploy

# 健康检查
.\run.ps1 health-check
```

---

## 🔐 进阶方案：HashiCorp Vault（如果需要更强控制）

### 何时使用 Vault？

- ✅ 团队超过 10 人
- ✅ 需要审计每次密钥访问
- ✅ 需要动态生成 SSH 证书
- ✅ 需要自动密钥轮换

### 快速部署

```powershell
# 使用 Docker 部署 Vault
docker run -d --name=vault `
  --cap-add=IPC_LOCK `
  -e VAULT_DEV_ROOT_TOKEN_ID=myroot `
  -p 8200:8200 `
  vault:latest

# 设置环境变量
$env:VAULT_ADDR = "http://localhost:8200"
$env:VAULT_TOKEN = "myroot"

# 存储 SSH 密钥
vault kv put anixops/ssh/ansible `
  private_key=@"$HOME\.ssh\anixops_ed25519"
```

### 创建 Vault 获取脚本

创建 `tools/get_key_from_vault.ps1`:

```powershell
param(
    [string]$VaultAddr = $env:VAULT_ADDR,
    [string]$VaultToken = $env:VAULT_TOKEN,
    [string]$KeyPath = "anixops/ssh/ansible"
)

# 从 Vault 获取密钥
$response = Invoke-RestMethod `
    -Uri "$VaultAddr/v1/$KeyPath" `
    -Headers @{ "X-Vault-Token" = $VaultToken } `
    -Method GET

# 保存到临时文件
$keyFile = "$env:TEMP\ansible_key_$(Get-Random)"
$response.data.data.private_key | Out-File -FilePath $keyFile -Encoding ASCII

# 输出文件路径
Write-Output $keyFile
```

使用：

```powershell
$keyFile = .\tools\get_key_from_vault.ps1
ansible-playbook -i inventory/hosts.yml playbooks/site.yml --private-key $keyFile
Remove-Item $keyFile
```

---

## 📊 方案对比总结

| 方案 | 设置难度 | 日常使用 | 月成本 | 团队规模 |
|-----|---------|---------|-------|---------|
| **1Password** | ⭐ | ⭐⭐⭐⭐⭐ | $3-8 | 1-20人 |
| **GitHub Secrets** | ⭐ | ⭐⭐⭐⭐⭐ | 免费 | 仅 CI/CD |
| **Vault** | ⭐⭐⭐ | ⭐⭐⭐ | 免费 | 10-100+人 |
| **AWS Secrets** | ⭐⭐ | ⭐⭐⭐⭐ | $0.4/月 | AWS 用户 |

---

## ✅ 最终推荐配置

### 方案 A：个人/小团队（1-5人）

```
开发机(Windows):   1Password CLI + run.ps1
开发机(Linux):     1Password CLI
GitHub Actions:    GitHub Secrets (自动)
总成本:           $3/月
```

### 方案 B：中型团队（5-20人）

```
开发机:           1Password Teams（共享 Vault）
CI/CD:            GitHub Secrets
跳板机:           从 1Password 一次性导出
总成本:           $8/人/月
```

### 方案 C：大型团队（20+人）

```
所有机器:         HashiCorp Vault
                 + 动态 SSH 证书
                 + 审计日志
总成本:           自托管免费，或 Vault Enterprise
```

---

## 🎬 立即开始（2 分钟快速配置）

### Windows 用户：

```powershell
# 1. 上传密钥到 GitHub Secrets
python tools/ssh_key_manager.py

# 2. 测试连接
.\run.ps1 ping

# 3. 部署
.\run.ps1 deploy
```

### Linux/Mac 用户：

```bash
# 1. 上传密钥到 GitHub Secrets
python tools/ssh_key_manager.py

# 2. 测试连接
make ping

# 3. 部署
make deploy
```

---

## 📞 需要帮助？

- 查看详细文档：`docs/SSH_KEY_MANAGEMENT.md`
- 查看使用示例：`EXAMPLES.md`
- 提交 Issue：https://github.com/AnixOps/AnixOps-ansible/issues

---

**恭喜！您现在可以在任何机器上安全地使用 SSH 密钥了！** 🎉
