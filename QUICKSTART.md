# AnixOps 快速部署指南

## 🎯 5 分钟快速上手

### 步骤 1: 准备 SSH 密钥

在你的本地机器上生成 SSH 密钥对（如果还没有）：

```bash
ssh-keygen -t rsa -b 4096 -C "ansible@anixops.com" -f ~/.ssh/anixops_rsa
```

将公钥复制到目标服务器：

```bash
ssh-copy-id -i ~/.ssh/anixops_rsa.pub root@YOUR_SERVER_IP
```

### 步骤 2: 克隆项目并安装依赖

```bash
# 克隆仓库
git clone https://github.com/AnixOps/AnixOps-ansible.git
cd AnixOps-ansible

# 安装 Python 依赖
pip install -r requirements.txt
```

### 步骤 3: 上传 SSH 密钥到 GitHub Secrets

```bash
python tools/ssh_key_manager.py
```

按照提示输入：
- SSH 私钥路径：`~/.ssh/anixops_rsa`
- GitHub 仓库：`AnixOps/AnixOps-ansible`
- GitHub Token：在 https://github.com/settings/tokens/new 创建（需要 `repo` 权限）
- Secret 名称：`SSH_PRIVATE_KEY`

### 步骤 4: 配置服务器清单

编辑 `inventory/hosts.yml`：

```yaml
all:
  children:
    web_servers:
      hosts:
        web-01:
          ansible_host: "YOUR_SERVER_IP_HERE"
  
  vars:
    ansible_user: root
    ansible_port: 22
    ansible_ssh_private_key_file: ~/.ssh/anixops_rsa
```

### 步骤 5: 测试连接

```bash
ansible all -m ping
```

预期输出：
```
web-01 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### 步骤 6: 执行部署

```bash
# 快速初始化（安装基础配置 + 监控）
ansible-playbook playbooks/quick-setup.yml

# 或完整部署（包括 Nginx）
ansible-playbook playbooks/site.yml
```

### 步骤 7: 验证部署

访问你的服务器查看结果：

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
ansible-playbook playbooks/health-check.yml

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
