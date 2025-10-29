# Netmaker Playbooks

## 概述 | Overview

此目录包含用于管理 Netmaker 网络的 Ansible Playbooks。

This directory contains Ansible Playbooks for managing Netmaker networks.

## 文件列表 | File List

### `deploy_netclient.yml`
部署和配置 Netmaker 客户端到目标主机。

Deploy and configure Netmaker client to target hosts.

**功能 | Features:**
- ✅ 自动安装 netclient
- ✅ 加入指定的 Netmaker 网络
- ✅ 配置 systemd 服务
- ✅ 验证部署状态

**使用方法 | Usage:**
```bash
# 标准部署
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass

# 限制到特定主机
ansible-playbook playbooks/netmaker/deploy_netclient.yml --limit de-1

# 检查模式
ansible-playbook playbooks/netmaker/deploy_netclient.yml --check
```

## 快速开始 | Quick Start

### 方法 1: 使用 Playbook 直接部署

```bash
# 1. 配置变量
vi inventory/group_vars/netmaker_clients.yml

# 2. 加密敏感信息
ansible-vault encrypt inventory/group_vars/netmaker_clients.yml

# 3. 运行部署
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass
```

### 方法 2: 使用部署脚本

```bash
# 使用便捷脚本
./scripts/deploy_netmaker_clients.sh

# 或指定选项
./scripts/deploy_netmaker_clients.sh --limit de-1 --verbose
```

## 相关文档 | Related Documentation

- **Role 文档**: `../../roles/netmaker_client/README.md`
- **快速参考**: `../../docs/NETMAKER_QUICK_REF.md`
- **Netmaker 官方文档**: https://docs.netmaker.io/

## 常见任务 | Common Tasks

### 部署到所有客户端
```bash
ansible-playbook playbooks/netmaker/deploy_netclient.yml --ask-vault-pass
```

### 仅验证状态
```bash
ansible-playbook playbooks/netmaker/deploy_netclient.yml --tags verify --ask-vault-pass
```

### 部署到特定环境
```bash
# 开发环境
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  --limit dev_servers \
  -e "netmaker_network_name=dev-mesh" \
  --ask-vault-pass

# 生产环境
ansible-playbook playbooks/netmaker/deploy_netclient.yml \
  --limit proxy_servers \
  -e "netmaker_network_name=prod-mesh" \
  --ask-vault-pass
```

## 故障排查 | Troubleshooting

查看详细的故障排查指南：
- `../../docs/NETMAKER_QUICK_REF.md#故障排查`
- `../../roles/netmaker_client/README.md#故障排查`

## 支持 | Support

如有问题，请参考：
1. 快速参考文档: `docs/NETMAKER_QUICK_REF.md`
2. Role README: `roles/netmaker_client/README.md`
3. Netmaker 官方文档: https://docs.netmaker.io/
