# GitHub Actions Workflow 快速参考 (简化版)

## 🎯 两个 Workflow

### 1️⃣ `ansible-test.yml` - 测试和健康检查
**用途**: 连接测试、快速验证
- ✅ 自动触发（push/PR/定时）
- ✅ 3 个选项：ping-only / health-check / quick-setup
- ✅ 默认 ping-only 到所有服务器

### 2️⃣ `ansible-deploy.yml` - 部署工具
**用途**: 实际部署配置
- ✅ 4 个 playbook 选项
- ✅ 5 个目标组
- ✅ 默认 dry-run 模式（安全）

---

## 🚀 常用场景

### 测试连接（自动）
```
Workflow: ansible-test.yml
不需要手动触发 - 每天自动运行
```

### 快速测试（手动）
```
Workflow: ansible-test.yml
Action: ping-only
Target: all
```

### 部署到开发环境（先测试）
```
Workflow: ansible-deploy.yml
Playbook: quick-setup.yml
Target: dev
Dry Run: ✅ true (测试模式)
```

### 实际部署到开发环境
```
Workflow: ansible-deploy.yml
Playbook: quick-setup.yml
Target: dev
Dry Run: ❌ false (真实部署)
```

### 部署 Web 服务器
```
Workflow: ansible-deploy.yml
Playbook: web-servers.yml
Target: web_servers
Dry Run: ❌ false
```

### 完整部署到生产
```
Workflow: ansible-deploy.yml
Playbook: site.yml
Target: prod
Dry Run: ❌ false
```

---

## 📊 参数说明

### ansible-test.yml
| 参数 | 选项 | 默认值 |
|------|------|--------|
| Action | ping-only, health-check.yml, quick-setup.yml | ping-only |
| Target | all, web_servers, observability, dev, prod | all |

### ansible-deploy.yml
| 参数 | 选项 | 默认值 |
|------|------|--------|
| Playbook | quick-setup, site, web-servers, observability | quick-setup |
| Target | all, web_servers, observability, dev, prod | dev |
| Dry Run | true / false | **true** ⚠️ |

---

## 🎨 目标组说明

| 组别 | 包含服务器 | 用途 |
|------|-----------|------|
| `all` | 所有服务器 | 全局操作 |
| `web_servers` | de-test-1, pl-test-1 | Web 服务 |
| `observability` | pl-test-1 | 监控系统 |
| `dev` | de-test-1 | 开发测试 |
| `prod` | pl-test-1 | 生产环境 |

---

## ⚠️ 重要提示

### ✅ 安全特性
- **默认 Dry Run**: ansible-deploy.yml 默认开启测试模式
- **先测试后部署**: 建议先 dev 后 prod
- **分阶段部署**: 永远不要跳过测试

### 🔄 推荐工作流
```
1. ansible-deploy.yml → dev + dry_run=true  (看看会改什么)
2. ansible-deploy.yml → dev + dry_run=false (开发环境部署)
3. ansible-test.yml → health-check → dev    (验证健康)
4. ansible-deploy.yml → prod + dry_run=false (生产部署)
```

---

## � 完整文档

- [详细使用指南](WORKFLOW_USAGE.md)
- [快速开始](QUICKSTART.md)
- [GitHub Actions 设置](GITHUB_ACTIONS_SETUP.md)
