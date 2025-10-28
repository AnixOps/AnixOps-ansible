# 项目结构总览

```
AnixOps-ansible/
│
├── README.md                    # 主文档（你现在看到的）
├── CHANGELOG.md                 # 变更日志
├── ansible.cfg                  # Ansible 全局配置
├── Makefile                     # 快捷命令
├── requirements.txt             # Python 依赖
│
├── scripts/                     # 🔧 所有脚本文件
│   ├── anixops.sh              # 统一管理脚本（主入口）★
│   ├── cleanup_cloudflared.sh  # Cloudflared 清理
│   └── quick_deploy_cloudflared.sh  # 快速部署
│
├── playbooks/                   # 📚 Ansible Playbooks（分类组织）
│   ├── README.md               # Playbooks 详细说明
│   ├── deployment/             # 部署相关
│   │   ├── local.yml          # 本地部署（Kind）★
│   │   ├── production.yml      # 生产部署（K3s）★
│   │   ├── quick-setup.yml
│   │   ├── site.yml
│   │   └── web-servers.yml
│   ├── cloudflared/           # Cloudflared 专用
│   │   ├── k8s-helm.yml
│   │   ├── k8s-local.yml
│   │   └── standalone.yml
│   └── maintenance/           # 维护管理
│       ├── health-check.yml
│       ├── firewall-setup.yml
│       ├── observability.yml
│       └── ssh-config-*.yml
│
├── inventories/                # 🗂️ 环境配置（环境隔离）
│   ├── local/                 # 本地开发环境
│   │   ├── hosts.ini          # Kind 集群配置
│   │   └── group_vars/
│   │       └── all.yml
│   └── production/            # 生产环境
│       ├── hosts.ini          # 远程服务器配置
│       └── group_vars/
│           └── all.yml
│
├── roles/                      # 🎭 Ansible Roles（模块化）
│   ├── k8s_provision/         # K8s 集群部署（Kind/K3s）★
│   │   ├── README.md
│   │   ├── defaults/
│   │   ├── tasks/
│   │   │   ├── main.yml
│   │   │   ├── prerequisites.yml
│   │   │   ├── provision_kind.yml
│   │   │   ├── provision_k3s.yml
│   │   │   └── verify.yml
│   │   └── meta/
│   ├── cloudflared_deploy/    # Cloudflared 部署★
│   │   ├── README.md
│   │   ├── defaults/
│   │   ├── tasks/
│   │   │   ├── main.yml
│   │   │   ├── validate.yml
│   │   │   ├── helm_repo.yml
│   │   │   ├── helm_deploy.yml
│   │   │   └── verify.yml
│   │   └── meta/
│   ├── common/                # 基础配置
│   ├── nginx/                 # Web 服务器
│   ├── node_exporter/         # 监控
│   └── ...（其他 roles）
│
├── inventory/                  # 📋 旧版 inventory（兼容保留）
│   ├── hosts.yml
│   └── group_vars/
│
├── vars/                       # 🔐 变量和密钥
│   └── secrets.yml.example    # 密钥模板
│
├── docs/                       # 📖 文档（精简版）
│   ├── README.md              # 文档索引
│   ├── REFACTORED_DEPLOYMENT_GUIDE.md  # 完整部署指南★
│   ├── QUICKSTART.md          # 快速开始
│   ├── CLOUDFLARED_K8S_HELM.md
│   ├── SECRETS_MANAGEMENT.md
│   ├── ...（22个核心文档）
│   └── archive/               # 归档文档
│       └── ...（历史文档）
│
├── tools/                      # 🛠️ Python 工具
│   ├── ssh_key_manager.py
│   ├── secrets_uploader.py
│   ├── cloudflare_manager.py
│   └── tunnel_manager.py
│
├── observability/              # 📊 可观测性配置
│   ├── prometheus/
│   └── grafana/
│
├── k8s_manifests/              # ☸️ Kubernetes 清单
│   └── cloudflared/
│
└── examples/                   # 📝 使用示例
    ├── cloudflared_simple.yml
    ├── cloudflared_advanced.yml
    └── cloudflared_multi_env.yml
```

## 🌟 重要文件说明

### 核心入口

| 文件 | 用途 | 优先级 |
|------|------|--------|
| `scripts/anixops.sh` | 统一管理脚本，所有操作的入口 | ⭐⭐⭐ |
| `README.md` | 主文档，快速开始和完整指南 | ⭐⭐⭐ |
| `playbooks/deployment/local.yml` | 本地部署 playbook | ⭐⭐⭐ |
| `playbooks/deployment/production.yml` | 生产部署 playbook | ⭐⭐⭐ |

### 配置文件

| 文件 | 用途 |
|------|------|
| `inventories/local/hosts.ini` | 本地环境配置 |
| `inventories/production/hosts.ini` | 生产环境配置（需修改） |
| `vars/secrets.yml.example` | 密钥模板 |
| `ansible.cfg` | Ansible 全局设置 |

### 核心 Roles

| Role | 用途 |
|------|------|
| `k8s_provision` | 自动部署 Kind 或 K3s 集群 |
| `cloudflared_deploy` | 部署 Cloudflared 到 K8s |

### 文档

| 文档 | 用途 |
|------|------|
| `docs/REFACTORED_DEPLOYMENT_GUIDE.md` | 最详细的部署指南 |
| `docs/QUICKSTART.md` | 快速开始 |
| `docs/README.md` | 文档索引 |
| `playbooks/README.md` | Playbooks 说明 |

## 📂 目录功能

### 按用途分类

#### 部署和执行
- `scripts/` - 执行脚本
- `playbooks/` - Ansible playbooks
- `roles/` - 可复用的 role 模块

#### 配置
- `inventories/` - 新版环境配置（推荐）
- `inventory/` - 旧版配置（兼容）
- `vars/` - 变量和密钥

#### 资源
- `k8s_manifests/` - K8s 清单文件
- `observability/` - 监控配置
- `examples/` - 示例文件

#### 工具和文档
- `tools/` - Python 工具
- `docs/` - 文档
- `scripts/` - Shell 脚本

## 🎯 快速导航

**我想...**

- **开始部署** → 运行 `./scripts/anixops.sh deploy-local -t TOKEN`
- **查看所有命令** → 运行 `./scripts/anixops.sh help`
- **了解 playbooks** → 查看 `playbooks/README.md`
- **配置生产环境** → 编辑 `inventories/production/hosts.ini`
- **管理密钥** → 查看 `docs/SECRETS_MANAGEMENT.md`
- **查看文档** → 打开 `docs/README.md`

## 📊 统计信息

- **Playbooks**: 14 个（按功能分类到 3 个目录）
- **Roles**: 13+ 个（模块化设计）
- **Scripts**: 3 个（集中在 scripts 目录）
- **Inventories**: 2 套（local 和 production 完全隔离）
- **核心文档**: 22 个（精简版）
- **归档文档**: 10+ 个（archive 目录）

## 🔄 版本历史

**v2.0 (重构版) - 2025-10-28**
- ✅ 创建 `scripts/anixops.sh` 统一管理脚本
- ✅ Playbooks 重组为多级目录结构
- ✅ 新增 `k8s_provision` 和 `cloudflared_deploy` roles
- ✅ 环境配置完全分离（inventories/local 和 production）
- ✅ 文档精简和归档
- ✅ 根目录只保留一个 README.md

**v1.x (旧版)**
- 原始结构，playbooks 扁平化
- 脚本分散
- 文档混乱

---

> 💡 **提示**: 这是一个经过完整重构的项目，新的结构更清晰、更易维护。建议新用户直接使用 `scripts/anixops.sh` 作为主入口。
