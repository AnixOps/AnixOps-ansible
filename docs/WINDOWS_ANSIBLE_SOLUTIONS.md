# Windows 内容已移除（Linux-only）

本页面已下线。项目仅支持在 Linux/Mac 上作为控制节点运行 Ansible。
<!-- Windows legacy content below is intentionally commented out (Linux-only) -->
<!--

请参考以下文档开始使用：

- README.md / QUICKSTART.md（快速开始）
- docs/SSH_KEY_MANAGEMENT.md（多机密钥管理）

如需在 Windows 机器上开发，请使用远程 Linux 主机或容器作为控制节点。
- ✅ No compatibility issues
- ✅ Native Linux environment
- ✅ Can still edit files with Windows tools (VS Code)
- ✅ Direct access to Windows filesystem via `/mnt/`

### Solution 2: Docker Container

Run Ansible in a Docker container on Windows.

#### Setup:

1. **Install Docker Desktop for Windows**

2. **Create a Dockerfile:**
   ```dockerfile
   FROM python:3.11-slim
   
   WORKDIR /ansible
   
   RUN apt-get update && \
       apt-get install -y openssh-client sshpass git && \
       rm -rf /var/lib/apt/lists/*
   
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY . .
   
   CMD ["/bin/bash"]
   ```

3. **Build and run:**
   ```powershell
   docker build -t anixops-ansible .
   docker run -it -v ${PWD}:/ansible anixops-ansible
   ```

4. **Run Ansible inside container:**
   ```bash
   ansible all -m ping
   ```

### Solution 3: Remote Linux VM or Server

Use a remote Linux machine as your Ansible control node:

1. Set up a Linux VM (VirtualBox, VMware, or cloud provider)
2. Install Ansible on the Linux VM
3. Clone your repository to the Linux VM
4. Run Ansible from there
5. Use VS Code Remote-SSH to edit files

### Solution 4: Git Bash / Cygwin (Limited Support)

⚠️ **Not Recommended** - Very limited and unreliable

Some users report partial success with:
- Git Bash with Python
- Cygwin with Python packages

However, these approaches are:
- Unreliable
- Have many compatibility issues
- Not officially supported
- Will still fail with many Ansible modules

## What We've Fixed (For Reference)

In case you need to troubleshoot or help others, we've created a patch script at `tools/patch_ansible_windows.py` that fixes:

1. **os.get_blocking() error** - Wrapped in try/except to skip on Windows
2. **Locale encoding error** - Force UTF-8 encoding on Windows

However, this is insufficient due to the `fcntl` module dependency.

## Next Steps - Choose Your Path

### For Development/Testing (Recommended):

```powershell
# Install WSL
wsl --install

# After restart, open Ubuntu and:
cd /mnt/c/Users/z7299/Documents/GitHub/AnixOps-ansible
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Now use Ansible normally
ansible all -m ping
```

### For Quick Testing (Docker):

```powershell
# Create and use the helper script
.\tools\run-in-docker.ps1 ping
.\tools\run-in-docker.ps1 deploy
```

## FAQ

**Q: Can I use Ansible natively on Windows PowerShell?**
A: No, Ansible requires Unix-specific modules and is not designed to run as a control node on Windows.

**Q: What about ansible-core vs ansible?**
A: Both have the same limitation - they require Unix-specific modules.

**Q: Can Windows be an Ansible managed node?**
A: Yes! Windows can be managed BY Ansible (running on Linux), but cannot RUN Ansible as a control node.

**Q: Is WSL slower than native Windows?**
A: WSL 2 performance is excellent and nearly native. For Ansible operations over SSH, the difference is negligible.

## Resources

- [Official Ansible Documentation - Windows Support](https://docs.ansible.com/ansible/latest/os_guide/windows_faq.html)
- [WSL Installation Guide](https://learn.microsoft.com/en-us/windows/wsl/install)
- [Ansible in Docker](https://www.ansible.com/blog/ansible-using-docker)

## Getting Help

If you're still having issues:

1. Check that you're using WSL or Docker (not native Windows)
2. Verify your Python version: `python --version` (should be 3.8+)
3. Verify Ansible installation: `ansible --version`
4. Check the project's GitHub issues
5. Join the Ansible community on [Matrix/IRC](https://docs.ansible.com/ansible/latest/community/communication.html)
