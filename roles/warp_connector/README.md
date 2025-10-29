# WARP Connector Ansible Role

这个 Ansible Role 用于在宿主机上部署 Cloudflare WARP Connector，实现服务器间的零信任网络连接。

## 功能特性

- ✅ 支持包安装和 Docker 两种部署方式
- ✅ 自动配置和注册 WARP Connector
- ✅ 系统服务管理
- ✅ 支持多种 Linux 发行版 (Debian/Ubuntu, RHEL/CentOS)

## 使用场景

WARP Connector 直接运行在宿主机上，为整个服务器提供网络连接能力：

1. **跨服务器私有网络**: 连接不同地理位置的服务器
2. **零信任访问**: 通过 Cloudflare Zero Trust 控制访问
3. **服务互联**: 让不同服务器上的应用可以互相访问
4. **统一网络**: 所有容器和应用自动享受 WARP 网络

## 前置要求

### 1. Cloudflare Zero Trust 账号

访问 https://one.dash.cloudflare.com/ 注册账号

### 2. 创建 WARP Connector Token

```bash
# 在 Cloudflare Zero Trust Dashboard 中:
# 1. 进入 Networks > Tunnels
# 2. 创建新的 WARP Connector
# 3. 获取 Token
```

### 3. Ansible 集合依赖

如果使用 Docker 部署方式，需要安装:

```bash
ansible-galaxy collection install community.docker
```

## 快速开始

### 方式 1: 包安装 (推荐)

```yaml
- hosts: servers
  become: yes
  roles:
    - role: warp_connector
      vars:
        warp_token: "YOUR_WARP_TOKEN_HERE"
        warp_install_method: "package"
```

### 方式 2: Docker 安装

```yaml
- hosts: servers
  become: yes
  roles:
    - role: warp_connector
      vars:
        warp_token: "YOUR_WARP_TOKEN_HERE"
        warp_install_method: "docker"
```

## 配置变量

### 必需变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `warp_token` | WARP Connector Token | `eyJh...` |

### 可选变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `warp_install_method` | `package` | 安装方式: `package` 或 `docker` |
| `warp_log_level` | `info` | 日志级别: `debug`, `info`, `warn`, `error` |
| `warp_package_name` | `cloudflare-warp` | 包名称 |
| `warp_service_name` | `warp-svc` | 系统服务名 |
| `warp_config_dir` | `/etc/cloudflare-warp` | 配置目录 |
| `warp_data_dir` | `/var/lib/cloudflare-warp` | 数据目录 |

### Docker 特定变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `warp_docker_image` | `cloudflare/cloudflare-warp-connector:latest` | Docker 镜像 |
| `warp_docker_container_name` | `warp-connector` | 容器名称 |
| `warp_docker_restart_policy` | `unless-stopped` | 重启策略 |

## 完整示例

### 示例 1: 连接多个服务器

```yaml
# playbooks/deploy_warp.yml
---
- name: 部署 WARP Connector 到所有服务器
  hosts: all
  become: yes
  
  vars:
    warp_token: "{{ lookup('env', 'WARP_TOKEN') }}"
    warp_log_level: "debug"
  
  roles:
    - warp_connector
  
  post_tasks:
    - name: 测试连接
      ansible.builtin.ping:
```

运行（使用 ansible.cfg 中配置的默认 inventory）:

```bash
ansible-playbook playbooks/deploy_warp.yml -e "warp_token=YOUR_TOKEN"
```

### 示例 2: 使用 Inventory 变量

```yaml
# inventory/hosts.yml
all:
  children:
    warp_servers:
      hosts:
        de-1:
          ansible_host: "{{ lookup('env', 'DE_1_V4_SSH') }}"
        pl-1:
          ansible_host: "{{ lookup('env', 'PL_1_V4_SSH') }}"
        jp-1:
          ansible_host: "{{ lookup('env', 'JP_1_V4_SSH') }}"
      vars:
        warp_install_method: package
        warp_log_level: info
```

```yaml
# inventory/group_vars/warp_servers.yml
---
warp_token: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          ...encrypted...
```

运行:

```bash
# 使用 ansible.cfg 中配置的默认 inventory
ansible-playbook playbooks/deployment/deploy_warp_host.yml

# 或显式指定 inventory
ansible-playbook playbooks/deployment/deploy_warp_host.yml -i inventory/hosts.yml
```

## 验证部署

### 检查服务状态

```bash
# 包安装方式
systemctl status warp-svc

# Docker 方式
docker ps | grep warp-connector
```

### 检查 WARP 连接

```bash
# 包安装方式
warp-cli status

# 查看日志
journalctl -u warp-svc -f
```

### 测试连通性

```bash
# 从一台服务器 ping 另一台服务器的 WARP IP
ping <other-server-warp-ip>
```

## 管理命令

### 包安装方式

```bash
# 查看状态
warp-cli status

# 连接/断开
warp-cli connect
warp-cli disconnect

# 查看设置
warp-cli settings

# 重启服务
systemctl restart warp-svc
```

### Docker 方式

```bash
# 查看日志
docker logs -f warp-connector

# 重启容器
docker restart warp-connector

# 进入容器
docker exec -it warp-connector sh
```

## 故障排除

### 1. 连接失败

```bash
# 检查 token 是否正确
warp-cli status

# 查看详细日志
journalctl -u warp-svc -n 100
```

### 2. 网络不通

- 检查防火墙规则
- 验证 Cloudflare Zero Trust 策略
- 确认所有服务器都已成功连接

### 3. 服务无法启动

```bash
# 检查系统日志
journalctl -xe

# 重新注册
warp-cli delete
warp-cli register <token>
```

## 与 K8s 部署对比

| 特性 | 宿主机部署 | K8s 部署 |
|------|-----------|----------|
| 复杂度 | ⭐ 简单 | ⭐⭐⭐ 复杂 |
| 资源开销 | ⭐ 低 | ⭐⭐ 中等 |
| 网络覆盖 | ✅ 全机器 | ⚠️ 仅 Pod |
| 管理成本 | ⭐ 低 | ⭐⭐ 高 |
| 稳定性 | ✅ 高 | ⚠️ 依赖 K8s |
| 适用场景 | 服务器互联 | 特定 Pod 互联 |

**结论**: 如果目标是连接服务器（而非特定容器），**宿主机部署是更好的选择**。

## 安全建议

1. 使用 Ansible Vault 加密 token
2. 定期轮换 WARP Connector token
3. 在 Cloudflare Zero Trust 中配置访问策略
4. 监控 WARP 连接状态
5. 启用日志审计

## 相关文档

- [Cloudflare WARP Connector 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-devices/warp/deployment/mdm-deployment/)
- [Zero Trust 架构](../docs/ZERO_TRUST_ARCHITECTURE.md)

## License

MIT
