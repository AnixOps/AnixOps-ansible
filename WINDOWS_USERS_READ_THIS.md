# ⚠️ IMPORTANT: Running Ansible on Windows

## The Problem

Ansible **does not officially support Windows as a control node** because it depends on Unix-specific modules (like `fcntl`) that don't exist on Windows.

## The Solution: Windows Subsystem for Linux (WSL)

We provide a helper script that makes it easy to run Ansible through WSL:

### Quick Start (Windows Users)

1. **Check if WSL is available:**
   ```powershell
   .\run-wsl.ps1 check
   ```

2. **Setup Ansible in WSL (one-time):**
   ```powershell
   .\run-wsl.ps1 setup
   ```
   
   This will:
   - Install WSL if needed (requires admin rights and restart)
   - Install Python and Ansible in WSL
   - Set up the virtual environment
   - Install all dependencies

3. **Use Ansible normally:**
   ```powershell
   # Test connectivity
   .\run-wsl.ps1 ping
   
   # Run deployment
   .\run-wsl.ps1 deploy
   
   # Quick setup
   .\run-wsl.ps1 quick-setup
   
   # Open bash shell for manual commands
   .\run-wsl.ps1 shell
   ```

### Why WSL?

✅ **Pros:**
- Full Ansible compatibility
- No workarounds needed
- Edit files with Windows tools (VS Code)
- Fast performance (WSL 2)
- Access Windows files via `/mnt/c/`

❌ **What doesn't work:**
- Native PowerShell Ansible (missing Unix modules)
- Git Bash (limited support, many issues)
- Cygwin (outdated, unreliable)

## Alternative Solutions

See `docs/WINDOWS_ANSIBLE_SOLUTIONS.md` for other options:
- Docker containers
- Remote Linux VM
- Cloud-based control nodes

## Troubleshooting

### "WSL is not installed"
Run as Administrator:
```powershell
wsl --install
```
Then restart your computer.

### "Virtual environment not found"
Run the setup:
```powershell
.\run-wsl.ps1 setup
```

### Need to run manual commands?
Open a WSL shell:
```powershell
.\run-wsl.ps1 shell
```

Then you can run any Ansible command directly:
```bash
ansible all -m ping
ansible-playbook playbooks/site.yml
ansible-vault encrypt inventory/group_vars/all/vault.yml
```

## For Linux/Mac Users

If you're on Linux or macOS, use the original `run.ps1` or Makefile:

```bash
# Linux/Mac
make ping
make deploy

# Or use Python directly
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ansible all -m ping
```

## More Information

- [Full Documentation](docs/WINDOWS_ANSIBLE_SOLUTIONS.md)
- [WSL Installation Guide](https://learn.microsoft.com/en-us/windows/wsl/install)
- [Ansible Windows FAQ](https://docs.ansible.com/ansible/latest/os_guide/windows_faq.html)
