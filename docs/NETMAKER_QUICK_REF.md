# Netmaker 部署快速参考 | Netmaker Deployment Quick Reference

## 📋 目录 | Table of Contents

1. [快速开始](#快速开始--quick-start)
2. [配置步骤](#配置步骤--configuration-steps)
3. [命令速查](#命令速查--command-cheat-sheet)
4. [故障排查](#故障排查--troubleshooting)
5. [常用操作](#常用操作--common-operations)

---

## 🚀 快速开始 | Quick Start

### 一键部署 (3 步骤)

```bash
# 1. 配置变量（编辑访问密钥）
vi inventory/group_vars/netmaker_clients.yml

# 2. 加密敏感信息
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 3. 部署到所有客户端
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass
```

---

## ⚙️ 配置步骤 | Configuration Steps

### 步骤 1: 获取 Netmaker 访问密钥

1. 访问 Netmaker UI: `http://<PL-1-IP>:8081`
2. 登录到管理面板
3. 选择网络 (例如: `anixops-mesh`)
4. 导航到 **Access Keys** / **Enrollment Keys**
5. 点击 **Create Access Key**
6. 配置参数:
   - Name: `ansible-deployment-2025`
   - Uses: `0` (无限制) 或设置具体数量
   - Expiration: 设置过期时间
7. 复制生成的密钥

### 步骤 2: 配置变量文件

编辑 `inventory/group_vars/netmaker_clients.yml`:

```yaml
netmaker_server_host: "{{ lookup('env', 'PL_1_V4_SSH') }}"
netmaker_access_key: "YOUR_ACCESS_KEY_HERE"  # 替换为实际密钥
netmaker_network_name: "anixops-mesh"
```

### 步骤 3: 加密敏感信息

```bash
# 方法 1: 加密整个文件
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 方法 2: 只加密访问密钥
ansible-vault encrypt_string 'your-access-key-here' --name 'netmaker_access_key'
# 输出复制到 YAML 文件中

# 方法 3: 交互式加密
ansible-vault encrypt_string --ask-vault-pass --stdin-name 'netmaker_access_key'
# 输入密钥后按 Ctrl+D
```

### 步骤 4: 选择目标主机

在 `inventory/hosts.yml` 中，`netmaker_clients` 组已配置为:
- de-1 (德国)
- jp-1 (日本)
- uk-1 (英国)
- sg-1 (新加坡)

根据需要调整主机列表。

### 步骤 5: 运行部署

```bash
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass
```

---

## 📝 命令速查 | Command Cheat Sheet

### Ansible Playbook 命令

```bash
# 标准部署
ansible-playbook playbooks/netmaker/deploy_netclient.yml

# 使用加密变量
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass

# 使用密码文件
ansible-playbook playbooks/netmaker/deploy_netclient.yml --vault-password-file ~/.vault_pass

# 限制到特定主机
ansible-playbook playbooks/netmaker/deploy_netclient.yml --limit de-1

# 限制到多个主机
ansible-playbook playbooks/netmaker/deploy_netclient.yml --limit "de-1,jp-1"

# 检查模式 (dry-run)
ansible-playbook playbooks/netmaker/deploy_netclient.yml --check

# 详细输出
ansible-playbook playbooks/netmaker/deploy_netclient.yml -v
ansible-playbook playbooks/netmaker/deploy_netclient.yml -vvv  # 更详细

# 仅运行特定 tags
ansible-playbook playbooks/netmaker/deploy_netclient.yml --tags verify
```

### Ansible Vault 命令

```bash
# 加密文件
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 解密文件
ansible-vault decrypt inventory/group_vars/netmaker_clients.yml

# 查看加密文件
ansible-vault view inventory/group_vars/netmaker_clients.yml

# 编辑加密文件
ansible-vault edit inventory/group_vars/netmaker_clients.yml

# 重新设置密码
ansible-vault rekey inventory/group_vars/netmaker_clients.yml

# 加密字符串
ansible-vault encrypt_string 'my-secret-key' --name 'netmaker_access_key'

# 使用密码文件
ansible-vault encrypt --vault-password-file ~/.vault_pass file.yml
```

### Ansible Ad-hoc 命令

```bash
# 检查所有客户端的连接
ansible netmaker_clients -m ping

# 检查 netclient 安装状态
ansible netmaker_clients -m shell -a "which netclient"

# 检查 netclient 版本
ansible netmaker_clients -m shell -a "netclient --version"

# 列出加入的网络
ansible netmaker_clients -m shell -a "netclient list"

# 检查服务状态
ansible netmaker_clients -m systemd -a "name=netclient state=started"

# 查看 WireGuard 接口
ansible netmaker_clients -m shell -a "wg show"

# 重启 netclient 服务
ansible netmaker_clients -m systemd -a "name=netclient state=restarted"
```

### Netclient 命令 (在远程主机上)

```bash
# 列出当前网络
netclient list

# 加入网络
netclient join -s <server> -k <key> -n <network>

# 离开网络
netclient leave -n <network>

# 拉取最新配置
netclient pull

# 显示版本
netclient --version

# 详细模式
netclient list --verbose
```

---

## 🔍 故障排查 | Troubleshooting

### 场景 1: 无法连接到远程主机

```bash
# 测试 SSH 连接
ansible netmaker_clients -m ping

# 使用详细输出
ansible netmaker_clients -m ping -vvv

# 检查 inventory 配置
ansible-inventory --list
ansible-inventory --host de-1
```

**解决方案**:
- 确保环境变量已设置 (`DE_1_V4_SSH` 等)
- 检查 SSH 密钥权限: `chmod 600 ~/.ssh/id_rsa`
- 验证防火墙规则

### 场景 2: netclient 安装失败

```bash
# 检查目标主机的操作系统
ansible netmaker_clients -m setup -a "filter=ansible_distribution*"

# 手动在目标主机上安装
ssh de-1
curl -sfL https://raw.githubusercontent.com/gravitl/netmaker/master/scripts/netclient-install.sh | sh
```

**解决方案**:
- 确保主机有互联网连接
- 检查是否安装了 curl 和 wget
- 验证 WireGuard 内核模块支持

### 场景 3: 无法加入网络

```bash
# 检查服务器连通性
ansible netmaker_clients -m shell -a "ping -c 4 {{ netmaker_server_host }}"

# 测试 gRPC 端口
ansible netmaker_clients -m shell -a "nc -zv {{ netmaker_server_host }} 50051"

# 查看 netclient 日志
ansible netmaker_clients -m shell -a "journalctl -u netclient -n 50"
```

**解决方案**:
- 验证 Access Key 是否有效
- 确认网络名称正确
- 检查 Netmaker 服务器状态
- 验证防火墙规则 (允许 UDP 51821)

### 场景 4: 服务无法启动

```bash
# 检查服务状态
ansible netmaker_clients -m shell -a "systemctl status netclient"

# 查看详细日志
ansible netmaker_clients -m shell -a "journalctl -u netclient -n 100 --no-pager"

# 检查配置文件
ansible netmaker_clients -m shell -a "ls -la /etc/netclient/"
```

**解决方案**:
- 手动重启服务: `systemctl restart netclient`
- 检查配置文件是否损坏
- 验证 WireGuard 接口状态: `wg show`

---

## 🛠️ 常用操作 | Common Operations

### 部署到特定环境

```bash
# 仅部署到开发环境
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  --limit dev_servers \
  -e "netmaker_network_name=dev-mesh"

# 仅部署到生产环境
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  --limit proxy_servers \
  -e "netmaker_network_name=prod-mesh"
```

### 更新已部署的客户端

```bash
# 更新到最新版本
ansible netmaker_clients -m shell -a "netclient update"

# 或强制重新安装
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  -e "force_reinstall=true"
```

### 批量离开网络

```bash
# 离开特定网络
ansible netmaker_clients -m shell -a "netclient leave -n anixops-mesh"

# 验证
ansible netmaker_clients -m shell -a "netclient list"
```

### 批量重启服务

```bash
# 重启所有客户端
ansible netmaker_clients -m systemd -a "name=netclient state=restarted"

# 验证服务状态
ansible netmaker_clients -m systemd -a "name=netclient"
```

### 收集网络状态

```bash
# 收集所有节点信息
ansible netmaker_clients -m shell -a "netclient list" > netmaker_status.txt

# 收集 WireGuard 信息
ansible netmaker_clients -m shell -a "wg show" > wireguard_status.txt
```

### 动态添加新节点

```bash
# 1. 在 hosts.yml 中添加新主机
# 2. 运行 playbook，仅针对新主机
ansible-playbook playbooks/netmaker/deploy_netclient.yml --limit new-host-1
```

---

## 🔐 安全最佳实践

### 密钥管理

```bash
# 创建 vault 密码文件 (仅用于自动化，需妥善保管)
echo 'your-vault-password' > ~/.vault_pass
chmod 600 ~/.vault_pass

# 在 ansible.cfg 中配置
[defaults]
vault_password_file = ~/.vault_pass
```

### 定期轮换访问密钥

```bash
# 1. 在 Netmaker UI 生成新密钥
# 2. 更新变量文件
ansible-vault edit inventory/group_vars/netmaker_clients.yml

# 3. 重新部署 (节点会自动更新配置)
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass
```

### 审计和监控

```bash
# 记录部署历史
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  --ask-vault-pass \
  | tee deployment-$(date +%Y%m%d-%H%M%S).log

# 定期检查节点状态
ansible netmaker_clients -m shell -a "netclient list" \
  > status-$(date +%Y%m%d).txt
```

---

## 📚 相关文档

- **Role 详细文档**: `roles/netmaker_client/README.md`
- **Netmaker 官方文档**: https://docs.netmaker.io/
- **netclient CLI 参考**: https://docs.netmaker.io/netclient.html
- **Ansible 最佳实践**: https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html

---

## 📞 支持

如有问题，请查看:
1. 详细的 Role README: `roles/netmaker_client/README.md`
2. Netmaker 社区: https://discord.gg/zRb9Vfhk8A
3. 项目 Issues: GitHub Issues

---

**最后更新**: 2025-10-29  
**维护者**: AnixOps Team
