# GitHub Actions 配置指南

## 必需的 Repository Secrets

要在 GitHub Actions 中自动部署，需要在仓库设置中配置以下 Secrets：

### 1. SSH 密钥
- `SSH_PRIVATE_KEY` - SSH 私钥内容（使用 `tools/ssh_key_manager.py` 上传）

### 2. 服务器连接
- `ANSIBLE_USER` - SSH 用户名（默认：`root`）

### 3. 服务器 IP 地址

根据你在 `.env.example` 中定义的服务器，设置对应的 secrets。

**重要：连接逻辑**
- **`/31` (IPv4) 或 `/127` (IPv6) 段**：点对点连接，直接使用该 IP 连接
- **其他网段**：必须额外设置 `_SSH_IP` 变量，用于 SSH 连接（如公网 IP 或网关）

#### 点对点连接示例 (/31 或 /127)
- `US_W_1_V4` = `203.0.113.10/31` → 直接连接到 `203.0.113.10`
- `US_W_1_V6` = `2001:db8::1/127` → 直接连接到 `2001:db8::1`

#### 其他网段示例 (需要 SSH_IP)
- `US_W_2_V4` = `10.0.1.100/24` （内网 IP）
- `US_W_2_SSH_IP` = `203.0.113.20` （SSH 连接用的公网 IP）
- `JP_1_V4` = `10.10.0.50/27` （内网 IP）
- `JP_1_SSH_IP` = `45.76.123.45` （SSH 连接用的公网 IP）

#### 完整示例配置

#### 完整示例配置

```plaintext
# 点对点连接 (直接连接)
US_W_1_V4=203.0.113.10/31
US_W_1_V6=2001:db8::1/127
US_E_1_V4=203.0.113.30/31

# 内网段 (需要SSH_IP)
US_W_2_V4=10.0.1.100/24
US_W_2_V6=2001:db8:100::1/64
US_W_2_SSH_IP=203.0.113.20

JP_1_V4=10.10.0.50/27
JP_1_SSH_IP=45.76.123.45
```

#### 美国西部
- `US_W_1_V4` - 美西服务器1 IPv4（例如：`203.0.113.10/31`）
- `US_W_1_V6` - 美西服务器1 IPv6（例如：`2001:db8::1/127`）
- `US_W_2_V4` - 美西服务器2 IPv4（例如：`10.0.1.100/24`）
- `US_W_2_V6` - 美西服务器2 IPv6
- `US_W_2_SSH_IP` - 美西服务器2 SSH连接IP（**必需**，例如：`203.0.113.20`）

#### 美国东部
- `US_E_1_V4` - 美东服务器1 IPv4（例如：`203.0.113.30/31`）
- `US_E_1_V6` - 美东服务器1 IPv6

#### 日本
- `JP_1_V4` - 日本服务器1 IPv4（例如：`10.10.0.50/27`）
- `JP_1_V6` - 日本服务器1 IPv6
- `JP_1_SSH_IP` - 日本服务器1 SSH连接IP（**必需**，例如：`45.76.123.45`）

#### 欧洲
- `EU_1_V4` - 欧洲服务器1 IPv4（例如：`203.0.113.50/31`）
- `EU_1_V6` - 欧洲服务器1 IPv6

### 4. 可观测性配置（可选）
- `PROMETHEUS_URL` - Prometheus 服务器地址
- `LOKI_URL` - Loki 服务器地址
- `GRAFANA_URL` - Grafana 服务器地址

## 如何设置 Secrets

1. 进入 GitHub 仓库页面
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 输入 Secret 名称和值
5. 点击 **Add secret**

## 本地开发 vs GitHub Actions

### 本地开发
- 使用 `.env` 文件存储服务器 IP 和配置
- 复制 `.env.example` 到 `.env` 并填入真实值
- 运行 `./scripts/anixops.sh` 命令

### GitHub Actions
- 使用 Repository Secrets 存储敏感信息
- Workflow 会自动从 secrets 生成 inventory
- 推送到 `deploy` 分支或手动触发工作流

## 示例：上传 SSH 密钥

```bash
# 使用密钥管理工具
python tools/ssh_key_manager.py

# 或使用命令行
python tools/ssh_key_manager.py \
  --key-file ~/.ssh/id_rsa \
  --repo YourUsername/AnixOps-ansible \
  --token ghp_your_github_token \
  --secret-name SSH_PRIVATE_KEY
```

## 注意事项

1. **IP 地址格式**：
   - 在 secrets 中应**包含** CIDR 后缀（如 `/31`、`/127`、`/24`）
   - 脚本会自动解析并决定连接方式

2. **连接逻辑**：
   - `/31` 或 `/127` 段：直接连接该 IP
   - 其他网段：使用 `_SSH_IP` 指定的地址连接

3. **密钥权限**：确保 SSH 私钥有正确的权限（`600`）

4. **用户权限**：确保 `ANSIBLE_USER` 在目标服务器上有 sudo 权限

5. **网络访问**：
   - 点对点连接：确保 GitHub Actions runner 能直接访问该 IP
   - 内网服务器：确保 `_SSH_IP` 可从外网访问，且能路由到内网 IP

## GitHub Actions 工作流说明

### 1. Deploy to Production (deploy.yml)
**主部署工作流** - 包含完整的 CI/CD 流程

触发条件：
- 推送到 `deploy` 分支
- 针对 `deploy` 或 `main` 分支的 Pull Request
- 手动触发（workflow_dispatch）

工作流程：
1. **Lint (代码质量检查)**
   - 运行 yamllint 检查 YAML 语法
   - 运行 ansible-lint 检查 Ansible 最佳实践
   - 验证 playbook 语法

2. **Test (连接测试)**
   - 使用 `ansible ping` 测试所有主机连接
   - 仅在非 PR 时运行（需要真实 secrets）
   
3. **Deploy (部署)**
   - 执行完整的 Ansible playbook 部署
   - 仅在通过所有测试后运行
   - 仅在非 PR 时运行

### 2. Ansible Connection Test (ansible-test.yml)
**独立的连接测试工作流**

触发条件：
- 手动触发（workflow_dispatch）
- 定时任务（每天 00:00 UTC）

测试内容：
- Ping 所有主机
- Ping web_servers 组
- Ping observability 组
- 收集系统信息（setup 模块）

用途：
- 日常健康检查
- 验证 SSH 连接和凭证
- 监控服务器可用性

### 3. Ansible CI/CD Pipeline (ansible-ci.yml)
**独立的 CI 工作流** - 已被整合到 deploy.yml 中

> **注意**: 此工作流的功能已完全整合到 `deploy.yml` 中，建议删除此文件以避免重复运行。

## 触发部署

### 自动触发
推送到 `deploy` 分支：
```bash
git push origin main:deploy
```

### 手动触发部署
1. 进入 GitHub 仓库的 **Actions** 标签
2. 选择 **Deploy to Production** workflow
3. 点击 **Run workflow**
4. 选择目标主机组（`all`、`web_servers`、`observability` 等）
5. 点击运行

### 手动触发连接测试
1. 进入 GitHub 仓库的 **Actions** 标签
2. 选择 **Ansible Connection Test** workflow
3. 点击 **Run workflow**
4. 点击运行

## 工作流最佳实践

### Pull Request 流程
1. 创建功能分支进行开发
2. 提交 PR 到 `main` 或 `deploy` 分支
3. 自动运行 Lint 检查（不需要 secrets）
4. 代码审查通过后合并
5. 合并到 `deploy` 分支触发完整部署

### 紧急部署
```bash
# 直接推送到 deploy 分支
git push origin HEAD:deploy
```

### 测试连接
```bash
# 可以随时在 GitHub Actions 界面手动触发
# Ansible Connection Test 工作流
```
