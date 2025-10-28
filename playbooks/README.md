# Playbooks 目录结构说明

## 📁 目录组织

Playbooks 按功能分类到不同的子目录中，便于管理和查找。

```
playbooks/
├── deployment/              # 部署相关的 playbooks
│   ├── local.yml           # 本地环境部署（Kind + Cloudflared）
│   ├── production.yml      # 生产环境部署（K3s + Cloudflared）
│   ├── quick-setup.yml     # 快速部署设置
│   ├── site.yml            # 完整站点部署
│   └── web-servers.yml     # Web 服务器部署
│
├── cloudflared/            # Cloudflared 专用 playbooks
│   ├── k8s-helm.yml       # 使用 Helm 部署到 K8s
│   ├── k8s-local.yml      # 本地 K8s 部署
│   └── standalone.yml      # 独立服务器部署
│
└── maintenance/            # 维护和管理 playbooks
    ├── health-check.yml            # 健康检查
    ├── firewall-setup.yml          # 防火墙配置
    ├── observability.yml           # 可观测性部署
    ├── ssh-config-force-apply.yml  # 强制应用 SSH 配置
    ├── ssh-config-test.yml         # SSH 配置测试
    └── update-observability-labels.yml  # 更新可观测性标签
```

---

## 🚀 主要 Playbooks 说明

### Deployment (部署)

#### `deployment/local.yml`
**用途**: 本地开发环境部署  
**目标**: localhost (Kind 集群)  
**包含**:
- 自动安装 Kind
- 创建本地 K8s 集群
- 部署 Cloudflared

**使用**:
```bash
./scripts/anixops.sh deploy-local -t "your-token"
# 或
ansible-playbook playbooks/deployment/local.yml \
  -i inventories/local/hosts.ini \
  --extra-vars "cloudflare_tunnel_token=your-token"
```

#### `deployment/production.yml`
**用途**: 生产环境部署  
**目标**: 远程服务器  
**包含**:
- 部署 K3s 集群
- 配置生产级 K8s
- 部署 Cloudflared（高可用）

**使用**:
```bash
./scripts/anixops.sh deploy-production --vault-password ~/.vault_pass
# 或
ansible-playbook playbooks/deployment/production.yml \
  -i inventories/production/hosts.ini \
  --extra-vars "@vars/secrets.yml" \
  --vault-password-file ~/.vault_pass
```

#### `deployment/quick-setup.yml`
**用途**: 快速部署基础设施  
**目标**: 所有服务器  
**包含**: 基础配置和常用服务

#### `deployment/site.yml`
**用途**: 完整站点部署  
**目标**: 所有定义的服务器组  
**包含**: 完整的基础设施部署

#### `deployment/web-servers.yml`
**用途**: Web 服务器专用部署  
**目标**: web_servers 组  
**包含**: Nginx、SSL、应用部署

---

### Cloudflared (Cloudflare Tunnel)

#### `cloudflared/k8s-helm.yml`
**用途**: 使用 Helm Chart 部署 Cloudflared  
**目标**: Kubernetes 集群  
**特点**: 
- 使用官方 Helm Chart
- 支持自定义配置
- 易于升级

**使用**:
```bash
ansible-playbook playbooks/cloudflared/k8s-helm.yml \
  --extra-vars "cloudflare_tunnel_token=your-token"
```

#### `cloudflared/k8s-local.yml`
**用途**: 本地 K8s 环境 Cloudflared 部署  
**目标**: 本地 Kind 集群  
**特点**: 开发和测试用

#### `cloudflared/standalone.yml`
**用途**: 独立服务器部署 Cloudflared  
**目标**: 不使用 K8s 的服务器  
**特点**: 
- 直接在主机上运行
- 作为 systemd 服务
- 适合简单场景

---

### Maintenance (维护)

#### `maintenance/health-check.yml`
**用途**: 系统健康检查  
**检查项**:
- 服务器连通性
- 服务运行状态
- 资源使用情况
- K8s 集群健康

**使用**:
```bash
./scripts/anixops.sh status-production
# 或
ansible-playbook playbooks/maintenance/health-check.yml \
  -i inventories/production/hosts.ini
```

#### `maintenance/firewall-setup.yml`
**用途**: 配置防火墙规则  
**功能**:
- 设置 iptables/ufw 规则
- 白名单配置
- 端口管理

#### `maintenance/observability.yml`
**用途**: 部署可观测性栈  
**包含**:
- Prometheus
- Loki
- Grafana
- Node Exporter
- Promtail

#### `maintenance/ssh-config-*.yml`
**用途**: SSH 配置管理  
**功能**:
- 测试 SSH 连接
- 强制应用配置
- 密钥管理

---

## 🏷️ 使用 Tags

大多数 playbooks 支持 tags 来运行特定部分：

```bash
# 只运行 K8s 部署
ansible-playbook playbooks/deployment/local.yml \
  -i inventories/local/hosts.ini \
  --tags "k8s"

# 只运行 Cloudflared 部署
ansible-playbook playbooks/deployment/local.yml \
  -i inventories/local/hosts.ini \
  --tags "cloudflared"

# 跳过验证
ansible-playbook playbooks/deployment/local.yml \
  -i inventories/local/hosts.ini \
  --skip-tags "verification"
```

常用 Tags:
- `k8s` - Kubernetes 相关任务
- `cloudflared` - Cloudflared 相关任务
- `helm` - Helm 相关任务
- `validation` - 验证检查
- `verification` - 部署后验证
- `prerequisites` - 前置条件检查
- `deploy` - 实际部署任务

---

## 📋 快速参考

| 任务 | 命令 |
|------|------|
| 本地部署 | `./scripts/anixops.sh deploy-local -t TOKEN` |
| 生产部署 | `./scripts/anixops.sh deploy-production --vault-password ~/.vault_pass` |
| 健康检查 | `./scripts/anixops.sh status-production` |
| 清理本地 | `./scripts/anixops.sh cleanup-local` |
| 运行特定 playbook | `ansible-playbook playbooks/PATH/TO/playbook.yml -i inventories/ENV/hosts.ini` |

---

## 🔍 选择合适的 Playbook

**我想...**

- ✅ **在本地测试 Cloudflared** → `deployment/local.yml`
- ✅ **部署到生产环境** → `deployment/production.yml`  
- ✅ **只部署 Cloudflared 到现有 K8s** → `cloudflared/k8s-helm.yml`
- ✅ **在非 K8s 服务器运行 Cloudflared** → `cloudflared/standalone.yml`
- ✅ **检查生产环境健康状态** → `maintenance/health-check.yml`
- ✅ **配置可观测性** → `maintenance/observability.yml`
- ✅ **部署 Web 服务器** → `deployment/web-servers.yml`

---

## 💡 提示

1. **新用户**: 从 `deployment/local.yml` 开始，在本地测试
2. **生产部署**: 始终使用 Ansible Vault 保护敏感信息
3. **维护任务**: 定期运行 `maintenance/health-check.yml`
4. **自定义**: 可以复制现有 playbook 创建自己的版本

---

## 🆘 需要帮助？

查看主 README 或运行：
```bash
./scripts/anixops.sh help
```
