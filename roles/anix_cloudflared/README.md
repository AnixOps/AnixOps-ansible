# Ansible Role: anix_cloudflared

[![Ansible Lint](https://img.shields.io/badge/Ansible-Lint-brightgreen)](https://github.com/AnixOps/AnixOps-ansible)
[![Security: No Secrets](https://img.shields.io/badge/Security-No_Secrets_Committed-success)](https://github.com/AnixOps/AnixOps-ansible)

## 📋 角色描述

此 Ansible Role 用于在目标主机上部署和管理 **Cloudflare Tunnel (cloudflared)**，实现零信任网络架构。

### 核心功能：
- ✅ 自动安装 `cloudflared` 客户端
- ✅ 配置 Tunnel Token（从环境变量读取，**绝不入库**）
- ✅ 配置系统服务（systemd）
- ✅ 支持自动重启和健康检查

---

## 🔒 安全警告

**此 Role 不包含任何敏感信息！**

你必须通过以下方式提供 `cf_tunnel_token`：

### 本地运行：
```bash
# 创建 .env 文件（已在 .gitignore 中）
echo 'export CF_TUNNEL_TOKEN="your-tunnel-token-here"' > .env

# 加载环境变量
source .env

# 运行 Playbook
ansible-playbook playbooks/cloudflared_playbook.yml
```

### CI/CD (GitHub Actions)：
1. 在仓库的 `Settings -> Secrets -> Actions` 中添加 `CF_TUNNEL_TOKEN`
2. Workflow 会自动读取并传递给 Ansible

---

## 📦 角色变量

### 必需变量（从环境变量读取）：
| 变量名             | 来源                   | 说明                              |
|-------------------|------------------------|-----------------------------------|
| `cf_tunnel_token` | `$CF_TUNNEL_TOKEN`     | Cloudflare Tunnel 的认证 Token     |

### 可选变量（在 `defaults/main.yml` 中定义）：
| 变量名                     | 默认值                     | 说明                     |
|---------------------------|----------------------------|--------------------------|
| `cloudflared_version`     | `latest`                   | cloudflared 安装版本      |
| `cloudflared_user`        | `cloudflared`              | 运行服务的系统用户         |
| `cloudflared_service_name`| `cloudflared`              | systemd 服务名称          |

---

## 📚 使用示例

### Playbook 示例：
```yaml
---
- name: 部署 Cloudflare Tunnel
  hosts: all
  become: yes
  
  vars:
    # 自动从环境变量读取
    cf_tunnel_token: "{{ lookup('env', 'CF_TUNNEL_TOKEN') | default('') }}"
  
  roles:
    - anix_cloudflared
```

---

## 🔧 依赖

- **操作系统**: Ubuntu 20.04+, Debian 10+, CentOS 7+
- **权限**: 需要 `sudo` 或 `root` 权限
- **网络**: 目标主机需要能够访问 Cloudflare 的服务器

---

## ✅ 测试

运行 `ansible-lint` 检查：
```bash
ansible-lint roles/anix_cloudflared/
```

---

## 📖 参考资料

- [Cloudflare Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [AnixOps 秘密管理指南](../../docs/SECRETS_MANAGEMENT.md)

---

## 🙋 维护者

**AnixOps Team**  
如有问题，请在 [GitHub Issues](https://github.com/AnixOps/AnixOps-ansible/issues) 中提交。
