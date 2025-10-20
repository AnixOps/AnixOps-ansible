# AnixOps Ansible - PowerShell Helper Script
# Windows version of Makefile alternative

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    
    [Parameter()]
    [switch]$NoVenv  # Skip virtual environment check
)

$ErrorActionPreference = "Stop"

# Set console output encoding to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Fix for Python/Ansible UTF-8 encoding on Windows
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Fix for Ansible on Windows - bypass os.get_blocking() check
$env:ANSIBLE_FORCE_COLOR = "true"
$env:ANSIBLE_NOCOLOR = "false"

# Color output functions
function Write-Success { Write-Host "[OK] $args" -ForegroundColor Green }
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

# 检查并激活虚拟环境
function Ensure-VirtualEnvironment {
    # 如果指定了 -NoVenv，跳过检查
    if ($NoVenv) {
        Write-Warning "Skipping virtual environment check (--NoVenv specified)"
        return
    }
    
    # 检查是否在虚拟环境中
    $inVenv = $env:VIRTUAL_ENV -ne $null
    
    if ($inVenv) {
        Write-Success "Virtual environment active: $env:VIRTUAL_ENV"
        return
    }
    
    # 检查 venv 目录是否存在
    if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
        Write-Warning "Virtual environment not found. Creating..."
        Write-Info "This will take a moment..."
        
        try {
            python -m venv venv
            Write-Success "Virtual environment created at: $(Get-Location)\venv"
        }
        catch {
            Write-Error "Failed to create virtual environment: $_"
            Write-Info "Please run manually: python -m venv venv"
            exit 1
        }
    }
    
    # 激活虚拟环境
    Write-Info "Activating virtual environment..."
    try {
        & ".\venv\Scripts\Activate.ps1"
        Write-Success "Virtual environment activated"
        
        # 检查是否需要安装依赖
        $pipList = pip list --format=freeze 2>$null
        if (-not ($pipList -match "ansible")) {
            Write-Warning "Ansible not found in virtual environment"
            Write-Info "Installing dependencies from requirements.txt..."
            pip install -r requirements.txt
            Write-Success "Dependencies installed"
        }
    }
    catch {
        Write-Warning "Could not activate virtual environment automatically"
        Write-Info "Please activate manually: .\venv\Scripts\Activate.ps1"
        Write-Info "If you get an execution policy error, run:"
        Write-Info "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
    }
}

# Display help
function Show-Help {
    Write-Host @"

+===============================================================+
|         AnixOps Ansible - Available Commands                |
+===============================================================+

Usage: .\run.ps1 <command> [-NoVenv]

Available Commands:

  help              - Show this help message
  install           - Install all dependencies (to virtual environment)
  setup-venv        - Create and configure virtual environment
  lint              - Run code quality checks
  syntax            - Check playbook syntax
  ping              - Test server connectivity
  deploy            - Full deployment
  quick-setup       - Quick initialization
  health-check      - Health check
  deploy-web        - Deploy web servers only
  list-hosts        - Show configured hosts list
  upload-key        - Upload SSH key to GitHub Secrets
  clean             - Clean temporary files
  clean-venv        - Remove virtual environment

Parameters:
  -NoVenv           - Skip virtual environment check (not recommended)

Examples:
  .\run.ps1 setup-venv      # First time: create virtual environment
  .\run.ps1 install         # Install dependencies to virtual environment
  .\run.ps1 ping            # Test connection (auto-uses venv)
  .\run.ps1 deploy          # Deploy (auto-uses venv)

Notes:
  - Script automatically detects and activates virtual environment
  - First run will auto-create virtual environment
  - Virtual environment location: .\venv\

"@ -ForegroundColor Cyan
}

# 安装依赖
function Install-Dependencies {
    Write-Info "Installing Python dependencies to virtual environment..."
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    Write-Success "Dependencies installed to: $env:VIRTUAL_ENV"
}

# 设置虚拟环境
function Setup-VirtualEnvironment {
    if (Test-Path "venv") {
        Write-Warning "Virtual environment already exists"
        $response = Read-Host "Do you want to recreate it? (y/N)"
        if ($response -ne "y") {
            Write-Info "Keeping existing virtual environment"
            return
        }
        Write-Info "Removing existing virtual environment..."
        Remove-Item -Recurse -Force venv
    }
    
    Write-Info "Creating virtual environment..."
    python -m venv venv
    Write-Success "Virtual environment created"
    
    Write-Info "Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
    Write-Success "Virtual environment activated"
    
    Write-Info "Upgrading pip..."
    python -m pip install --upgrade pip
    
    Write-Info "Installing dependencies..."
    pip install -r requirements.txt
    Write-Success "All dependencies installed"
    
    Write-Host ""
    Write-Success "Virtual environment setup complete!"
    Write-Info "Location: $(Get-Location)\venv"
    Write-Info "Python: $(python --version)"
    Write-Info "To activate manually: .\venv\Scripts\Activate.ps1"
}

# 代码检查
function Invoke-Lint {
    Write-Info "Running yamllint..."
    yamllint -c .yamllint.yml .
    
    Write-Info "Running ansible-lint..."
    ansible-lint --force-color playbooks/*.yml roles/*/tasks/*.yml
    
    Write-Success "Lint completed"
}

# 语法检查
function Test-Syntax {
    Write-Info "Checking playbook syntax..."
    
    ansible-playbook --syntax-check playbooks/site.yml
    ansible-playbook --syntax-check playbooks/quick-setup.yml
    ansible-playbook --syntax-check playbooks/health-check.yml
    
    Write-Success "Syntax check passed"
}

# 测试连接
function Test-Ping {
    Write-Info "Testing server connectivity..."
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    ansible all -m ping
    Write-Success "Connectivity test completed"
}

# 完整部署
function Invoke-Deploy {
    Write-Info "Starting full deployment..."
    ansible-playbook -i inventory/hosts.yml playbooks/site.yml
    Write-Success "Deployment completed"
}

# 快速初始化
function Invoke-QuickSetup {
    Write-Info "Starting quick setup..."
    ansible-playbook -i inventory/hosts.yml playbooks/quick-setup.yml
    Write-Success "Quick setup completed"
}

# 健康检查
function Invoke-HealthCheck {
    Write-Info "Running health check..."
    ansible-playbook -i inventory/hosts.yml playbooks/health-check.yml
    Write-Success "Health check completed"
}

# Web 服务器部署
function Invoke-DeployWeb {
    Write-Info "Deploying web servers..."
    ansible-playbook -i inventory/hosts.yml playbooks/web-servers.yml
    Write-Success "Web servers deployed"
}

# 显示主机列表
function Show-Hosts {
    Write-Info "Configured hosts:"
    ansible all --list-hosts
}

# 上传 SSH 密钥
function Invoke-UploadKey {
    Write-Info "Starting SSH key upload wizard..."
    python tools/ssh_key_manager.py
}

# 清理临时文件
function Invoke-Clean {
    Write-Info "Cleaning up..."
    
    Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
    Get-ChildItem -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force
    Get-ChildItem -Recurse -Filter "*.retry" | Remove-Item -Force
    
    if (Test-Path ".cache") {
        Remove-Item -Path ".cache" -Recurse -Force
    }
    
    Write-Success "Cleanup completed"
}

# 清理虚拟环境
function Remove-VirtualEnvironment {
    if (-not (Test-Path "venv")) {
        Write-Warning "No virtual environment found"
        return
    }
    
    Write-Warning "This will delete the virtual environment at: $(Get-Location)\venv"
    $response = Read-Host "Are you sure? (y/N)"
    
    if ($response -eq "y") {
        Write-Info "Removing virtual environment..."
        Remove-Item -Recurse -Force venv
        Write-Success "Virtual environment removed"
        Write-Info "Run '.\run.ps1 setup-venv' to create a new one"
    }
    else {
        Write-Info "Cancelled"
    }
}

# 主逻辑
# 先检查虚拟环境（除了某些命令）
$commandsSkipVenv = @("help", "setup-venv", "clean-venv")
if ($commandsSkipVenv -notcontains $Command.ToLower()) {
    Ensure-VirtualEnvironment
}

switch ($Command.ToLower()) {
    "help" { Show-Help }
    "setup-venv" { Setup-VirtualEnvironment }
    "install" { Install-Dependencies }
    "lint" { Invoke-Lint }
    "syntax" { Test-Syntax }
    "ping" { Test-Ping }
    "deploy" { Invoke-Deploy }
    "quick-setup" { Invoke-QuickSetup }
    "health-check" { Invoke-HealthCheck }
    "deploy-web" { Invoke-DeployWeb }
    "list-hosts" { Show-Hosts }
    "upload-key" { Invoke-UploadKey }
    "clean" { Invoke-Clean }
    "clean-venv" { Remove-VirtualEnvironment }
    default {
        Write-Error "Unknown command: $Command"
        Write-Host ""
        Show-Help
        exit 1
    }
}
