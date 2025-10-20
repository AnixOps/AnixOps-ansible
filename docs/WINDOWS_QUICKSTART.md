# 🚀 Windows 用户快速开始指南

## 第一次使用（一次性设置）

### 步骤 1: 创建虚拟环境

```powershell
# 打开 PowerShell，进入项目目录
cd C:\Users\z7299\Documents\GitHub\AnixOps-ansible

# 自动创建虚拟环境并安装依赖
.\run.ps1 setup-venv
```

这会：
- ✅ 创建 Python 虚拟环境（`venv` 文件夹）
- ✅ 激活虚拟环境
- ✅ 升级 pip
- ✅ 安装所有依赖（Ansible, ansible-lint 等）

### 步骤 2: 配置 SSH 密钥

```powershell
# 上传 SSH 密钥到 GitHub Secrets
.\run.ps1 upload-key
```

按照提示输入您的 SSH 密钥路径和 GitHub 信息。

### 步骤 3: 配置服务器清单

编辑 `inventory\hosts.yml`，添加您的服务器信息。

### 步骤 4: 测试连接

```powershell
.\run.ps1 ping
```

---

## 日常使用

### 方式 A: 使用 run.ps1（推荐，自动管理虚拟环境）

```powershell
cd C:\Users\z7299\Documents\GitHub\AnixOps-ansible

# 所有命令自动使用虚拟环境
.\run.ps1 ping
.\run.ps1 deploy
.\run.ps1 health-check
```

### 方式 B: 手动激活虚拟环境

```powershell
cd C:\Users\z7299\Documents\GitHub\AnixOps-ansible

# 激活虚拟环境
.\activate.ps1
# 或
.\venv\Scripts\Activate.ps1

# 然后使用 Ansible 命令
ansible all -m ping
ansible-playbook playbooks/site.yml

# 完成后退出
deactivate
```

---

## 常用命令

```powershell
# 查看帮助
.\run.ps1 help

# 测试服务器连接
.\run.ps1 ping

# 完整部署
.\run.ps1 deploy

# 快速初始化新服务器
.\run.ps1 quick-setup

# 健康检查
.\run.ps1 health-check

# 仅部署 Web 服务器
.\run.ps1 deploy-web

# 代码检查
.\run.ps1 lint

# 语法检查
.\run.ps1 syntax

# 清理临时文件
.\run.ps1 clean
```

---

## 维护命令

```powershell
# 安装/更新依赖
.\run.ps1 install

# 重建虚拟环境
.\run.ps1 clean-venv
.\run.ps1 setup-venv

# 显示已配置的主机
.\run.ps1 list-hosts
```

---

## 🔧 PowerShell 执行策略问题

如果遇到 "无法加载文件，因为在此系统上禁止运行脚本" 错误：

```powershell
# 以管理员身份运行 PowerShell，执行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 或仅针对当前会话：
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

---

## 📁 文件结构

创建虚拟环境后，项目结构：

```
AnixOps-ansible/
├── venv/                    # Python 虚拟环境（不提交到 Git）
│   ├── Scripts/            # Windows 可执行文件
│   │   ├── python.exe     # 虚拟环境的 Python
│   │   ├── pip.exe        # 虚拟环境的 pip
│   │   └── Activate.ps1   # 激活脚本
│   └── Lib/               # 安装的包
│
├── run.ps1                 # 主要使用这个！
├── activate.ps1            # 快速激活脚本
├── requirements.txt        # 依赖列表
└── ... (其他项目文件)
```

---

## 💡 最佳实践

### 1. 总是使用虚拟环境

```powershell
# ✅ 好
.\run.ps1 deploy

# ⚠️ 不推荐（会污染系统 Python）
python -m pip install ansible
ansible-playbook playbooks/site.yml
```

### 2. 定期更新依赖

```powershell
# 激活虚拟环境
.\activate.ps1

# 查看过期的包
pip list --outdated

# 更新特定包
pip install --upgrade ansible

# 更新 requirements.txt
pip freeze > requirements.txt
```

### 3. 团队协作

当其他人克隆项目时：

```powershell
git clone https://github.com/AnixOps/AnixOps-ansible.git
cd AnixOps-ansible
.\run.ps1 setup-venv  # 一键设置
.\run.ps1 ping        # 立即开始工作
```

---

## 🐛 常见问题

### Q: 如何确认我在虚拟环境中？

A: 
```powershell
# 检查 Python 路径
Get-Command python | Select-Object Source
# 应该显示 ...venv\Scripts\python.exe

# 或检查环境变量
$env:VIRTUAL_ENV
# 应该显示虚拟环境路径
```

### Q: 虚拟环境占用多少空间？

A:
```powershell
Get-ChildItem venv -Recurse | Measure-Object -Property Length -Sum | 
    Select-Object @{Name="Size(MB)";Expression={[math]::Round($_.Sum/1MB,2)}}
```

通常约 50-100 MB。

### Q: 如何完全重置环境？

A:
```powershell
.\run.ps1 clean-venv
.\run.ps1 setup-venv
```

### Q: 能在 VS Code 中使用吗？

A: 可以！VS Code 会自动检测虚拟环境。

1. 打开项目文件夹
2. 按 `Ctrl+Shift+P`
3. 输入 "Python: Select Interpreter"
4. 选择 `.\venv\Scripts\python.exe`

---

## 📊 性能对比

| 操作 | 无虚拟环境 | 有虚拟环境 | 说明 |
|-----|----------|----------|------|
| 首次设置 | 2 分钟 | 3 分钟 | 多花 1 分钟创建环境 |
| 日常使用 | 相同 | 相同 | 性能无差异 |
| 依赖冲突 | 可能 ❌ | 不会 ✅ | 隔离的优势 |
| 清理 | 困难 ❌ | 简单 ✅ | 删除文件夹即可 |

---

## ✅ 推荐工作流

```powershell
# 1. 每天开始工作
cd C:\Users\z7299\Documents\GitHub\AnixOps-ansible
.\activate.ps1

# 2. 查看帮助
.\run.ps1 help

# 3. 执行任务
.\run.ps1 ping
.\run.ps1 deploy

# 4. 完成后（可选）
deactivate
```

---

## 🎓 下一步

- 📖 阅读 [完整虚拟环境指南](docs/VIRTUAL_ENVIRONMENT.md)
- 🔐 查看 [SSH 密钥管理](docs/SSH_KEY_MANAGEMENT.md)
- 💻 学习 [多机器操作](docs/MULTI_MACHINE_SETUP.md)
- 📝 查看 [使用示例](EXAMPLES.md)

---

**现在您可以在干净、隔离的环境中工作了！** 🎉

有问题？运行 `.\run.ps1 help` 查看所有可用命令。
