# GitHub Actions Workflow 快速参考

## 🎯 两个 Workflow 的区别

### 1️⃣ `ansible-test.yml` - 连接测试 + 简单部署
**用途**: 快速测试连接、自动化 CI/CD
- ✅ 自动触发（push/PR/定时任务）
- ✅ 手动触发时可选 playbook
- ✅ 适合日常检查和简单部署

### 2️⃣ `ansible-deploy.yml` - 专业部署工具
**用途**: 生产环境部署、高级配置
- ✅ 更多部署选项（环境、dry-run、详细日志）
- ✅ 环境保护（development/staging/production）
- ✅ 健康检查和部署摘要

---

## 🚀 快速场景选择

### 测试服务器连接
```
Workflow: ansible-test.yml
Playbook: ping-only
Target: all
```

### 部署到开发环境（安全测试）
```
Workflow: ansible-deploy.yml
Playbook: site.yml
Target: dev
Environment: development
Dry Run: ✅ (先测试)
```

### 只更新 Web 服务器
```
Workflow: ansible-deploy.yml
Playbook: web-servers.yml
Target: web_servers
Environment: production
Skip Roles: (留空)
```

### 只更新 Prometheus（不动 Grafana）
```
Workflow: ansible-deploy.yml
Playbook: observability.yml
Target: observability
Environment: production
Skip Roles: grafana_server,loki_server
```

### 生产环境完整部署
```
Workflow: ansible-deploy.yml
Playbook: site.yml
Target: prod
Environment: production
Dry Run: ❌
Verbosity: verbose (-v)
```

---

## 📊 参数对照表

### Target Group（目标组）
| 选项 | 包含的服务器 | 用途 |
|------|-------------|------|
| `all` | 所有服务器 | 完整部署 |
| `web_servers` | de-test-1, pl-test-1 | Web 服务 |
| `observability` | pl-test-1 | 监控系统 |
| `dev` | de-test-1 | 开发测试 |
| `prod` | pl-test-1 | 生产环境 |

### Playbook 选择
| Playbook | 功能 | 耗时 |
|----------|------|------|
| `ping-only` | 仅测试连接 | ~30s |
| `quick-setup.yml` | 快速基础配置 | ~2min |
| `web-servers.yml` | Web 服务器配置 | ~3min |
| `observability.yml` | 监控系统部署 | ~5min |
| `firewall-setup.yml` | 防火墙配置 | ~1min |
| `health-check.yml` | 健康检查 | ~1min |
| `site.yml` | 完整部署 | ~8min |

### Skip Roles（跳过角色）
常用角色名称：
- `nginx` - 跳过 Nginx
- `prometheus_server` - 跳过 Prometheus
- `grafana_server` - 跳过 Grafana
- `loki_server` - 跳过 Loki
- `node_exporter` - 跳过 Node Exporter
- `promtail` - 跳过 Promtail
- `common` - 跳过基础配置

**示例**: `nginx,grafana_server` (逗号分隔，无空格)

---

## ⚠️ 最佳实践

### ✅ 推荐做法
1. **先 dry-run 后部署** - 生产环境必须先测试
2. **先 dev 后 prod** - 分阶段部署
3. **小步快跑** - 部分更新比完整部署安全
4. **查看日志** - 部署后检查 Actions 日志

### ❌ 避免的做法
1. ~~直接部署到 prod（未测试）~~
2. ~~同时运行多个部署到同一服务器~~
3. ~~跳过关键依赖角色~~
4. ~~忽略失败警告~~

---

## 🔄 典型工作流

### 情况 1: 新功能测试
```
1. ansible-deploy.yml
   → Playbook: site.yml
   → Target: dev
   → Dry Run: true (查看变更)

2. ansible-deploy.yml
   → Playbook: site.yml
   → Target: dev
   → Dry Run: false (实际部署)

3. ansible-test.yml
   → Playbook: health-check.yml
   → Target: dev (验证)

4. ansible-deploy.yml
   → Playbook: site.yml
   → Target: prod
   → Environment: production (上线)
```

### 情况 2: Nginx 配置更新
```
1. ansible-deploy.yml
   → Playbook: web-servers.yml
   → Target: dev
   → Dry Run: true

2. ansible-deploy.yml
   → Playbook: web-servers.yml
   → Target: web_servers
   → Environment: production
```

### 情况 3: 紧急防火墙修复
```
ansible-deploy.yml
→ Playbook: firewall-setup.yml
→ Target: all
→ Verbosity: verbose (-v)
→ 立即执行
```

---

## 📞 获取帮助

- 📖 详细文档: [WORKFLOW_USAGE.md](WORKFLOW_USAGE.md)
- 🔧 Workflow 配置: `.github/workflows/`
- 📝 使用示例: [EXAMPLES.md](EXAMPLES.md)
- 🏷️ 服务器信息: [SERVER_ALIASES.md](SERVER_ALIASES.md)

---

**快速导航**: [README](../README.md) • [快速开始](QUICKSTART.md) • [GitHub Actions 设置](GITHUB_ACTIONS_SETUP.md)
