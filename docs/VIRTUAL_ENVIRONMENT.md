# Python 虚拟环境管理指南

## 🎯 为什么使用虚拟环境？

- ✅ **隔离依赖** - 避免污染系统 Python 环境
- ✅ **版本控制** - 每个项目使用独立的包版本
- ✅ **可复现性** - 确保团队成员环境一致
- ✅ **易于清理** - 删除虚拟环境即可完全清理

---

## 🚀 快速开始

### Windows (PowerShell)

```powershell
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -r requirements.txt

# 4. 使用项目
.\run.ps1 help

# 5. 退出虚拟环境
deactivate
```

### Linux/Mac (Bash/Zsh)

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 使用项目
make help

# 5. 退出虚拟环境
deactivate
```

---

## 🔧 详细说明

### 方式 1: 标准 venv（推荐）

#### 创建虚拟环境

```powershell
# Windows
python -m venv venv

# Linux/Mac
python3 -m venv venv
```

这会在项目根目录创建 `venv` 文件夹，包含：
- `Scripts/` (Windows) 或 `bin/` (Linux/Mac) - 可执行文件
- `Lib/` - Python 库
- `Include/` - C 头文件

#### 激活虚拟环境

**Windows PowerShell**:
```powershell
.\venv\Scripts\Activate.ps1
```

如果遇到权限错误，运行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Windows CMD**:
```cmd
venv\Scripts\activate.bat
```

**Linux/Mac**:
```bash
source venv/bin/activate
```

激活后，命令行提示符会显示 `(venv)`。

#### 验证虚拟环境

```powershell
# 查看 Python 路径（应该指向 venv）
Get-Command python | Select-Object Source

# 或
python -c "import sys; print(sys.prefix)"
```

应该显示包含 `venv` 的路径。

#### 安装依赖

```powershell
# 升级 pip
python -m pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 查看已安装的包
pip list
```

---

### 方式 2: Conda（可选）

如果你使用 Anaconda/Miniconda：

```bash
# 创建环境
conda create -n anixops python=3.11

# 激活环境
conda activate anixops

# 安装依赖
pip install -r requirements.txt

# 退出环境
conda deactivate

# 删除环境（如需要）
conda env remove -n anixops
```

**优势**:
- 包含非 Python 依赖（如系统库）
- 更好的包管理
- 跨平台一致性更好

---

### 方式 3: Poetry（现代化）

如果你喜欢现代化的依赖管理：

```bash
# 安装 Poetry
curl -sSL https://install.python-poetry.org | python3 -

# 初始化项目（已有 requirements.txt）
poetry init

# 从 requirements.txt 导入
poetry add $(cat requirements.txt)

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell

# 运行命令
poetry run ansible-playbook playbooks/site.yml
```

---

## 📝 项目配置文件

我已经为您创建了虚拟环境相关的配置：

### 1. `.gitignore` 已包含

```gitignore
# Python virtual environments
venv/
env/
.venv/
.Python
```

### 2. `requirements.txt` 已准备好

包含所有必需依赖：
- ansible
- ansible-lint
- yamllint
- PyNaCl
- requests

---

## 🎨 自动化脚本

### Windows PowerShell 脚本增强版

我为您更新了 `run.ps1`，添加了自动虚拟环境检测和创建功能。

### Linux/Mac Makefile 增强版

我为您创建了 `setup.sh` 脚本来自动处理虚拟环境。

---

## 💡 最佳实践

### 1. 永远在虚拟环境中工作

```powershell
# 创建别名（Windows PowerShell）
# 添加到 $PROFILE
function Start-AnixOps {
    Set-Location "C:\Users\z7299\Documents\GitHub\AnixOps-ansible"
    .\venv\Scripts\Activate.ps1
}
Set-Alias anix Start-AnixOps

# 使用
anix
```

```bash
# 创建别名（Linux/Mac）
# 添加到 ~/.bashrc 或 ~/.zshrc
alias anix='cd ~/projects/AnixOps-ansible && source venv/bin/activate'

# 使用
anix
```

### 2. 使用 `.envrc` (direnv)

安装 direnv 后，创建 `.envrc`:

```bash
# .envrc
layout python python3
```

每次进入项目目录自动激活虚拟环境。

### 3. IDE 配置

**VSCode** - 创建 `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true
}
```

**PyCharm**:
1. File → Settings → Project → Python Interpreter
2. 点击齿轮图标 → Add
3. 选择 "Existing environment"
4. 选择 `venv/bin/python` 或 `venv\Scripts\python.exe`

---

## 🔄 日常工作流

### 启动工作

```powershell
# Windows
cd C:\Users\z7299\Documents\GitHub\AnixOps-ansible
.\venv\Scripts\Activate.ps1

# 确认环境
pip list

# 开始工作
.\run.ps1 ping
```

### 更新依赖

```powershell
# 安装新包
pip install package-name

# 更新 requirements.txt
pip freeze > requirements.txt

# 提交变更
git add requirements.txt
git commit -m "chore: update dependencies"
```

### 共享环境

当其他人克隆项目时：

```powershell
# 1. 克隆项目
git clone https://github.com/AnixOps/AnixOps-ansible.git
cd AnixOps-ansible

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活
.\venv\Scripts\Activate.ps1

# 4. 安装依赖
pip install -r requirements.txt

# 5. 立即开始工作
.\run.ps1 help
```

---

## 🧹 清理和维护

### 完全清理虚拟环境

```powershell
# Windows
deactivate  # 先退出虚拟环境
Remove-Item -Recurse -Force venv

# Linux/Mac
deactivate
rm -rf venv
```

### 重建虚拟环境

```powershell
# 删除旧环境
Remove-Item -Recurse -Force venv

# 创建新环境
python -m venv venv

# 激活
.\venv\Scripts\Activate.ps1

# 重新安装
pip install -r requirements.txt
```

### 升级所有包

```powershell
# 列出过期的包
pip list --outdated

# 升级所有包（谨慎使用！）
pip list --outdated --format=json | ConvertFrom-Json | ForEach-Object { pip install --upgrade $_.name }

# 更新 requirements.txt
pip freeze > requirements.txt
```

---

## 🐛 故障排查

### PowerShell 执行策略错误

```powershell
# 错误: 无法加载文件 Activate.ps1，因为在此系统上禁止运行脚本

# 解决方案
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Python 找不到

```powershell
# 确认 Python 已安装
python --version

# 如果没有，下载安装：
# https://www.python.org/downloads/
# 或使用 winget
winget install Python.Python.3.11
```

### pip 安装失败

```powershell
# 升级 pip
python -m pip install --upgrade pip setuptools wheel

# 使用清华镜像（国内用户）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 虚拟环境激活后 Python 版本不对

```powershell
# 删除并使用指定 Python 版本重建
Remove-Item -Recurse -Force venv
C:\Python311\python.exe -m venv venv
.\venv\Scripts\Activate.ps1
```

---

## 📊 虚拟环境对比

| 工具 | 优点 | 缺点 | 推荐场景 |
|-----|------|------|----------|
| **venv** | 标准库、简单、快速 | 功能基础 | 大多数项目 ✅ |
| **virtualenv** | 更多功能、兼容旧版本 | 需要额外安装 | 遗留项目 |
| **conda** | 管理非 Python 依赖 | 体积大、慢 | 数据科学项目 |
| **poetry** | 现代化、依赖解析好 | 学习曲线 | 新项目 |
| **pipenv** | Pipfile + 虚拟环境 | 性能问题 | 中小型项目 |

---

## ✅ 推荐配置（本项目）

```powershell
# 1. 一次性设置
cd C:\Users\z7299\Documents\GitHub\AnixOps-ansible
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. 每次使用
cd C:\Users\z7299\Documents\GitHub\AnixOps-ansible
.\venv\Scripts\Activate.ps1
.\run.ps1 <command>

# 3. 完成后
deactivate
```

---

## 🎁 额外福利

### 自动激活脚本（Windows）

创建 `activate.ps1`:

```powershell
# 检查虚拟环境是否存在
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# 激活
.\venv\Scripts\Activate.ps1
Write-Host "✓ Virtual environment activated: $(python --version)" -ForegroundColor Green

# 检查依赖
$installed = pip list --format=freeze
if (-not ($installed -match "ansible")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
}
```

使用：
```powershell
.\activate.ps1
```

---

**现在您可以在干净、隔离的环境中工作了！** 🎉
