"# AnixOps-ansible

AnixOps 自动化运维 Ansible 项目仓库

## 项目概述

本项目是 AnixOps 团队的自动化运维解决方案，使用 Ansible 进行服务器配置管理和应用部署。项目采用 GitOps 工作流，通过版本控制管理基础设施配置。

## 目录结构

```
AnixOps-ansible/
├── .github/
│   └── workflows/          # GitHub Actions CI/CD 工作流
├── inventory/
│   ├── group_vars/         # 组变量
│   ├── host_vars/          # 主机变量
│   └── hosts.yml          # 主机清单
├── playbooks/             # Ansible Playbook 文件
├── roles/                 # Ansible 角色
├── ansible.cfg           # Ansible 配置文件
├── .gitignore           # Git 忽略文件
└── README.md           # 项目说明文档
```

## 快速开始

### 1. 环境准备

确保您的系统已安装：
- Python 3.8+
- Ansible 2.9+
- Git

### 2. 克隆项目

```bash
git clone git@github.com:AnixOps/AnixOps-ansible.git
cd AnixOps-ansible
```

### 3. 配置主机清单

编辑 `inventory/hosts.yml` 文件，添加您的服务器信息：

```yaml
all:
  children:
    jump_servers:
      hosts:
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
