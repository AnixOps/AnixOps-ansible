# AnixOps Ansible 项目更新日志

## v0.1.0 - 2025-10-28 🎉 重大重构版本

### 🚀 重大功能更新

#### ✨ Kubernetes 部署支持（重要里程碑）

- **🆕 K8s 集群自动化部署**
  - 新增 `k8s_provision` Role：支持本地 Kind 和生产 K3s 集群部署
  - 自动检测并安装 Docker、kubectl、Helm 等依赖工具
  - 本地环境：自动创建 Kind 集群，适合开发测试
  - 生产环境：一键部署 K3s 轻量级 Kubernetes 集群
  - 完整的集群验证和健康检查流程

- **🆕 Cloudflared K8s 部署**
  - 新增 `cloudflared_deploy` Role：使用 Helm 部署 Cloudflared
  - 支持本地和生产环境自动适配
  - 安全的 Token 管理（支持命令行、环境变量、Ansible Vault）
  - 自动化 Namespace、Secret、Helm Chart 管理
  - 完整的部署验证和日志查看

#### 🔧 统一管理脚本

- **🎯 anixops.sh - 统一入口**
  - 集成所有管理功能到单一脚本
  - 支持命令：`deploy-local`、`deploy-production`、`cleanup-local`、`status-local` 等
  - 友好的彩色输出和进度提示
  - 完整的参数支持：`--tags`、`--skip-tags`、`--dry-run`、`--verbose`
  - 详细的帮助文档和使用示例
  - 所有脚本统一移至 `scripts/` 目录

#### 📁 项目结构重组

- **Playbooks 多级目录结构**
  - `playbooks/deployment/` - 部署相关（local.yml、production.yml 等）
  - `playbooks/cloudflared/` - Cloudflared 专用（k8s-helm.yml 等）
  - `playbooks/maintenance/` - 维护管理（health-check.yml 等）
  - 总计 14 个 playbooks，按功能清晰分类

- **环境配置完全分离**
  - `inventories/local/` - 本地 Kind 集群配置
  - `inventories/production/` - 生产 K3s 集群配置
  - 独立的 hosts.ini 和 group_vars，互不干扰

#### 📚 文档重构

- **精简和归档**
  - 根目录只保留 1 个主 README.md
  - 核心文档：22 个（常用和实用）
  - 归档文档：14 个（历史和过时文档移至 docs/archive/）
  - 新增 `PROJECT_STRUCTURE.md` - 完整的项目结构说明
  - 新增 `docs/README.md` - 文档索引和导航
  - 新增 `playbooks/README.md` - Playbooks 详细说明

### 🔄 重构和改进

#### 架构优化

- ✅ Role 模块化设计：k8s_provision + cloudflared_deploy
- ✅ 三阶段部署流程：K8s 部署 → Cloudflared 部署 → 验证
- ✅ 环境隔离：本地和生产完全独立配置
- ✅ 统一脚本管理：从多个脚本到一个 anixops.sh

#### 安全增强

- ✅ 多种 Token 管理方式（命令行、环境变量、Vault）
- ✅ Ansible Vault 完整集成
- ✅ 敏感信息不记录日志（no_log: true）
- ✅ 生产部署前确认提示

#### 用户体验

- ✅ 友好的彩色输出界面
- ✅ 详细的进度和状态展示
- ✅ 完整的错误提示和故障排除指南
- ✅ Dry-run 模式支持
- ✅ Tags 支持（只运行特定部分）

### 📊 统计数据

- **Playbooks**: 14 个（重组为 3 级目录）
- **Roles**: 13+ 个（新增 2 个核心 Role）
- **Scripts**: 3 个（全部在 scripts/ 目录）
- **Inventories**: 2 套（完全隔离）
- **文档**: 22 核心 + 14 归档

### 🎯 使用示例

```bash
# 本地部署（最简单）
./scripts/anixops.sh deploy-local -t "your-cloudflare-token"

# 生产部署（使用 Vault）
./scripts/anixops.sh deploy-production --vault-password ~/.vault_pass

# 查看状态
./scripts/anixops.sh status-local

# 清理环境
./scripts/anixops.sh cleanup-local
```

### 🔗 相关文档

- [README.md](README.md) - 快速开始和完整指南
- [docs/REFACTORED_DEPLOYMENT_GUIDE.md](docs/REFACTORED_DEPLOYMENT_GUIDE.md) - 详细部署指南
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - 项目结构总览
- [playbooks/README.md](playbooks/README.md) - Playbooks 说明

---

## v0.0.2 - 2025-10-23

### 🚀 功能增强

#### ✨ 新增功能

- **🆕 Secrets 批量上传工具**（重要更新）
  - 新增 `secrets_uploader.py` 工具，从 .env 文件批量上传 GitHub Secrets
  - 支持交互式和命令行两种模式
  - 自动加密并安全上传敏感信息
  - 支持过滤和排除特定变量
  - 提供 Dry Run 测试模式
  - 实时显示上传进度和结果统计
  - 完整的错误处理和用户友好提示
  - 详细的使用文档和示例

- **GitHub Actions 工作流完善**
  - 完善 `deploy.yml` 工作流，添加完整的环境变量支持（45+ 环境变量）
  - 更新 `lint.yml` 工作流，优化代码检查流程
  - 改进 `ansible-ci.yml` CI/CD 流程，添加 Dry Run 测试
  - 支持 workflow_dispatch 手动触发部署，可选择部署目标
  - 添加部署摘要和详细的错误通知

- **环境变量系统**
  - 完善 `.env.example` 文件，提供详细的配置说明
  - 支持多服务器 IP 配置（IPv4/IPv6）
  - 添加可观测性服务配置（Prometheus、Loki、Grafana）
  - 支持 SSL/TLS 配置（自定义证书和 ACME）
  - Cloudflare API 集成配置
  - Grafana 认证配置
  - 防火墙白名单配置

#### 📝 文档改进

- 新增 `docs/GITHUB_SECRETS_REFERENCE.md` - 完整的 Secrets 配置参考手册
- 新增 `docs/RELEASE_GUIDE.md` - 版本发布流程和检查清单
- 新增 `tools/README_SECRETS_UPLOADER.md` - Secrets 上传工具详细文档
- 更新 README.md，添加版本徽章和许可证徽章
- 完善快速开始指南，添加新工具使用说明
- 优化项目结构说明
- 改进 SSH 密钥管理说明
- 文档索引添加新文档链接

#### 🔧 工作流改进

- 优化部署流程，添加部署摘要输出
- 改进错误处理和失败通知
- 添加更多调试信息输出
- 支持动态 inventory 生成

### 🐛 Bug 修复

- 修复工作流中环境变量传递问题
- 修正文档中的示例错误
- 优化 SSH 密钥权限设置

### 📦 依赖更新

- 更新 GitHub Actions 版本（checkout@v4, setup-python@v5）
- 使用 Python 3.11 作为默认版本

---

## v0.0.1 - 2025-10-20

### 🎉 初始版本发布

#### ✨ 新功能

- **GitOps 工作流**
  - 完整的 GitHub Actions CI/CD 集成
  - 自动化代码检查 (ansible-lint, yamllint)
  - 自动化部署到生产环境
  
- **Ansible Roles**
  - `common`: 基础系统配置、安全加固、用户管理
  - `nginx`: Web 服务器部署和配置
  - `node_exporter`: Prometheus 主机监控
  - `promtail`: Loki 日志收集代理

- **Playbooks**
  - `site.yml`: 完整部署所有配置
  - `quick-setup.yml`: 快速初始化新服务器
  - `web-servers.yml`: 专门部署 Web 服务器
  - `health-check.yml`: 健康检查和状态监控

- **可观测性**
  - Prometheus 告警规则（主机和 Nginx）
  - Grafana 仪表盘模板
  - 完整的 PLG (Prometheus + Loki + Grafana) 栈集成

- **工具**
  - `ssh_key_manager.py`: SSH 密钥安全管理工具
  - 支持加密上传私钥到 GitHub Secrets
  - 交互式和命令行模式

#### 🔒 安全特性

- SSH 密钥认证，禁用密码登录
- UFW/Firewalld 防火墙配置
- Fail2Ban 入侵防护
- 系统内核参数优化
- 安全的 SSH 配置模板

#### 📚 文档

- 完整的中英文双语运维手册
- README.md 快速开始指南
- QUICKSTART.md 5 分钟部署指南
- 代码内详细注释

#### 🌐 全球分布式支持

- 支持多区域服务器管理
- 环境变量驱动的主机配置
- 跳板机支持（可选）

---

## 路线图

### v0.1.0 (计划中)

- [ ] Docker 容器支持
- [ ] K8s 集成
- [ ] 更多应用 roles (Redis, PostgreSQL, etc.)
- [ ] Vault 集成用于密钥管理
- [ ] 更完善的回滚机制

### v0.2.0 (计划中)

- [ ] 多云支持 (AWS, GCP, Azure)
- [ ] Terraform 集成
- [ ] 自动化测试框架
- [ ] 性能优化和并发执行

---

## 贡献者

- @kalijerry - 项目创建者和主要维护者

---

**感谢所有贡献者和使用者！**
