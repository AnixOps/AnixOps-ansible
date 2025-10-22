# 版本发布指南

> AnixOps-ansible 项目版本发布流程和检查清单

## 📋 版本发布检查清单

### 准备阶段

- [ ] 确认所有功能已完成并测试通过
- [ ] 更新 `CHANGELOG.md`
- [ ] 更新 `README.md` 中的版本徽章
- [ ] 检查所有文档是否已更新
- [ ] 运行完整的代码检查（lint）
- [ ] 验证 GitHub Actions 工作流配置

### 发布阶段

- [ ] 更新版本号
- [ ] 创建 Git 标签
- [ ] 推送到 GitHub
- [ ] 创建 GitHub Release
- [ ] 发布公告

### 验证阶段

- [ ] 验证 GitHub Actions 工作流正常运行
- [ ] 测试部署流程
- [ ] 更新项目文档链接

---

## 🔢 版本号规范

项目使用 **语义化版本控制（Semantic Versioning）**：`MAJOR.MINOR.PATCH`

### 版本号含义

- **MAJOR（主版本号）**：不兼容的 API 修改
- **MINOR（次版本号）**：向下兼容的功能性新增
- **PATCH（修订号）**：向下兼容的问题修正

### 版本号示例

```
v1.0.0 - 第一个稳定版本
v1.1.0 - 添加新功能
v1.1.1 - Bug 修复
v2.0.0 - 重大变更，不向下兼容
```

### 预发布版本

- **Alpha**：`v1.0.0-alpha.1` - 内部测试版本
- **Beta**：`v1.0.0-beta.1` - 公开测试版本
- **RC**：`v1.0.0-rc.1` - 候选发布版本

---

## 📝 更新 CHANGELOG.md

### 模板结构

```markdown
# AnixOps Ansible 项目更新日志

## vX.Y.Z - YYYY-MM-DD

### 🚀 功能增强

#### ✨ 新增功能
- 功能描述 1
- 功能描述 2

#### 📝 文档改进
- 文档改进 1
- 文档改进 2

#### 🔧 工作流改进
- 工作流改进 1
- 工作流改进 2

### 🐛 Bug 修复
- Bug 修复描述 1
- Bug 修复描述 2

### 📦 依赖更新
- 依赖更新说明

### ⚠️ 破坏性变更（如有）
- 破坏性变更说明

### 🗑️ 废弃功能（如有）
- 废弃功能说明

---
```

### Emoji 使用指南

- 🎉 初始版本发布
- ✨ 新增功能
- 🐛 Bug 修复
- 📝 文档更新
- 🔧 配置/工具改进
- 🚀 性能提升
- 🔒 安全修复
- ♻️ 代码重构
- 🗑️ 移除功能
- ⚠️ 破坏性变更

---

## 🏷️ 更新版本徽章

### README.md 徽章

```markdown
![Version](https://img.shields.io/badge/version-vX.Y.Z-blue?style=for-the-badge)
```

### 其他需要更新的地方

- 项目描述中的版本号
- 文档页脚的"最后更新"和"版本"信息
- LICENSE 文件（如果包含版本信息）

---

## 🏗️ 发布流程

### 1. 完成代码修改

确保所有功能已完成并测试通过。

### 2. 更新文档

```bash
# 更新 CHANGELOG.md
vim CHANGELOG.md

# 更新 README.md 版本徽章
vim README.md

# 更新其他文档的版本信息
grep -r "v[0-9]\.[0-9]\.[0-9]" docs/
```

### 3. 提交变更

```bash
# 暂存所有变更
git add .

# 提交（使用统一的提交消息格式）
git commit -m "chore: prepare for vX.Y.Z release"
```

### 4. 创建标签

```bash
# 创建带注释的标签
git tag -a vX.Y.Z -m "Release vX.Y.Z

主要变更：
- 功能 1
- 功能 2
- Bug 修复
"

# 查看标签
git tag -l

# 查看标签详情
git show vX.Y.Z
```

### 5. 推送到 GitHub

```bash
# 推送代码
git push origin main

# 推送标签
git push origin vX.Y.Z

# 或一次性推送所有标签
git push origin --tags
```

### 6. 创建 GitHub Release

#### 方式一：通过 GitHub 网页界面

1. 进入仓库页面
2. 点击右侧 "Releases" → "Draft a new release"
3. 选择标签：`vX.Y.Z`
4. 填写 Release 标题：`Release vX.Y.Z`
5. 填写发布说明（从 CHANGELOG.md 复制）
6. 上传附件（如有）
7. 勾选选项：
   - ✅ Set as the latest release（设为最新版本）
   - ⚠️ Set as a pre-release（预发布版本勾选）
8. 点击 "Publish release"

#### 方式二：使用 GitHub CLI

```bash
# 安装 GitHub CLI
# https://cli.github.com/

# 创建 Release
gh release create vX.Y.Z \
  --title "Release vX.Y.Z" \
  --notes-file CHANGELOG.md \
  --latest

# 创建预发布版本
gh release create vX.Y.Z-beta.1 \
  --title "Beta Release vX.Y.Z-beta.1" \
  --notes "测试版本，请勿用于生产环境" \
  --prerelease
```

### 7. 发布公告

根据需要，在以下渠道发布公告：

- GitHub Discussions
- 项目博客
- 社交媒体
- 邮件列表

---

## 🧪 测试发布

在正式发布前，建议先创建预发布版本进行测试。

### 创建测试分支

```bash
git checkout -b release/vX.Y.Z
```

### 部署到测试环境

```bash
# 触发测试部署
git push origin release/vX.Y.Z

# 或使用工作流手动触发
gh workflow run deploy.yml --ref release/vX.Y.Z
```

### 验证测试

- [ ] 所有 Ansible playbook 正常运行
- [ ] GitHub Actions 工作流通过
- [ ] 文档链接正确
- [ ] 配置文件无误

### 合并到主分支

```bash
git checkout main
git merge release/vX.Y.Z
git push origin main
```

---

## 🔄 回滚发布

如果发现严重问题需要回滚：

### 1. 删除有问题的 Release

```bash
# 删除 GitHub Release
gh release delete vX.Y.Z --yes

# 删除本地标签
git tag -d vX.Y.Z

# 删除远程标签
git push origin :refs/tags/vX.Y.Z
```

### 2. 回退代码

```bash
# 回退到上一个版本
git reset --hard vX.Y.Z-1

# 强制推送（谨慎操作）
git push origin main --force
```

### 3. 发布修复版本

修复问题后，发布一个 PATCH 版本（如 vX.Y.Z+1）。

---

## 📊 发布后检查

### 验证项目

- [ ] GitHub Release 页面显示正常
- [ ] 版本徽章正确显示
- [ ] 下载链接可用
- [ ] 文档链接有效

### 监控工作流

- [ ] GitHub Actions 工作流运行正常
- [ ] 部署流程无错误
- [ ] 测试通过率正常

### 收集反馈

- [ ] 关注 GitHub Issues
- [ ] 检查部署日志
- [ ] 收集用户反馈

---

## 📅 发布周期

建议的发布周期：

- **主版本（MAJOR）**：每年 1-2 次
- **次版本（MINOR）**：每季度 1-2 次
- **修订版本（PATCH）**：按需发布（Bug 修复）
- **预发布版本**：开发阶段持续发布

---

## 🔐 安全发布

对于包含安全修复的版本：

1. **不要提前公开漏洞细节**
2. **协调发布时间**（与受影响用户沟通）
3. **在 Release Notes 中明确标注安全修复**
4. **建议用户立即升级**
5. **发布后通知相关方**

### 安全发布模板

```markdown
## 🔒 安全更新 vX.Y.Z

本版本包含重要安全修复，建议所有用户立即升级。

### 修复的安全问题

- **CVE-XXXX-XXXX**: 问题描述
- **严重程度**: High/Medium/Low
- **影响版本**: vX.Y.Z 之前的所有版本

### 升级方法

\`\`\`bash
git pull origin main
git checkout vX.Y.Z
./scripts/anixops.sh deploy
\`\`\`

### 详细信息

完整的安全公告请查看：[链接]
```

---

## 🛠️ 自动化发布

可以创建自动化脚本简化发布流程：

```bash
#!/bin/bash
# release.sh - 自动化版本发布脚本

VERSION=$1
if [ -z "$VERSION" ]; then
  echo "Usage: ./release.sh vX.Y.Z"
  exit 1
fi

echo "📦 Preparing release $VERSION..."

# 1. 更新版本号
sed -i "s/version-v[0-9.]\+/version-$VERSION/" README.md

# 2. 提交变更
git add .
git commit -m "chore: prepare for $VERSION release"

# 3. 创建标签
git tag -a $VERSION -m "Release $VERSION"

# 4. 推送
git push origin main
git push origin $VERSION

# 5. 创建 GitHub Release
gh release create $VERSION \
  --title "Release $VERSION" \
  --notes-file CHANGELOG.md \
  --latest

echo "✅ Release $VERSION published successfully!"
```

---

## 📚 相关资源

- [语义化版本控制](https://semver.org/lang/zh-CN/)
- [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
- [GitHub Releases 文档](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [Git 标签管理](https://git-scm.com/book/zh/v2/Git-基础-打标签)

---

**最后更新：** 2025-10-23  
**版本：** v0.0.2
