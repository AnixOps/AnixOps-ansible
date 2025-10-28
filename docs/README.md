# 📚 文档目录

## 核心文档 (推荐阅读)

### 快速入门
- **[QUICKSTART.md](QUICKSTART.md)** - 快速开始指南
- **[REFACTORED_DEPLOYMENT_GUIDE.md](REFACTORED_DEPLOYMENT_GUIDE.md)** - 完整部署指南（重构版）

### Cloudflared 部署
- **[CLOUDFLARED_K8S_HELM.md](CLOUDFLARED_K8S_HELM.md)** - 使用 Helm 部署 Cloudflared 到 K8s
- **[CLOUDFLARED_QUICKSTART.md](CLOUDFLARED_QUICKSTART.md)** - Cloudflared 快速开始
- **[CLOUDFLARED_K8S_QUICK_REF.md](CLOUDFLARED_K8S_QUICK_REF.md)** - K8s 部署快速参考
- **[CLOUDFLARE_TOKEN_QUICK_REF.md](CLOUDFLARE_TOKEN_QUICK_REF.md)** - Token 管理快速参考

### 配置管理
- **[PARAMETERS.md](PARAMETERS.md)** - 所有可配置参数说明
- **[SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md)** - 密钥管理指南
- **[SSH_KEY_MANAGEMENT.md](SSH_KEY_MANAGEMENT.md)** - SSH 密钥管理

### 高级功能
- **[OBSERVABILITY_SETUP.md](OBSERVABILITY_SETUP.md)** - 可观测性设置 (PLG Stack)
- **[FIREWALL_WHITELIST_SETUP.md](FIREWALL_WHITELIST_SETUP.md)** - 防火墙白名单配置
- **[CUSTOM_SSL_SETUP.md](CUSTOM_SSL_SETUP.md)** - 自定义 SSL 证书
- **[SERVER_ALIASES.md](SERVER_ALIASES.md)** - 服务器别名配置

### CI/CD
- **[GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)** - GitHub Actions 设置
- **[GITHUB_SECRETS_REFERENCE.md](GITHUB_SECRETS_REFERENCE.md)** - GitHub Secrets 参考
- **[WORKFLOW_QUICK_REF.md](WORKFLOW_QUICK_REF.md)** - 工作流快速参考
- **[WORKFLOW_USAGE.md](WORKFLOW_USAGE.md)** - 工作流使用说明

### 工具
- **[README_SECRETS_UPLOADER.md](README_SECRETS_UPLOADER.md)** - Secrets 批量上传工具
- **[README_TUNNEL_MANAGER.md](README_TUNNEL_MANAGER.md)** - Tunnel 管理工具

### 示例和发布
- **[EXAMPLES.md](EXAMPLES.md)** - 使用示例
- **[RELEASE_GUIDE.md](RELEASE_GUIDE.md)** - 发布指南

---

## 归档文档

旧的、过时的或特定场景的文档已移至 **[archive/](archive/)** 目录：
- Windows/WSL 相关文档
- 旧版 Cloudflared 部署指南
- 历史更新摘要
- 特定问题解决方案

---

## 📖 推荐阅读顺序

### 新用户
1. [QUICKSTART.md](QUICKSTART.md) - 了解基本概念
2. [REFACTORED_DEPLOYMENT_GUIDE.md](REFACTORED_DEPLOYMENT_GUIDE.md) - 完整部署流程
3. [CLOUDFLARED_QUICKSTART.md](CLOUDFLARED_QUICKSTART.md) - 部署 Cloudflared

### 配置管理
1. [PARAMETERS.md](PARAMETERS.md) - 了解所有参数
2. [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md) - 安全管理密钥
3. [SSH_KEY_MANAGEMENT.md](SSH_KEY_MANAGEMENT.md) - 管理 SSH 密钥

### CI/CD 设置
1. [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) - 配置 GitHub Actions
2. [GITHUB_SECRETS_REFERENCE.md](GITHUB_SECRETS_REFERENCE.md) - 设置 Secrets
3. [WORKFLOW_USAGE.md](WORKFLOW_USAGE.md) - 使用工作流

---

## 🔍 查找文档

**我想要...**

| 需求 | 文档 |
|------|------|
| 快速开始 | [QUICKSTART.md](QUICKSTART.md) |
| 部署 Cloudflared | [CLOUDFLARED_K8S_HELM.md](CLOUDFLARED_K8S_HELM.md) |
| 管理密钥 | [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md) |
| 配置监控 | [OBSERVABILITY_SETUP.md](OBSERVABILITY_SETUP.md) |
| 设置防火墙 | [FIREWALL_WHITELIST_SETUP.md](FIREWALL_WHITELIST_SETUP.md) |
| GitHub Actions | [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) |
| 所有参数 | [PARAMETERS.md](PARAMETERS.md) |
| 使用示例 | [EXAMPLES.md](EXAMPLES.md) |

---

## 💡 文档维护原则

本文档目录遵循以下原则：
1. **简洁**: 只保留常用和核心文档
2. **分类**: 按功能清晰分类
3. **更新**: 定期归档过时文档
4. **实用**: 注重实际使用价值

如果找不到需要的文档，可以：
1. 检查 [archive/](archive/) 目录
2. 查看项目 [README.md](../README.md)
3. 提交 Issue 询问
