# AnixOps-ansible

<div align="center">

![AnixOps](https://img.shields.io/badge/AnixOps-GitOps-blue?style=for-the-badge)
![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)

**基于 GitOps 理念的全球分布式服务器自动化运维平台**

[快速开始](#-快速开始) • [项目结构](#-项目结构) • [工作流](#-工作流程) • [文档](#-完整文档)

</div>

---

## 📖 项目概述

AnixOps-ansible 是一个完整的 GitOps 基础设施即代码（Infrastructure as Code）解决方案，用于管理全球分布式服务器集群。

### 核心特性

- 🔐 **GitOps 工作流**：所有变更通过 Git 管理，完全可审计
- 🤖 **自动化部署**：GitHub Actions 自动执行配置变更
- 📊 **可观测性**：集成 Prometheus + Loki + Grafana (PLG) 栈
- 🔒 **安全加固**：SSH 密钥管理、防火墙、Fail2Ban
- 🌍 **全球分布式**：支持多区域服务器管理
- 📦 **模块化设计**：可复用的 Ansible Roles

---

## 📁 项目结构

```
AnixOps-ansible/
├── .github/
│   └── workflows/              # CI/CD 工作流
│       ├── lint.yml           # 代码检查
│       └── deploy.yml         # 自动部署
│
├── inventory/
│   ├── hosts.yml              # 主机清单（支持环境变量）
│   └── group_vars/
│       └── all/
│           └── main.yml       # 全局变量配置
│
├── roles/                      # Ansible 角色
│   ├── common/                # 基础配置（安全、时区、用户）
│   ├── nginx/                 # Web 服务器
│   ├── node_exporter/         # Prometheus 监控
│   └── promtail/              # Loki 日志收集
│
├── playbooks/                  # Playbook 文件
│   ├── site.yml              # 完整部署
│   ├── quick-setup.yml       # 快速初始化
│   ├── web-servers.yml       # Web 服务器部署
│   └── health-check.yml      # 健康检查
│
├── observability/              # 可观测性配置
│   ├── prometheus/
│   │   └── rules/            # 告警规则
│   └── grafana/
│       └── dashboards/       # Grafana 仪表盘
│
├── tools/
│   └── ssh_key_manager.py    # SSH 密钥管理工具
│
├── ansible.cfg                # Ansible 配置
├── requirements.txt           # Python 依赖
└── README.md                  # 本文件
```

---

## 🚀 快速开始

### 前置要求

- Python 3.8+
- Ansible 2.15+
- Git
- GitHub 账户（用于 GitHub Actions）

### 1. 克隆项目

```bash
git clone https://github.com/AnixOps/AnixOps-ansible.git
cd AnixOps-ansible
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 SSH 密钥

使用我们提供的工具安全地将 SSH 私钥上传到 GitHub Secrets：

```bash
python tools/ssh_key_manager.py
```

交互式程序会引导你完成以下步骤：
1. 输入本地 SSH 私钥路径（默认：`~/.ssh/id_rsa`）
2. 输入 GitHub 仓库（格式：`owner/repo`）
3. 输入 GitHub Personal Access Token（需要 `repo` 权限）
4. 输入 Secret 名称（默认：`SSH_PRIVATE_KEY`）

**或者使用命令行参数：**

```bash
python tools/ssh_key_manager.py \
  --key-file ~/.ssh/id_rsa \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_your_token_here \
  --secret-name SSH_PRIVATE_KEY
```

### 4. 配置 GitHub Secrets

在 GitHub 仓库设置中配置以下 Secrets：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `SSH_PRIVATE_KEY` | SSH 私钥 | 通过 ssh_key_manager.py 上传 |
| `ANSIBLE_USER` | SSH 用户名 | `root` 或 `ubuntu` |
| `PROMETHEUS_URL` | Prometheus 服务器地址 | `http://prometheus.example.com:9090` |
| `LOKI_URL` | Loki 服务器地址 | `http://loki.example.com:3100` |
| `GRAFANA_URL` | Grafana 服务器地址 | `http://grafana.example.com:3000` |

### 5. 配置服务器清单

编辑 `inventory/hosts.yml`，添加你的服务器信息：

```yaml
all:
  children:
    web_servers:
      hosts:
        web-01:
          ansible_host: "{{ lookup('env', 'WEB_01_IP') | default('192.168.1.10') }}"
```

**提示**：可以使用环境变量或直接在 GitHub Actions 中设置服务器 IP。

### 6. 测试连接

```bash
ansible all -m ping -i inventory/hosts.yml
```

### 7. 执行部署

#### 本地执行

```bash
# 完整部署
ansible-playbook -i inventory/hosts.yml playbooks/site.yml

# 快速初始化
ansible-playbook -i inventory/hosts.yml playbooks/quick-setup.yml

# 健康检查
ansible-playbook -i inventory/hosts.yml playbooks/health-check.yml
```

#### 通过 GitHub Actions

1. 创建一个新分支：`git checkout -b feature/your-change`
2. 修改配置文件
3. 提交并推送：`git commit -am "feat: your change" && git push`
4. 创建 Pull Request
5. 合并到 `main` 分支后自动部署

---

## 🔄 工作流程

### 标准变更流程

```mermaid
graph LR
    A[创建功能分支] --> B[修改代码]
    B --> C[提交 & 推送]
    C --> D[创建 Pull Request]
    D --> E[CI: Lint & 检查]
    E --> F[代码审查]
    F --> G[合并到 main]
    G --> H[CD: 自动部署]
    H --> I[验证 Grafana]
```

### 紧急修复流程

```bash
# 1. 创建 hotfix 分支
git checkout -b hotfix/critical-fix

# 2. 快速修改并提交
git commit -am "hotfix: critical issue"

# 3. 推送并创建 PR
git push origin hotfix/critical-fix

# 4. 快速审核后立即合并
# 5. 在 Grafana 中验证修复
```

---

## 📊 可观测性

### Prometheus 监控

- **主机指标**：CPU、内存、磁盘、网络
- **应用指标**：Nginx 请求、状态码、延迟
- **告警规则**：在 `observability/prometheus/rules/` 中定义

### Loki 日志

- **系统日志**：syslog、auth.log
- **应用日志**：Nginx access.log、error.log
- **关联查询**：与 Prometheus 指标一键关联

### Grafana 仪表盘

- **Node Exporter Dashboard**：主机性能监控
- **Nginx Dashboard**：Web 服务器监控
- **自定义仪表盘**：在 `observability/grafana/dashboards/` 中定义

---

## 🔒 安全最佳实践

1. ✅ **SSH 密钥通过 ssh_key_manager.py 加密上传**
2. ✅ **敏感信息存储在 GitHub Secrets 中**
3. ✅ **所有服务器启用防火墙 + Fail2Ban**
4. ✅ **SSH 禁用密码登录，仅允许密钥认证**
5. ✅ **定期审计 Git 提交历史**
6. ⚠️ **永远不要将私钥或密码提交到 Git**

---

## 📚 完整文档

详细的运维手册请参见项目根目录的完整文档（中英文版本）。

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/amazing-feature`
3. 提交变更：`git commit -m 'feat: Add amazing feature'`
4. 推送到分支：`git push origin feature/amazing-feature`
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 👥 联系方式

- 项目维护者：@kalijerry
- 项目主页：[https://github.com/AnixOps/AnixOps-ansible](https://github.com/AnixOps/AnixOps-ansible)
- 问题反馈：[Issues](https://github.com/AnixOps/AnixOps-ansible/issues)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star！⭐**

Made with ❤️ by AnixOps Team

</div>
        jumphost-01:
          ansible_host: 您的跳板机IP
```

### 4. 测试连接

```bash
# 测试所有主机连接
ansible all -m ping

# 检查 Playbook 语法
ansible-playbook --syntax-check playbooks/site.yml
```

### 5. 运行 Playbook

```bash
# 试运行（不实际执行）
ansible-playbook playbooks/site.yml --check

# 正式运行
ansible-playbook playbooks/site.yml
```

## 主要功能

- 🔧 **服务器初始化**: 自动配置时区、软件包、用户等基础设置
- 🔒 **安全加固**: SSH 配置、防火墙规则、用户权限管理
- 📊 **监控部署**: 自动部署监控代理和配置
- 🚀 **应用部署**: 支持多种应用的自动化部署
- 🔄 **CI/CD 集成**: 通过 GitHub Actions 实现自动化测试和部署

## 开发指南

### 创建新角色

```bash
# 在 roles/ 目录下创建新角色
ansible-galaxy init roles/your-role-name
```

### 使用 Ansible Vault

```bash
# 创建加密变量文件
ansible-vault create inventory/group_vars/all/vault.yml

# 编辑加密文件
ansible-vault edit inventory/group_vars/all/vault.yml
```

### 代码规范

- 所有 YAML 文件使用 2 空格缩进
- 变量名使用下划线命名法
- 添加适当的注释和文档
- 提交前运行 `ansible-lint` 检查

## 贡献指南

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系我们

- 项目主页: https://github.com/AnixOps/AnixOps-ansible
- 问题反馈: https://github.com/AnixOps/AnixOps-ansible/issues" 
