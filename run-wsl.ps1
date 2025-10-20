# AnixOps Ansible - WSL Helper Script
# This script helps you run Ansible through WSL

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[OK] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

function Test-WSLInstalled {
    try {
        $wslCheck = wsl --status 2>&1
        return $true
    }
    catch {
        return $false
    }
}

function Show-Help {
    Write-Host @"

+===============================================================+
|         AnixOps Ansible - WSL Helper                         |
+===============================================================+

⚠️  Ansible cannot run natively on Windows PowerShell due to
   missing Unix modules (fcntl, etc.).

✅  The recommended solution is to use WSL (Windows Subsystem for Linux)

Usage: .\run-wsl.ps1 <command>

Commands:
  help          - Show this help
  check         - Check if WSL is installed
  setup         - Guide you through WSL setup
  shell         - Open a bash shell in WSL
  ping          - Test server connectivity (via WSL)
  deploy        - Run full deployment (via WSL)
  <any-command> - Run arbitrary Ansible command in WSL

Examples:
  .\run-wsl.ps1 setup
  .\run-wsl.ps1 ping
  .\run-wsl.ps1 deploy
  .\run-wsl.ps1 shell

Documentation:
  See docs\WINDOWS_ANSIBLE_SOLUTIONS.md for detailed information

"@
}

function Show-SetupGuide {
    Write-Host @"

+===============================================================+
|         WSL Setup Guide                                      |
+===============================================================+

"@

    $wslInstalled = Test-WSLInstalled
    
    if (-not $wslInstalled) {
        Write-Warning "WSL is not installed on your system"
        Write-Host ""
        Write-Info "To install WSL, run this command in an Administrator PowerShell:"
        Write-Host "  wsl --install" -ForegroundColor Yellow
        Write-Host ""
        Write-Info "After installation:"
        Write-Host "  1. Restart your computer" -ForegroundColor Gray
        Write-Host "  2. Open 'Ubuntu' from the Start Menu" -ForegroundColor Gray
        Write-Host "  3. Create a username and password when prompted" -ForegroundColor Gray
        Write-Host "  4. Run: .\run-wsl.ps1 setup" -ForegroundColor Gray
        Write-Host ""
        return
    }
    
    Write-Success "WSL is installed!"
    Write-Host ""
    Write-Info "Setting up Ansible in WSL..."
    Write-Host ""
    
    # Get current directory as WSL path
    $currentDir = (Get-Location).Path
    $wslPath = $currentDir -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
    $wslPath = $wslPath.ToLower()
    
    Write-Host "Creating setup script..." -ForegroundColor Gray
    
    $setupScript = @"
#!/bin/bash
set -e

echo "=================================="
echo "AnixOps Ansible - WSL Setup"
echo "=================================="
echo ""

# Update system
echo "[1/6] Updating package lists..."
sudo apt-get update -qq

# Install dependencies
echo "[2/6] Installing Python and dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv sshpass > /dev/null 2>&1

# Navigate to project
echo "[3/6] Navigating to project directory..."
cd "$wslPath"

# Create virtual environment
echo "[4/6] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate and install requirements
echo "[5/6] Installing Ansible and dependencies..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Test installation
echo "[6/6] Testing Ansible installation..."
ansible --version > /dev/null 2>&1

echo ""
echo "=================================="
echo "✓ Setup complete!"
echo "=================================="
echo ""
echo "You can now run Ansible commands:"
echo "  .\run-wsl.ps1 ping"
echo "  .\run-wsl.ps1 deploy"
echo "  .\run-wsl.ps1 shell  # Open bash shell"
echo ""
"@
    
    $tempScript = [System.IO.Path]::GetTempFileName()
    $setupScript | Out-File -FilePath $tempScript -Encoding ASCII
    
    Write-Info "Running setup in WSL..."
    Write-Host ""
    
    wsl bash $tempScript
    
    Remove-Item $tempScript -Force
    
    Write-Host ""
    Write-Success "Setup completed successfully!"
}

function Invoke-WSLCommand {
    param([string]$Cmd)
    
    $wslInstalled = Test-WSLInstalled
    
    if (-not $wslInstalled) {
        Write-Error "WSL is not installed!"
        Write-Info "Run: .\run-wsl.ps1 setup"
        return 1
    }
    
    $currentDir = (Get-Location).Path
    $wslPath = $currentDir -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
    $wslPath = $wslPath.ToLower()
    
    $script = @"
cd "$wslPath"
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
else
    echo "ERROR: Virtual environment not found!"
    echo "Please run: .\run-wsl.ps1 setup"
    exit 1
fi
$Cmd
"@
    
    wsl bash -c $script
}

# Main command dispatcher
switch ($Command.ToLower()) {
    "help" {
        Show-Help
    }
    "check" {
        Write-Info "Checking WSL installation..."
        if (Test-WSLInstalled) {
            Write-Success "WSL is installed and available"
            wsl --version
        }
        else {
            Write-Warning "WSL is not installed"
            Write-Info "Run: .\run-wsl.ps1 setup"
        }
    }
    "setup" {
        Show-SetupGuide
    }
    "shell" {
        Write-Info "Opening bash shell in WSL..."
        Write-Info "Type 'exit' to return to PowerShell"
        Write-Host ""
        
        $currentDir = (Get-Location).Path
        $wslPath = $currentDir -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
        $wslPath = $wslPath.ToLower()
        
        wsl bash -c "cd $wslPath && source venv/bin/activate && exec bash"
    }
    "ping" {
        Write-Info "Testing server connectivity via WSL..."
        Invoke-WSLCommand "ansible all -m ping"
    }
    "deploy" {
        Write-Info "Running full deployment via WSL..."
        Invoke-WSLCommand "ansible-playbook playbooks/site.yml"
    }
    "quick-setup" {
        Write-Info "Running quick setup via WSL..."
        Invoke-WSLCommand "ansible-playbook playbooks/quick-setup.yml"
    }
    "health-check" {
        Write-Info "Running health check via WSL..."
        Invoke-WSLCommand "ansible-playbook playbooks/health-check.yml"
    }
    default {
        Write-Info "Running custom command via WSL..."
        Invoke-WSLCommand $Command
    }
}
