# Netmaker Client Role

## 概述 | Overview

此 Ansible Role 用于在目标主机上自动部署、配置和管理 Netmaker 客户端 (netclient)。它提供了完整的生命周期管理，包括安装、网络加入、服务管理和状态验证。

This Ansible Role is used to automatically deploy, configure, and manage Netmaker client (netclient) on target hosts. It provides complete lifecycle management including installation, network joining, service management, and status verification.

## 核心特性 | Core Features

- ✅ **幂等性设计** | Idempotent design - 可安全地重复运行
- 🐧 **多发行版支持** | Multi-distro support - 支持 Debian/Ubuntu 和 RHEL/CentOS/Rocky
- 🔐 **安全配置** | Secure configuration - 支持 Ansible Vault 加密敏感信息
- 🔄 **自动化管理** | Automated management - 自动检测安装和加入状态
- 📊 **状态验证** | Status verification - 完整的部署验证和报告
- 🛠️ **Systemd 集成** | Systemd integration - 完整的服务生命周期管理

## 前置要求 | Prerequisites

### 控制节点 | Control Node
- Ansible >= 2.9
- Python >= 3.6

### 目标主机 | Target Hosts
- 支持的操作系统 | Supported OS:
  - Ubuntu 18.04+
  - Debian 10+
  - CentOS 7+
  - Rocky Linux 8+
- 内核支持 WireGuard | Kernel with WireGuard support
- Systemd 服务管理器 | Systemd service manager
- 互联网连接（用于下载 netclient）| Internet connection (for downloading netclient)

### Netmaker 服务器 | Netmaker Server
- Netmaker Server v0.17.0+（推荐 v0.20+）
- 已创建目标网络 | Target network already created
- 生成的访问密钥 | Generated access key

## 快速开始 | Quick Start

### 1. 配置 Inventory

在 `inventory/hosts.yml` 中添加 `netmaker_clients` 组：

```yaml
all:
  children:
    netmaker_clients:
      hosts:
        de-1:
          ansible_host: "{{ lookup('env', 'DE_1_V4_SSH') }}"
        jp-1:
          ansible_host: "{{ lookup('env', 'JP_1_V4_SSH') }}"
      vars:
        server_role: netmaker_client
```

### 2. 配置变量

创建或编辑 `inventory/group_vars/netmaker_clients.yml`：

```yaml
# Netmaker 服务器地址
netmaker_server_host: "nm.example.com"

# Netmaker 访问密钥（建议使用 Vault 加密）
netmaker_access_key: "your-access-key-here"

# 目标网络名称
netmaker_network_name: "anixops-mesh"
```

### 3. 加密敏感信息（推荐）

```bash
# 加密整个变量文件
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 或者只加密访问密钥
ansible-vault encrypt_string 'your-access-key-here' --name 'netmaker_access_key'
```

### 4. 运行 Playbook

```bash
# 标准部署
ansible-playbook playbooks/netmaker/deploy_netclient.yml

# 使用 Vault 密码
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass

# 限制到特定主机
ansible-playbook playbooks/netmaker/deploy_netclient.yml --limit de-1

# 检查模式（dry-run）
ansible-playbook playbooks/netmaker/deploy_netclient.yml --check
```

### 5. 验证部署（可选）

```bash
# 运行健康检查
ansible-playbook playbooks/netmaker/deploy_netclient.yml --tags verify
```

## 变量说明 | Variable Reference

### 必需变量 | Required Variables

| 变量名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `netmaker_server_host` | string | Netmaker 服务器地址 | `nm.example.com` |
| `netmaker_access_key` | string | 访问密钥/注册令牌 | `abc123...` |
| `netmaker_network_name` | string | 要加入的网络名称 | `prod-mesh` |

### 可选变量 | Optional Variables

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `netmaker_server_grpc_port` | int | `50051` | gRPC 端口 |
| `netmaker_show_status` | bool | `true` | 是否显示详细状态 |
| `netmaker_install_script_url` | string | 官方脚本 URL | 自定义安装脚本 |
| `netmaker_service_restart_policy` | string | `on-failure` | Systemd 重启策略 |

## 使用场景 | Use Cases

### 场景 1: 基础部署

在开发服务器上部署 netclient：

```bash
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  -e "netmaker_network_name=dev-mesh"
```

### 场景 2: 生产环境部署

使用加密变量部署到生产环境：

```bash
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  --limit production \
  --ask-vault-pass \
  -e "netmaker_network_name=prod-mesh"
```

### 场景 3: 多网络环境

为不同主机组配置不同的网络：

```yaml
# inventory/group_vars/web_servers.yml
netmaker_network_name: "web-mesh"

# inventory/group_vars/db_servers.yml
netmaker_network_name: "db-mesh"
```

### 场景 4: 重新加入网络

如果需要节点离开并重新加入网络：

```bash
# 在目标主机上手动离开
netclient leave -n prod-mesh

# 重新运行 playbook
ansible-playbook playbooks/netmaker/deploy_netclient.yml
```

## 工作原理 | How It Works

### 执行流程 | Execution Flow

1. **前置检查** | Pre-flight checks
   - 验证操作系统兼容性
   - 检查必需变量是否定义
   
2. **安装检测** | Installation detection
   - 检查 netclient 是否已安装
   - 如已安装，显示当前版本
   
3. **安装过程** | Installation process
   - 安装依赖包（curl, wget, wireguard-tools）
   - 下载官方安装脚本
   - 执行安装并验证
   
4. **网络加入检测** | Network join detection
   - 列出当前加入的网络
   - 检查目标网络是否已加入
   - 如已加入，跳过 join 步骤
   
5. **网络加入** | Network joining
   - 使用提供的凭据加入网络
   - 隐藏敏感信息（no_log）
   
6. **服务管理** | Service management
   - 启动 netclient 服务
   - 设置开机自启
   - 验证服务状态
   
7. **最终验证** | Final verification
   - 显示节点信息
   - 显示 WireGuard 接口状态

## 故障排查 | Troubleshooting

### 常见问题 | Common Issues

#### 1. netclient 命令未找到

**症状**: `command not found: netclient`

**解决方案**:
```bash
# 检查安装状态
which netclient
ls -l /usr/sbin/netclient

# 手动重新安装
curl -sfL https://raw.githubusercontent.com/gravitl/netmaker/master/scripts/netclient-install.sh | sh
```

#### 2. 无法加入网络

**症状**: `Failed to join network`

**检查项**:
- Netmaker 服务器是否可访问
- Access Key 是否有效（未过期）
- 网络名称是否正确
- 防火墙规则是否允许 WireGuard（UDP）

```bash
# 测试服务器连接
ping -c 4 <netmaker_server_host>

# 检查端口
nc -zv <netmaker_server_host> 50051

# 手动加入测试
netclient join -s <server> -k <key> -n <network> --verbose
```

#### 3. WireGuard 模块未加载

**症状**: `modprobe: FATAL: Module wireguard not found`

**解决方案**:
```bash
# Ubuntu/Debian
sudo apt-get install wireguard

# RHEL/CentOS
sudo yum install elrepo-release epel-release
sudo yum install kmod-wireguard wireguard-tools
```

#### 4. 服务无法启动

**症状**: `Failed to start netclient.service`

**检查**:
```bash
# 查看服务状态
sudo systemctl status netclient

# 查看日志
sudo journalctl -u netclient -n 50

# 检查配置
sudo netclient list
ls -la /etc/netclient/
```

## 从 Netmaker UI 生成访问密钥 | Generating Access Key from Netmaker UI

1. 登录 Netmaker UI
2. 选择目标网络（例如 `anixops-mesh`）
3. 导航到 **Access Keys** 或 **Enrollment Keys** 页面
4. 点击 **Create Access Key**
5. 设置参数：
   - **Name**: 例如 `ansible-deployment`
   - **Uses**: 使用次数（0 = 无限制）
   - **Expiration**: 过期时间
6. 复制生成的密钥
7. 使用 Ansible Vault 加密存储

## 安全最佳实践 | Security Best Practices

1. **永远不要明文存储访问密钥** | Never store access keys in plaintext
   ```bash
   ansible-vault encrypt_string 'your-key' --name 'netmaker_access_key'
   ```

2. **使用有限使用次数的密钥** | Use limited-use keys
   - 在 Netmaker UI 中创建密钥时设置使用次数限制

3. **定期轮换访问密钥** | Rotate access keys regularly
   - 建议每 90 天更新一次

4. **限制网络访问** | Restrict network access
   - 使用防火墙规则限制哪些主机可以访问 Netmaker 服务器

5. **审计日志** | Audit logs
   - 定期检查 Netmaker 服务器日志
   - 监控异常的加入活动

## 集成示例 | Integration Examples

### 与现有 Playbook 集成

```yaml
# playbooks/deployment/full_stack.yml
---
- name: 完整应用栈部署
  hosts: all
  become: true
  
  roles:
    - role: common              # 基础配置
    - role: netmaker_client     # Netmaker 网络
    - role: nginx               # Web 服务器
    - role: node_exporter       # 监控
```

### 使用 Handler

```yaml
# roles/netmaker_client/handlers/main.yml
---
- name: restart netclient
  ansible.builtin.systemd:
    name: netclient
    state: restarted
```

### 自定义 Tags

```bash
# 仅安装，不加入网络
ansible-playbook playbooks/netmaker/deploy_netclient.yml --tags install

# 仅验证状态
ansible-playbook playbooks/netmaker/deploy_netclient.yml --tags verify
```

## 维护与更新 | Maintenance and Updates

### 更新 netclient

```bash
# 升级到最新版本
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  -e "force_reinstall=true"
```

### 检查节点状态

```bash
# 使用 ad-hoc 命令
ansible netmaker_clients -m shell -a "netclient list"
ansible netmaker_clients -m shell -a "systemctl status netclient"
```

### 离开网络

```bash
ansible netmaker_clients -m shell -a "netclient leave -n anixops-mesh"
```

## 贡献与支持 | Contributing and Support

### 项目仓库 | Repository
- GitHub: AnixOps/AnixOps-ansible

### 相关文档 | Related Documentation
- [Netmaker Official Docs](https://docs.netmaker.io/)
- [netclient CLI Reference](https://docs.netmaker.io/netclient.html)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)

### 报告问题 | Report Issues
如果遇到问题，请提供：
- Ansible 版本: `ansible --version`
- 目标操作系统: `cat /etc/os-release`
- netclient 版本: `netclient --version`
- 错误日志: `journalctl -u netclient -n 100`

## 许可证 | License

MIT License - 请参阅项目根目录的 LICENSE 文件

---

**作者**: AnixOps Team  
**版本**: 1.0.0  
**最后更新**: 2025-10-29
