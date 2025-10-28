> NOTE: This project is Linux-only. All Windows-related notes have been removed.

# Windows 内容已移除

本仓库不再提供 Windows/WSL 支持或兼容性说明。请在 Linux/Mac 上作为控制节点使用 Ansible。

- 控制节点支持：Linux、macOS
- 运行方式：使用 Python venv + Ansible CLI 或 Makefile

相关文档请参阅：`README.md`、`QUICKSTART.md`、`docs/SSH_KEY_MANAGEMENT.md`
#
<!-- Windows legacy content below is intentionally commented out (Linux-only) -->
<!--
# 1. Setup (one-time)
.\run-wsl.ps1 setup

# 2. Use Ansible
.\run-wsl.ps1 ping
.\run-wsl.ps1 deploy

# 3. For manual commands
.\run-wsl.ps1 shell
```

### Why WSL?

✅ **Advantages:**
- Full Ansible compatibility
- No workarounds or patches needed
- Native Linux environment
- Fast performance
- Can still edit files with Windows tools

❌ **Why not native Windows:**
- Missing Unix modules (`fcntl`, etc.)
- Many Ansible modules don't work
- SSH/network handling differs
- Not officially supported

## Alternative Solutions

1. **Docker** - Run Ansible in a container
2. **Remote Linux VM** - Use a Linux server as control node
3. **Cloud-based** - Use AWS/Azure/GCP Linux instance

See `docs/WINDOWS_ANSIBLE_SOLUTIONS.md` for details.

## Testing Results

| Approach | Result |
|----------|--------|
| Native PowerShell | ❌ Fails (missing fcntl module) |
| With patches | ❌ Fails (still missing fcntl) |
| WSL | ✅ Full support |
| Docker | ✅ Full support |
| Git Bash | ⚠️ Partial (many issues) |

## Next Steps

1. **For immediate use:**
   ```powershell
   .\run-wsl.ps1 setup
   .\run-wsl.ps1 ping
   ```

2. **For development:**
   - Install WSL 2
   - Use VS Code with WSL extension
   - Edit files in Windows, run in WSL

3. **For production:**
   - Use a dedicated Linux server
   - Or use WSL for development, Linux for production

## References

- [Ansible Windows FAQ](https://docs.ansible.com/ansible/latest/os_guide/windows_faq.html)
- [WSL Installation](https://learn.microsoft.com/en-us/windows/wsl/install)
- [Project Documentation](docs/WINDOWS_ANSIBLE_SOLUTIONS.md)

## Support

If you encounter issues:

1. Read `WINDOWS_USERS_READ_THIS.md`
2. Check `docs/WINDOWS_ANSIBLE_SOLUTIONS.md`
3. Verify WSL installation: `wsl --version`
4. Open bash shell: `.\run-wsl.ps1 shell`
5. Test Ansible: `ansible --version`

## Summary

**The patch approach cannot fully fix Ansible on Windows.** The recommended solution is to use WSL, which provides:
- Full compatibility
- No modifications needed
- Official support
- Better performance
- Easier maintenance

Use `run-wsl.ps1` for a seamless experience!
