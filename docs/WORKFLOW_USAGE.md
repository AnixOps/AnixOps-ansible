# GitHub Actions Workflow 使用指南

## 概述

我们的 Ansible workflow 现在支持灵活的部署选项，你可以：
- ✅ 选择特定的 playbook 进行部署
- ✅ 指定目标服务器组（all/web_servers/observability/dev/prod）
- ✅ 跳过不需要的角色
- ✅ 只进行连接测试（ping-only）

## 🚀 快速使用

### 1. 手动触发 Workflow

在 GitHub 仓库中：
1. 进入 **Actions** 标签页
2. 选择 **Ansible Connection Test** workflow
3. 点击 **Run workflow** 按钮
4. 配置参数（见下方）

### 2. Workflow 参数说明

#### **Playbook to run** (要运行的 playbook)
选择要执行的任务：

- **`ping-only`** (默认) - 仅测试服务器连接，不部署
- **`site.yml`** - 完整部署所有配置
- **`web-servers.yml`** - 仅部署 Web 服务器
- **`observability.yml`** - 仅部署监控系统
- **`quick-setup.yml`** - 快速设置
- **`firewall-setup.yml`** - 防火墙配置
- **`health-check.yml`** - 健康检查

#### **Target server group** (目标服务器组)
选择部署到哪些服务器：

- **`all`** (默认) - 所有服务器
- **`web_servers`** - Web 服务器组（de-1, jp-1, uk-1, us-w-1）
- **`observability`** - 监控服务器（pl-1）
- **`dev`** - 开发服务器（de-test-1）
- **`prod`** - 生产服务器（pl-test-1）

#### **Roles to skip** (跳过的角色)
可选参数，逗号分隔的角色名称，例如：
- `nginx` - 跳过 Nginx 安装
- `prometheus,grafana` - 跳过多个角色
- 留空 - 不跳过任何角色

## 📖 使用场景示例

### 场景 1: 只测试服务器连接
```
Playbook: ping-only
Target Group: all
Skip Roles: (留空)
```
**用途**: 每日自动检查、手动验证连接

---

### 场景 2: 部署 Web 服务到开发环境
```
Playbook: web-servers.yml
Target Group: dev
Skip Roles: (留空)
```
**用途**: 在开发服务器上测试 Web 配置

---

### 场景 3: 部署监控系统（跳过 Grafana）
```
Playbook: observability.yml
Target Group: observability
Skip Roles: grafana_server
```
**用途**: 只更新 Prometheus 和 Loki，不动 Grafana

---

### 场景 4: 完整部署到生产环境
```
Playbook: site.yml
Target Group: prod
Skip Roles: (留空)
```
**用途**: 完整部署所有服务到生产服务器

---

### 场景 5: 只部署 Nginx 到所有 Web 服务器
```
Playbook: web-servers.yml
Target Group: web_servers
Skip Roles: (留空)
```
**用途**: 更新所有 Web 服务器的 Nginx 配置

---

### 场景 6: 更新防火墙规则（仅开发环境）
```
Playbook: firewall-setup.yml
Target Group: dev
Skip Roles: (留空)
```
**用途**: 在开发环境测试防火墙变更

---

## 🔄 自动触发

Workflow 也会在以下情况自动运行（仅 ping 测试）：

- **Push to main** - 推送到 main 分支
- **Pull Request** - 创建或更新 PR
- **Daily Schedule** - 每天 00:00 UTC 自动运行

## 🏗️ Inventory 组别定义

当前配置的服务器组别：

### GitHub Actions (CI/CD)
```yaml
web_servers:
  - de-test-1  # 德国测试服务器
  - pl-test-1  # 波兰测试服务器

observability:
  - pl-test-1  # 监控系统服务器

dev:
  - de-test-1  # 开发环境

prod:
  - pl-test-1  # 生产环境
```

### 本地环境
```yaml
web_servers:
  - de-1, jp-1, uk-1, us-w-1

proxy_servers:
  - sg-1, jp-2, hk-1, uk-2

dev_servers:
  - fr-1

observability:
  - pl-1
```

## 🎯 最佳实践

### 1. 分阶段部署
```
第一步: ping-only → all (验证连接)
第二步: site.yml → dev (开发环境测试)
第三步: site.yml → prod (生产环境部署)
```

### 2. 部分更新
当你只需要更新某个服务：
```
# 只更新 Nginx
Playbook: web-servers.yml
Target: web_servers
Skip: (留空)

# 只更新 Prometheus
Playbook: observability.yml
Target: observability
Skip: grafana_server,loki_server
```

### 3. 紧急修复
快速部署关键修复：
```
Playbook: quick-setup.yml
Target: all
Skip: (留空)
```

### 4. 测试新功能
在开发环境验证：
```
Playbook: site.yml
Target: dev
Skip: (根据需要跳过不相关角色)
```

## 🔧 高级技巧

### 使用 --limit 和 --skip-tags
Workflow 内部会将参数转换为 Ansible 命令：

```bash
# 示例：部署到 dev 环境，跳过 nginx
ansible-playbook playbooks/site.yml \
  -i inventory/hosts.yml \
  --limit dev \
  --skip-tags nginx
```

### 扩展服务器组
如需添加新的服务器组，编辑：
1. `.github/workflows/ansible-test.yml` - 添加到 `target_group` 选项
2. Workflow 中的 inventory 生成部分

### 添加新的 Playbook
在 `playbooks/` 目录添加新 playbook 后：
1. 在 workflow 的 `playbook` 选项中添加文件名
2. 确保 playbook 使用了正确的 hosts 组别

## 📊 查看执行结果

运行后可以看到：
- ✅ 连接测试结果
- ✅ 各步骤执行日志
- ✅ 失败时的详细错误
- ✅ 部署摘要信息

## ⚠️ 注意事项

1. **生产环境部署** - 务必先在 dev 环境测试
2. **跳过角色** - 确保跳过的角色不影响其他依赖
3. **权限检查** - 确保 SSH 密钥和 secrets 配置正确
4. **并发执行** - 避免同时运行多个部署到同一服务器组

## 🆘 故障排查

### Workflow 执行失败
1. 检查 GitHub Secrets 是否配置完整
2. 验证服务器 SSH 连接
3. 查看具体的错误日志

### 无法连接服务器
1. 确认服务器 IP 正确
2. 检查防火墙规则
3. 验证 SSH 密钥权限

### Playbook 执行错误
1. 检查 playbook 语法
2. 确认角色依赖关系
3. 验证变量配置

## 📚 相关文档

- [快速入门](QUICKSTART.md)
- [参数说明](PARAMETERS.md)
- [GitHub Actions 设置](GITHUB_ACTIONS_SETUP.md)
- [多机器设置](MULTI_MACHINE_SETUP.md)

---

**提示**: 合理使用 workflow 参数可以大幅提升部署效率和安全性！
