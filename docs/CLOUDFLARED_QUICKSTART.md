# 🚀 Cloudflare Tunnel 快速部署指南

[![Ansible Lint](https://img.shields.io/badge/Ansible-Lint_Passed-brightgreen)](https://github.com/AnixOps/AnixOps-ansible)
[![Security](https://img.shields.io/badge/Security-No_Secrets-success)](https://github.com/AnixOps/AnixOps-ansible)

---

## ⚡ 快速开始 (60 秒)

### 本地部署

```bash
# 1. 设置环境变量
echo 'export CF_TUNNEL_TOKEN="your-cloudflare-tunnel-token"' > .env
source .env

# 2. 验证
echo $CF_TUNNEL_TOKEN

# 3. 部署
ansible-playbook playbooks/cloudflared_playbook.yml

# 4. 验证部署
ansible all -m shell -a 'systemctl status cloudflared'
```

### CI/CD 部署 (GitHub Actions)

1. **添加 Secret**: `Settings` → `Secrets` → `Actions` → `New secret`
   - Name: `CF_TUNNEL_TOKEN`
   - Value: `your-token`

2. **运行 Workflow**: `Actions` → `Deploy Cloudflare Tunnel` → `Run workflow`

---

## 📁 项目结构

```
AnixOps-ansible/
├── playbooks/
│   └── cloudflared_playbook.yml          # 主 Playbook
│
├── roles/
│   └── anix_cloudflared/                 # Cloudflare Tunnel Role
│       ├── README.md                     # Role 文档
│       ├── defaults/main.yml             # 默认变量
│       ├── handlers/main.yml             # 服务重启 Handler
│       ├── tasks/main.yml                # 部署任务
│       └── templates/
│           └── cloudflared.service.j2    # Systemd 服务模板
│
├── .github/workflows/
│   └── deploy-cloudflared.yml            # GitHub Actions Workflow
│
├── docs/
│   ├── SECRETS_MANAGEMENT.md             # 秘密管理完整指南
│   └── CLOUDFLARED_QUICKSTART.md         # 本文档
│
└── .env.example                          # 环境变量模板
```

---

## 🔐 安全原则

### ✅ DO (正确做法)

```bash
# 本地：使用环境变量
export CF_TUNNEL_TOKEN="your-token"

# CI/CD：使用 GitHub Secrets
env:
  CF_TUNNEL_TOKEN: ${{ secrets.CF_TUNNEL_TOKEN }}
```

### ❌ DON'T (错误做法)

```yaml
# ❌ 永远不要硬编码！
vars:
  cf_tunnel_token: "eyJhIjoiY2FmZS0xMjM0..."  # 错误！
```

---

## 📖 常用命令

### 部署相关

```bash
# 部署到所有节点
ansible-playbook playbooks/cloudflared_playbook.yml

# 部署到特定主机
ansible-playbook playbooks/cloudflared_playbook.yml --limit "web-servers"

# Dry Run 模式
ansible-playbook playbooks/cloudflared_playbook.yml --check --diff

# 详细输出
ansible-playbook playbooks/cloudflared_playbook.yml -vvv
```

### 验证相关

```bash
# 检查服务状态
ansible all -m shell -a 'systemctl status cloudflared'

# 查看日志
ansible all -m shell -a 'journalctl -u cloudflared -n 50'

# 验证 Token (只显示前 10 个字符)
echo $CF_TUNNEL_TOKEN | cut -c1-10
```

### 代码质量检查

```bash
# Lint Role
ansible-lint roles/anix_cloudflared/

# Lint Playbook
ansible-lint playbooks/cloudflared_playbook.yml

# Lint 所有文件
ansible-lint .
```

---

## 🔧 变量说明

| 变量名                                    | 默认值                    | 说明                     |
|------------------------------------------|---------------------------|--------------------------|
| `cf_tunnel_token`                        | (从环境变量读取)           | Cloudflare Tunnel Token   |
| `anix_cloudflared_version`               | `latest`                  | cloudflared 版本          |
| `anix_cloudflared_service_name`          | `cloudflared`             | Systemd 服务名称          |
| `anix_cloudflared_user`                  | `cloudflared`             | 运行服务的系统用户         |
| `anix_cloudflared_binary_path`           | `/usr/local/bin/cloudflared` | 二进制文件路径         |
| `anix_cloudflared_config_dir`            | `/etc/cloudflared`        | 配置文件目录              |
| `anix_cloudflared_log_dir`               | `/var/log/cloudflared`    | 日志目录                  |
| `anix_cloudflared_health_check_enabled`  | `true`                    | 启用健康检查              |

---

## 🐛 故障排查

### 问题 1: "cf_tunnel_token is not set"

**原因**: 环境变量未设置

**解决**:
```bash
# 检查环境变量
echo $CF_TUNNEL_TOKEN

# 如果为空，重新加载
source .env

# 验证
echo $CF_TUNNEL_TOKEN
```

---

### 问题 2: 服务启动失败

**原因**: Token 无效或网络问题

**解决**:
```bash
# 1. 检查服务状态
ansible all -m shell -a 'systemctl status cloudflared'

# 2. 查看详细日志
ansible all -m shell -a 'journalctl -u cloudflared -n 100'

# 3. 验证 Token 在 Cloudflare Dashboard 中是否有效
# https://one.dash.cloudflare.com/
```

---

### 问题 3: Ansible Lint 失败

**原因**: 代码格式不符合规范

**解决**:
```bash
# 运行 Lint 并查看详细错误
ansible-lint roles/anix_cloudflared/ -v

# 修复后重新运行
ansible-lint roles/anix_cloudflared/
```

---

## 📚 相关文档

- [完整秘密管理指南](./SECRETS_MANAGEMENT.md)
- [Role 详细文档](../roles/anix_cloudflared/README.md)
- [GitHub Actions Workflow](../.github/workflows/deploy-cloudflared.yml)
- [Cloudflare Tunnel 官方文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)

---

## 🎯 下一步

1. **配置 Tunnel 路由**: 在 Cloudflare Dashboard 中配置路由规则
2. **设置访问策略**: 配置 Zero Trust 访问策略
3. **监控部署**: 集成 Prometheus 和 Grafana
4. **定期轮换 Token**: 建议每 90 天轮换一次

---

## 🙋 获取帮助

- **GitHub Issues**: https://github.com/AnixOps/AnixOps-ansible/issues
- **文档**: https://github.com/AnixOps/AnixOps-ansible/docs

---

**AnixOps Team**  
Last Updated: 2025-10-27
