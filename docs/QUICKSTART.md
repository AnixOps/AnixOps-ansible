# AnixOps 快速部署指南 | AnixOps Quick Deployment Guide

## 🎯 5 分钟快速上手 | 5-Minute Quick Start

### 步骤 1: 配置服务器 IP | Step 1: Configure Server IPs

复制环境变量模板并填入你的服务器 IP：

Copy the environment variable template and fill in your server IPs:

```bash
cd AnixOps-ansible
cp .env.example .env
vim .env  # 填入真实 IP | Fill in real IPs
```

**.env 配置示例 | .env Configuration Example:**

```bash
# 点对点连接 (/31 或 /127 段) - 直接连接
# Point-to-point connection (/31 or /127 segment) - Direct connection
US_W_1_V4=203.0.113.10/31
US_W_1_V6=2001:db8::1/127

# 内网段 - 需要指定SSH连接IP
# Private network - Requires SSH connection IP
JP_1_V4=10.10.0.50/27
JP_1_V6=2001:19f0:5001::1/120
JP_1_SSH_IP=45.76.123.45  # 公网IP用于SSH连接 | Public IP for SSH connection

# SSH 配置 | SSH Configuration
ANSIBLE_USER=root
SSH_KEY_PATH=~/.ssh/id_rsa
```

**说明 | Explanation:**
- **`/31` (IPv4) 或 `/127` (IPv6) 段 | `/31` (IPv4) or `/127` (IPv6) segment**：点对点连接，直接使用该IP | Point-to-point connection, use IP directly
  - 示例 | Example：`203.0.113.10/31` → 直接 SSH 到 | Direct SSH to `203.0.113.10`
- **其他网段 | Other segments**：必须设置 `_SSH_IP` 变量指定SSH连接地址 | Must set `_SSH_IP` variable for SSH connection
  - 示例 | Example：`JP_1_V4=10.10.0.50/27` + `JP_1_SSH_IP=45.76.123.45`
  - SSH 连接到 | SSH to `45.76.123.45`，内网IP用于配置管理 | Private IP for configuration

**网段判断规则 | Subnet Detection Rules:**
- IPv4: `/31` = 点对点 | Point-to-point，其他 | others = 需要 SSH_IP | Requires SSH_IP
- IPv6: `/127` = 点对点 | Point-to-point，其他 | others = 需要 SSH_IP | Requires SSH_IP

### 步骤 2: 准备 SSH 密钥 | Step 2: Prepare SSH Keys

在你的本地机器上生成 SSH 密钥对（如果还没有）：

Generate SSH key pair on your local machine (if you don't have one):

```bash
ssh-keygen -t rsa -b 4096 -C "ansible@anixops.com" -f ~/.ssh/id_rsa
```

将公钥复制到**所有**目标服务器（根据 .env 中配置的 IP）：

Copy the public key to **all** target servers (based on IPs in .env):

```bash
# 示例：复制到美西服务器 | Example: Copy to US West server
ssh-copy-id -i ~/.ssh/id_rsa.pub root@203.0.113.10

# 示例：复制到日本服务器 | Example: Copy to Japan server
ssh-copy-id -i ~/.ssh/id_rsa.pub root@45.76.123.45
```

### 步骤 3: 克隆项目并安装依赖（Linux-only）| Step 3: Clone Project and Install Dependencies (Linux-only)

```bash
# 克隆仓库 | Clone repository
git clone https://github.com/AnixOps/AnixOps-ansible.git
cd AnixOps-ansible

# 使用启动脚本创建虚拟环境并安装依赖
# Use setup script to create virtual environment and install dependencies
./scripts/anixops.sh setup-venv
```

### 步骤 4: 上传 SSH 密钥到 GitHub Secrets（可选，用于 CI/CD）| Step 4: Upload SSH Key to GitHub Secrets (Optional, for CI/CD)

如果需要使用 GitHub Actions 自动部署：

If you need to use GitHub Actions for automated deployment:

```bash
python tools/ssh_key_manager.py
```

按照提示输入：
- SSH 私钥路径：`~/.ssh/id_rsa`
- GitHub 仓库：`YourUsername/AnixOps-ansible`
- GitHub Token：在 https://github.com/settings/tokens/new 创建（需要 `repo` 权限）
- Secret 名称：`SSH_PRIVATE_KEY`

**另外需要在 GitHub Secrets 中添加服务器 IP 变量**（参考 .env.example）

### 步骤 5: 测试连接

```bash
./scripts/anixops.sh ping
```

预期输出：
```
us-w-1 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
jp-1 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### 步骤 6: 执行部署

```bash
# 快速初始化（安装基础配置 + 监控）
./scripts/anixops.sh quick-setup

# 或完整部署（包括 Nginx）
./scripts/anixops.sh deploy
```

### 步骤 7: 验证部署

访问你的服务器查看结果（替换为 .env 中配置的真实 IP）：

```bash
# 查看 Nginx 欢迎页
curl http://YOUR_SERVER_IP

# 查看 Node Exporter 指标
curl http://YOUR_SERVER_IP:9100/metrics

# 查看 Promtail 状态
curl http://YOUR_SERVER_IP:9080/ready
```

---

## 🔧 配置 GitHub Actions 自动部署

### 1. 配置必需的 Secrets

在 GitHub 仓库设置中添加以下 Secrets（Settings → Secrets and variables → Actions）：

- `SSH_PRIVATE_KEY` - 已通过 ssh_key_manager.py 上传
- `ANSIBLE_USER` - 设置为 `root`
- `WEB_01_IP` - 你的服务器 IP 地址
- `PROMETHEUS_URL` - Prometheus 服务器地址（如有）
- `LOKI_URL` - Loki 服务器地址（如有）
- `GRAFANA_URL` - Grafana 服务器地址（如有）

### 2. 启用 GitHub Actions

1. 进入仓库的 "Actions" 标签页
2. 启用 workflows
3. 推送代码到 `main` 分支将自动触发部署

### 3. 手动触发部署

在 Actions 标签页，选择 "Deploy to Production" workflow，点击 "Run workflow"。

---

## 📋 常用命令

### Ansible 命令

```bash
# 查看所有主机
ansible all --list-hosts

# 执行临时命令
ansible all -m shell -a "uptime"

# 检查 playbook 语法
ansible-playbook --syntax-check playbooks/site.yml

# 仅执行特定 role
ansible-playbook playbooks/site.yml --tags nginx

# 限制执行范围
ansible-playbook playbooks/site.yml --limit web_servers

# 检查模式（不实际执行）
ansible-playbook playbooks/site.yml --check
```

### 健康检查

```bash
# 运行健康检查 playbook
./scripts/anixops.sh health-check

# 快速 ping 测试
ansible all -m ping

# 查看系统信息
ansible all -m setup -a "filter=ansible_distribution*"
```

---

## 🐛 故障排查

### SSH 连接失败

```bash
# 测试 SSH 连接
ssh -i ~/.ssh/anixops_rsa root@YOUR_SERVER_IP

# 查看详细日志
ansible all -m ping -vvv
```

### Playbook 执行失败

```bash
# 使用详细模式
ansible-playbook playbooks/site.yml -vvv

# 逐步执行
ansible-playbook playbooks/site.yml --step
```

### 权限问题

确保：
1. SSH 私钥权限：`chmod 600 ~/.ssh/anixops_rsa`
2. 用户有 sudo 权限
3. 防火墙允许 SSH 端口

---

## 📞 获取帮助

- 查看完整文档：项目根目录的运维手册
- 提交 Issue：https://github.com/AnixOps/AnixOps-ansible/issues
- 联系维护者：@kalijerry

---

**祝你部署顺利！🚀**
