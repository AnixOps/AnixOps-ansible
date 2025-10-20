# Quick Virtual Environment Activation Script
# 快速激活虚拟环境

# 检查虚拟环境是否存在
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create it first:" -ForegroundColor Yellow
    Write-Host "  .\run.ps1 setup-venv" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or manually:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor Cyan
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Cyan
    exit 1
}

# 激活虚拟环境
Write-Host "🔄 Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Fix for Python/Ansible UTF-8 encoding on Windows
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Fix for Ansible on Windows - bypass os.get_blocking() check
$env:ANSIBLE_FORCE_COLOR = "true"
$env:ANSIBLE_NOCOLOR = "false"

# 显示信息
Write-Host "✓ Virtual environment activated!" -ForegroundColor Green
Write-Host ""
Write-Host "Python: $(python --version)" -ForegroundColor Gray
Write-Host "Location: $env:VIRTUAL_ENV" -ForegroundColor Gray
Write-Host ""
Write-Host "Available commands:" -ForegroundColor Yellow
Write-Host "  .\run.ps1 help        - Show all commands" -ForegroundColor Cyan
Write-Host "  .\run.ps1 ping        - Test server connection" -ForegroundColor Cyan
Write-Host "  .\run.ps1 deploy      - Deploy configuration" -ForegroundColor Cyan
Write-Host ""
Write-Host "To deactivate: deactivate" -ForegroundColor Gray
