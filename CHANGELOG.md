# AnixOps Ansible 项目更新日志

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
