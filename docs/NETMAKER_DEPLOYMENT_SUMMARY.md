# Netmaker 客户端部署 - 项目总结

## 📦 已创建的文件

### 1. Ansible Role: `netmaker_client`

#### `roles/netmaker_client/tasks/main.yml`
**核心任务文件** - 完整的部署逻辑
- ✅ 前置检查（OS 兼容性、必需变量）
- ✅ 安装状态检测（幂等性）
- ✅ 自动安装 netclient
- ✅ 网络加入状态检测
- ✅ 自动加入 Netmaker 网络
- ✅ Systemd 服务管理
- ✅ 最终验证和状态报告

**特点**:
- 完全幂等，可安全重复执行
- 支持 Debian/Ubuntu 和 RHEL/CentOS/Rocky
- 隐藏敏感信息（Access Key）
- 详细的执行日志和状态反馈

#### `roles/netmaker_client/defaults/main.yml`
**默认变量配置**
```yaml
netmaker_server_host: ""           # Netmaker 服务器地址
netmaker_access_key: ""            # 访问密钥（需加密）
netmaker_network_name: ""          # 网络名称
netmaker_show_status: true         # 显示详细状态
```

#### `roles/netmaker_client/README.md`
**详细文档** (300+ 行)
- 完整的使用说明
- 故障排查指南
- 安全最佳实践
- 多场景使用示例
- 常见问题解答

### 2. Playbook: `playbooks/netmaker/deploy_netclient.yml`

**主部署 Playbook**
- Pre-tasks: 显示目标主机信息、更新包缓存
- Roles: 调用 netmaker_client role
- Post-tasks: 收集部署结果、显示摘要
- 可选: 网络健康检查（使用 `--tags verify,never`）

### 3. Inventory 配置

#### `inventory/hosts.yml` (已更新)
添加了 `netmaker_clients` 组：
```yaml
netmaker_clients:
  hosts:
    de-1:  # 德国
    jp-1:  # 日本
    uk-1:  # 英国
    sg-1:  # 新加坡
  vars:
    server_role: netmaker_client
```

#### `inventory/group_vars/netmaker_clients.yml`
**变量配置文件**
```yaml
netmaker_server_host: "{{ lookup('env', 'PL_1_V4_SSH') }}"
netmaker_access_key: "YOUR_ACCESS_KEY_HERE"  # 需替换并加密
netmaker_network_name: "anixops-mesh"
```

#### `inventory/group_vars/netmaker_clients.yml.vault_example`
**Vault 加密示例**
- 展示如何使用 Ansible Vault
- 包含详细的加密步骤说明
- 多环境配置示例

### 4. 文档

#### `docs/NETMAKER_QUICK_REF.md`
**快速参考指南** (400+ 行)
- 📋 快速开始（3 步部署）
- ⚙️ 详细配置步骤
- 📝 命令速查表
  - Ansible Playbook 命令
  - Ansible Vault 命令
  - Ansible Ad-hoc 命令
  - Netclient 命令
- 🔍 故障排查场景
- 🛠️ 常用操作
- 🔐 安全最佳实践

#### `playbooks/netmaker/README.md`
Playbook 目录说明文档

### 5. 部署脚本

#### `scripts/deploy_netmaker_clients.sh`
**交互式部署脚本** (可执行)
```bash
./scripts/deploy_netmaker_clients.sh [options]
```

**功能**:
- ✅ 彩色输出和进度提示
- ✅ 自动检查前置条件
- ✅ 验证 Vault 加密状态
- ✅ 交互式确认
- ✅ 支持多种部署选项
- ✅ 智能路径处理（可从任何目录运行）

**选项**:
- `-e, --env`: 指定环境 (dev/test/prod)
- `-l, --limit`: 限制到特定主机
- `-c, --check`: 检查模式 (dry-run)
- `-v, --verbose`: 详细输出
- `-h, --help`: 显示帮助

---

## 🚀 快速开始指南

### 方法 1: 使用部署脚本（推荐）

```bash
# 1. 配置变量（编辑并填入 Access Key）
vi inventory/group_vars/netmaker_clients.yml

# 2. 加密敏感信息
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 3. 运行部署脚本
./scripts/deploy_netmaker_clients.sh
```

### 方法 2: 直接使用 Playbook

```bash
# 1. 配置变量
vi inventory/group_vars/netmaker_clients.yml

# 2. 加密
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 3. 运行 playbook
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass
```

---

## 📚 核心配置步骤

### 步骤 1: 获取 Netmaker Access Key

1. 访问 Netmaker UI: `http://<PL-1-IP>:8081`
2. 登录管理面板
3. 选择网络（如 `anixops-mesh`）
4. 导航到 **Access Keys** / **Enrollment Keys**
5. 点击 **Create Access Key**
6. 配置并复制生成的密钥

### 步骤 2: 配置变量

编辑 `inventory/group_vars/netmaker_clients.yml`:

```yaml
netmaker_server_host: "{{ lookup('env', 'PL_1_V4_SSH') }}"
netmaker_access_key: "abc123xyz..."  # 你的实际密钥
netmaker_network_name: "anixops-mesh"
```

### 步骤 3: 加密敏感信息

```bash
# 方法 1: 加密整个文件（推荐初次使用）
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 方法 2: 只加密密钥字符串（推荐生产环境）
ansible-vault encrypt_string 'your-key' --name 'netmaker_access_key'
```

### 步骤 4: 部署

```bash
# 使用脚本
./scripts/deploy_netmaker_clients.sh

# 或直接使用 playbook
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass
```

---

## 🎯 使用场景

### 场景 1: 部署到所有客户端
```bash
./scripts/deploy_netmaker_clients.sh
```

### 场景 2: 仅部署到特定主机
```bash
./scripts/deploy_netmaker_clients.sh --limit de-1
```

### 场景 3: 多个主机
```bash
./scripts/deploy_netmaker_clients.sh --limit "de-1,jp-1,sg-1"
```

### 场景 4: 检查模式（不实际执行）
```bash
./scripts/deploy_netmaker_clients.sh --check
```

### 场景 5: 详细输出
```bash
./scripts/deploy_netmaker_clients.sh --verbose
```

### 场景 6: 不同环境
```bash
./scripts/deploy_netmaker_clients.sh --env dev
./scripts/deploy_netmaker_clients.sh --env prod
```

---

## 🔍 验证部署

```bash
# 检查所有客户端连接
ansible netmaker_clients -m ping

# 查看 netclient 版本
ansible netmaker_clients -m shell -a "netclient --version"

# 列出加入的网络
ansible netmaker_clients -m shell -a "netclient list"

# 检查服务状态
ansible netmaker_clients -m shell -a "systemctl status netclient"

# 查看 WireGuard 接口
ansible netmaker_clients -m shell -a "wg show"
```

---

## 📋 文件清单

```
AnixOps-ansible/
├── roles/netmaker_client/
│   ├── tasks/
│   │   └── main.yml                    # ✅ 核心任务
│   ├── defaults/
│   │   └── main.yml                    # ✅ 默认变量
│   └── README.md                       # ✅ 详细文档
│
├── playbooks/netmaker/
│   ├── deploy_netclient.yml            # ✅ 主 Playbook
│   └── README.md                       # ✅ Playbook 文档
│
├── inventory/
│   ├── hosts.yml                       # ✅ 已更新（添加 netmaker_clients 组）
│   └── group_vars/
│       ├── netmaker_clients.yml        # ✅ 变量配置
│       └── netmaker_clients.yml.vault_example  # ✅ Vault 示例
│
├── scripts/
│   └── deploy_netmaker_clients.sh      # ✅ 部署脚本（可执行）
│
└── docs/
    └── NETMAKER_QUICK_REF.md           # ✅ 快速参考
```

---

## 🔐 安全注意事项

1. **永远加密 Access Key**
   ```bash
   ansible-vault encrypt inventory/group_vars/netmaker_clients.yml
   ```

2. **使用有限使用次数的密钥**
   - 在 Netmaker UI 中设置使用次数限制

3. **定期轮换密钥**
   - 建议每 90 天更新

4. **不要提交未加密的配置**
   - 确保 `.gitignore` 包含未加密的变量文件

5. **使用密码文件（可选）**
   ```bash
   echo 'your-vault-password' > ~/.vault_pass
   chmod 600 ~/.vault_pass
   ```

---

## 🛠️ 常用命令

### Ansible Vault
```bash
# 加密文件
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 查看加密文件
ansible-vault view inventory/group_vars/netmaker_clients.yml

# 编辑加密文件
ansible-vault edit inventory/group_vars/netmaker_clients.yml

# 解密文件
ansible-vault decrypt inventory/group_vars/netmaker_clients.yml

# 加密字符串
ansible-vault encrypt_string 'secret' --name 'netmaker_access_key'
```

### Playbook 执行
```bash
# 标准执行
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass

# 限制主机
ansible-playbook playbooks/netmaker/deploy_netclient.yml --limit de-1

# 检查模式
ansible-playbook playbooks/netmaker/deploy_netclient.yml --check

# 详细输出
ansible-playbook playbooks/netmaker/deploy_netclient.yml -vvv
```

### Ad-hoc 命令
```bash
# 检查连接
ansible netmaker_clients -m ping

# 执行命令
ansible netmaker_clients -m shell -a "netclient list"

# 重启服务
ansible netmaker_clients -m systemd -a "name=netclient state=restarted"
```

---

## 📞 获取帮助

- **Role 详细文档**: `roles/netmaker_client/README.md`
- **快速参考**: `docs/NETMAKER_QUICK_REF.md`
- **脚本帮助**: `./scripts/deploy_netmaker_clients.sh --help`
- **Netmaker 官方文档**: https://docs.netmaker.io/

---

## ✅ 核心特性总结

1. **完全幂等** - 可安全重复执行
2. **自动检测** - 智能识别已安装/已加入状态
3. **多发行版支持** - Debian/Ubuntu 和 RHEL/CentOS
4. **安全第一** - 支持 Ansible Vault 加密
5. **详细日志** - 完整的执行反馈
6. **灵活部署** - 支持多种部署选项
7. **易于使用** - 交互式脚本 + 详细文档

---

**创建时间**: 2025-10-29  
**维护者**: AnixOps Team  
**版本**: 1.0.0
