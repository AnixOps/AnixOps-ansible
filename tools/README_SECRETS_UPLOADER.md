# GitHub Secrets Uploader

> 从 `.env` 文件批量上传 Secrets 到 GitHub - v0.0.2

这是一个自动化工具，可以将本地 `.env` 文件中的环境变量批量上传为 GitHub Repository Secrets，极大简化 CI/CD 配置过程。

## 🌟 功能特性

- ✅ **批量上传**：一次性上传所有环境变量
- ✅ **安全加密**：使用 GitHub 公钥加密传输
- ✅ **交互式模式**：友好的交互式配置界面
- ✅ **命令行模式**：支持脚本自动化
- ✅ **过滤支持**：可排除不需要上传的变量
- ✅ **Dry Run**：测试模式，不实际上传
- ✅ **进度显示**：实时显示上传进度和结果
- ✅ **错误处理**：详细的错误提示和处理

## 📋 前置要求

### 1. Python 依赖

```bash
pip install requests PyNaCl
```

或使用项目的 requirements.txt：

```bash
pip install -r requirements.txt
```

### 2. GitHub Personal Access Token

创建一个具有 `repo` 权限的 Token：

1. 进入 GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限（完整仓库访问）
4. 生成并复制 Token（格式：`ghp_...`）

⚠️ **重要**：Token 只显示一次，请妥善保存！

## 🚀 使用方法

### 方式一：交互式模式（推荐新手）

直接运行脚本，按提示输入信息：

```bash
python tools/secrets_uploader.py
```

交互式界面：

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           GitHub Secrets Uploader v0.0.2                     ║
║           从 .env 文件批量上传 Secrets                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

🔧 交互式配置模式

📁 .env 文件路径 [.env]: .env
📦 GitHub 仓库 (owner/repo): AnixOps/AnixOps-ansible
🔑 GitHub Token (ghp_...): ghp_your_token_here

是否要排除某些变量？(输入关键词，用逗号分隔，留空则全部上传)
排除模式 [留空]: LOCAL,TEST
```

### 方式二：命令行模式（适合自动化）

```bash
python tools/secrets_uploader.py \
  --env .env \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_your_token_here \
  --yes
```

### 方式三：测试模式（Dry Run）

先测试，不实际上传：

```bash
python tools/secrets_uploader.py \
  --env .env \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_your_token_here \
  --dry-run
```

## 📖 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--env` | .env 文件路径 | `--env .env` |
| `--repo` | GitHub 仓库（必需） | `--repo owner/repo` |
| `--token` | GitHub Token（必需） | `--token ghp_xxx` |
| `--exclude` | 排除的变量关键词，逗号分隔 | `--exclude LOCAL,TEST` |
| `--dry-run` | 测试模式，不实际上传 | `--dry-run` |
| `--yes` | 跳过确认提示 | `--yes` |

## 📝 使用示例

### 示例 1：上传所有变量

```bash
python tools/secrets_uploader.py \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_xxxxxxxxxxxxx \
  --yes
```

### 示例 2：排除本地测试变量

```bash
python tools/secrets_uploader.py \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_xxxxxxxxxxxxx \
  --exclude LOCAL,DEV,TEST \
  --yes
```

### 示例 3：使用不同的 .env 文件

```bash
python tools/secrets_uploader.py \
  --env .env.production \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_xxxxxxxxxxxxx \
  --yes
```

### 示例 4：先测试再上传

```bash
# 1. 测试模式
python tools/secrets_uploader.py \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_xxxxxxxxxxxxx \
  --dry-run

# 2. 确认无误后正式上传
python tools/secrets_uploader.py \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_xxxxxxxxxxxxx \
  --yes
```

## 🔒 安全最佳实践

1. ✅ **永远不要将 Token 提交到 Git**
2. ✅ **使用最小权限 Token**（只需要 `repo` 权限）
3. ✅ **定期轮换 Token**
4. ✅ **使用 `.gitignore` 忽略 .env 文件**
5. ✅ **上传完成后立即删除本地 Token**
6. ⚠️ **不要在公共环境运行此脚本**
7. ⚠️ **检查 .env 文件内容，确保没有敏感注释**

## 📤 输出示例

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           GitHub Secrets Uploader v0.0.2                     ║
║           从 .env 文件批量上传 Secrets                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

📖 读取文件: .env
✓ 找到 25 个环境变量

📋 准备上传 25 个 secrets:
  1. ANSIBLE_USER = root
  2. ANSIBLE_PORT = 22
  3. US_W_1_V4 = 203.0.113.10/31
  4. US_W_1_V6 = 2001:db8::1/127
  ...

🔗 连接到 GitHub: AnixOps/AnixOps-ansible
✓ 连接成功

🚀 开始上传 secrets...

[1/25] 上传 ANSIBLE_USER... ✓
[2/25] 上传 ANSIBLE_PORT... ✓
[3/25] 上传 US_W_1_V4... ✓
...
[25/25] 上传 FIREWALL_WHITELIST_IPS... ✓

============================================================
📊 上传摘要
============================================================
  总计: 25
  ✓ 成功: 25
  ✗ 失败: 0
============================================================

🎉 所有 secrets 上传成功！
```

## 🐛 故障排除

### 问题 1：导入错误

```
✗ 错误: 缺少依赖库
```

**解决方法**：

```bash
pip install requests PyNaCl
```

### 问题 2：Token 无效

```
✗ 错误: Token 无效或已过期
```

**解决方法**：
1. 检查 Token 格式（应以 `ghp_` 开头）
2. 确认 Token 未过期
3. 确认 Token 有 `repo` 权限
4. 重新生成 Token

### 问题 3：仓库不存在

```
✗ 错误: 仓库 owner/repo 不存在或无权访问
```

**解决方法**：
1. 检查仓库名称格式：`owner/repo`
2. 确认你有仓库的访问权限
3. 检查 Token 权限范围

### 问题 4：上传失败

```
[5/25] 上传 SOME_SECRET... ✗ 上传失败: 422
```

**解决方法**：
1. Secret 名称只能包含字母、数字和下划线
2. Secret 值不能为空
3. 检查 API 速率限制

### 问题 5：.env 文件格式错误

**确保 .env 文件格式正确**：

```bash
# 正确格式
ANSIBLE_USER=root
ANSIBLE_PORT=22

# 支持引号
US_W_1_V4="203.0.113.10/31"

# 支持注释
# 这是注释
PROMETHEUS_URL=http://example.com

# 错误格式（会被跳过）
EMPTY_VALUE=
```

## 🔄 与其他工具对比

| 功能 | secrets_uploader.py | ssh_key_manager.py | GitHub CLI | 手动配置 |
|------|---------------------|---------------------|------------|----------|
| 批量上传 | ✅ | ❌ | ❌ | ❌ |
| 从 .env 读取 | ✅ | ❌ | ❌ | ❌ |
| 单个密钥上传 | ✅ | ✅ | ✅ | ✅ |
| 交互式模式 | ✅ | ✅ | ❌ | ✅ |
| 自动化友好 | ✅ | ✅ | ✅ | ❌ |
| 进度显示 | ✅ | ❌ | ❌ | ❌ |

## 📚 相关文档

- 📖 [GitHub Secrets 配置参考](../docs/GITHUB_SECRETS_REFERENCE.md)
- 🔐 [SSH 密钥管理方案](../docs/SSH_KEY_MANAGEMENT.md)
- 🔧 [GitHub Actions 配置](../docs/GITHUB_ACTIONS_SETUP.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

---

**最后更新：** 2025-10-23  
**版本：** v0.0.2  
**作者：** AnixOps Team
