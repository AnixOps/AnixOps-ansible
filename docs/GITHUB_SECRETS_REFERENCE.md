# GitHub Secrets 配置参考

> 完整的 GitHub Secrets 配置指南 - v0.0.2

本文档列出了 AnixOps-ansible 项目中所有支持的 GitHub Secrets 配置项。

## 📋 目录

- [必需配置](#必需配置)
- [服务器 IP 配置](#服务器-ip-配置)
- [可观测性配置](#可观测性配置)
- [SSL/TLS 配置](#ssltls-配置)
- [Cloudflare 配置](#cloudflare-配置)
- [Grafana 认证配置](#grafana-认证配置)
- [防火墙配置](#防火墙配置)
- [配置步骤](#配置步骤)

---

## 必需配置

这些是运行 Ansible playbook 所必需的基础配置。

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `SSH_PRIVATE_KEY` | SSH 私钥内容 | `-----BEGIN RSA PRIVATE KEY-----\n...` | ✅ |
| `ANSIBLE_USER` | SSH 登录用户名 | `root` 或 `ubuntu` | ✅ |
| `ANSIBLE_PORT` | SSH 端口 | `22` | ✅ |

### 配置方法

#### SSH_PRIVATE_KEY

使用 `ssh_key_manager.py` 工具安全上传：

```bash
python tools/ssh_key_manager.py \
  --key-file ~/.ssh/id_rsa \
  --repo AnixOps/AnixOps-ansible \
  --token ghp_your_token_here \
  --secret-name SSH_PRIVATE_KEY
```

或通过 GitHub 网页界面：
1. 读取私钥内容：`cat ~/.ssh/id_rsa`
2. 复制完整内容（包括 BEGIN 和 END 行）
3. 在 GitHub 仓库 Settings → Secrets → Actions → New repository secret
4. Name: `SSH_PRIVATE_KEY`，Value: 粘贴私钥内容

---

## 服务器 IP 配置

根据你的服务器配置，设置对应的 IP 地址变量。

### 格式说明

- **点对点连接**（`/31` 或 `/127` 段）：只需配置 IP/掩码
- **其他网段**：需要同时配置 IP/掩码 和 SSH_IP

### 配置示例

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `US_W_1_V4` | 美西服务器1 IPv4 | `203.0.113.10/31` | 根据实际 |
| `US_W_1_V6` | 美西服务器1 IPv6 | `2001:db8::1/127` | 根据实际 |
| `US_W_2_V4` | 美西服务器2 IPv4 | `10.0.1.100/24` | 根据实际 |
| `US_W_2_V6` | 美西服务器2 IPv6 | `2001:db8:100::1/64` | 根据实际 |
| `US_W_2_SSH_IP` | 美西服务器2 SSH连接IP | `203.0.113.20` | ⚠️ 非/31段必需 |
| `US_E_1_V4` | 美东服务器 IPv4 | `203.0.113.30/31` | 根据实际 |
| `US_E_1_V6` | 美东服务器 IPv6 | `2001:db8::3/127` | 根据实际 |
| `JP_1_V4` | 日本服务器 IPv4 | `10.10.0.50/27` | 根据实际 |
| `JP_1_V6` | 日本服务器 IPv6 | `2001:db8:200::1/120` | 根据实际 |
| `JP_1_SSH_IP` | 日本服务器 SSH连接IP | `45.76.123.45` | ⚠️ 非/31段必需 |
| `EU_1_V4` | 欧洲服务器 IPv4 | `203.0.113.50/31` | 根据实际 |
| `EU_1_V6` | 欧洲服务器 IPv6 | `2001:db8::5/127` | 根据实际 |
| `DE_1_V4_SSH` | 德国测试服务器1 | `192.0.2.10` | 根据实际 |
| `PL_1_V4_SSH` | 波兰测试服务器1 | `192.0.2.20` | 根据实际 |

### 判断是否需要 SSH_IP

```bash
# 点对点连接 (/31 或 /127) - 不需要 SSH_IP
US_W_1_V4=203.0.113.10/31        # 直接 SSH 到这个 IP
US_W_1_V6=2001:db8::1/127

# 内网段 - 需要 SSH_IP
JP_1_V4=10.10.0.50/27            # 内网 IP，用于配置管理
JP_1_SSH_IP=45.76.123.45         # SSH 连接到这个公网 IP
```

---

## 可观测性配置

配置 Prometheus、Loki、Grafana 的访问地址。

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `PROMETHEUS_URL` | Prometheus 访问地址 | `http://prometheus.example.com:9090` | ⚠️ 部署监控时必需 |
| `LOKI_URL` | Loki 访问地址 | `http://loki.example.com:3100` | ⚠️ 部署日志时必需 |
| `GRAFANA_URL` | Grafana 访问地址 | `http://grafana.example.com:3000` | ⚠️ 部署 Grafana 时必需 |

---

## SSL/TLS 配置

为可观测性服务启用 HTTPS。

### 基础 SSL 配置

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `OBSERVABILITY_SSL_ENABLED` | 是否启用 SSL | `true` 或 `false` | 启用 SSL 时必需 |
| `OBSERVABILITY_SSL_METHOD` | SSL 证书方式 | `custom` 或 `acme` | 启用 SSL 时必需 |

### 域名配置（启用 SSL 时必需）

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `GRAFANA_DOMAIN` | Grafana 域名 | `grafana.example.com` | ✅ 启用 SSL 时 |
| `PROMETHEUS_DOMAIN` | Prometheus 域名 | `prometheus.example.com` | ✅ 启用 SSL 时 |
| `LOKI_DOMAIN` | Loki 域名 | `loki.example.com` | ✅ 启用 SSL 时 |

### 自定义 SSL 证书（SSL_METHOD=custom）

| Secret 名称 | 说明 | 必需 |
|------------|------|------|
| `SSL_CERTIFICATE_PEM` | SSL 证书（base64 编码） | ✅ custom 模式时 |
| `SSL_CERTIFICATE_KEY_PEM` | SSL 私钥（base64 编码） | ✅ custom 模式时 |

#### 生成 base64 编码的证书

```bash
# 编码证书
cat cert.pem | base64 -w 0 > cert_encoded.txt

# 编码私钥
cat key.pem | base64 -w 0 > key_encoded.txt

# 复制编码后的内容到 GitHub Secrets
```

或使用提供的工具：

```bash
./tools/encode_ssl_cert.sh cert.pem key.pem
```

### ACME.sh 配置（SSL_METHOD=acme）

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `ACME_EMAIL` | Let's Encrypt 通知邮箱 | `admin@example.com` | ✅ acme 模式时 |
| `ACME_CA_SERVER` | ACME CA 服务器 | `letsencrypt` 或 `letsencrypt_test` | ✅ acme 模式时 |

---

## Cloudflare 配置

用于 SSL 证书自动获取和 DNS 管理。

### 认证方式 1：API Token（推荐）

| Secret 名称 | 说明 | 必需 |
|------------|------|------|
| `CLOUDFLARE_API_TOKEN` | Cloudflare API Token | ✅ 使用 Cloudflare 时 |
| `CLOUDFLARE_ZONE_ID` | Zone ID | ✅ 使用 Cloudflare 时 |

#### 获取 API Token

1. 登录 Cloudflare Dashboard
2. 进入 "My Profile" → "API Tokens"
3. 创建 Token，权限：
   - Zone - DNS - Edit
   - Zone - Zone - Read
4. 复制 Token 到 `CLOUDFLARE_API_TOKEN`

#### 获取 Zone ID

1. 在 Cloudflare Dashboard 选择域名
2. 右侧 "API" 部分找到 "Zone ID"
3. 复制到 `CLOUDFLARE_ZONE_ID`

### 认证方式 2：Global API Key（备选）

| Secret 名称 | 说明 | 必需 |
|------------|------|------|
| `CLOUDFLARE_EMAIL` | Cloudflare 账户邮箱 | ✅ 使用 Global Key 时 |
| `CLOUDFLARE_API_KEY` | Global API Key | ✅ 使用 Global Key 时 |

### DNS 配置

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `CLOUDFLARE_BASE_DOMAIN` | 基础域名 | `example.com` | ✅ 使用 Cloudflare 时 |

---

## Grafana 认证配置

配置 Grafana 管理员账户。

| Secret 名称 | 说明 | 默认值 | 必需 |
|------------|------|--------|------|
| `GRAFANA_ADMIN_USER` | 管理员用户名 | `admin` | ❌ |
| `GRAFANA_ADMIN_PASSWORD` | 管理员密码 | `admin` | ❌ |

⚠️ **安全建议**：强烈建议设置强密码，不要使用默认值！

---

## 防火墙配置

配置可观测性服务端口的访问白名单。

| Secret 名称 | 说明 | 示例 | 必需 |
|------------|------|------|------|
| `FIREWALL_WHITELIST_IPS` | 白名单 IP 列表 | `1.2.3.4,5.6.7.8` | ❌ |

### 说明

- 多个 IP 用逗号分隔
- 留空则只允许本地（127.0.0.1）访问
- 控制以下端口的访问：
  - 9090（Prometheus）
  - 3100（Loki）
  - 3000（Grafana）
  - 9100（Node Exporter）

---

## 配置步骤

### 1. 通过 GitHub 网页界面

1. 进入仓库 Settings
2. 左侧菜单选择 "Secrets and variables" → "Actions"
3. 点击 "New repository secret"
4. 输入 Name 和 Value
5. 点击 "Add secret"

### 2. 使用 GitHub CLI

```bash
# 安装 GitHub CLI
# https://cli.github.com/

# 登录
gh auth login

# 添加 Secret
gh secret set SSH_PRIVATE_KEY < ~/.ssh/id_rsa
gh secret set ANSIBLE_USER -b "root"
gh secret set ANSIBLE_PORT -b "22"

# 批量添加
gh secret set US_W_1_V4 -b "203.0.113.10/31"
gh secret set PROMETHEUS_URL -b "http://prometheus.example.com:9090"
```

### 3. 使用脚本批量导入

创建一个 `.secrets` 文件（不要提交到 Git）：

```bash
SSH_PRIVATE_KEY=<从 ~/.ssh/id_rsa 读取>
ANSIBLE_USER=root
ANSIBLE_PORT=22
US_W_1_V4=203.0.113.10/31
PROMETHEUS_URL=http://prometheus.example.com:9090
```

批量导入：

```bash
while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" =~ ^# ]] && continue
  gh secret set "$key" -b "$value"
done < .secrets
```

---

## 验证配置

### 检查已配置的 Secrets

```bash
gh secret list
```

### 测试工作流

触发一个测试运行：

```bash
# 触发 lint 工作流
git commit --allow-empty -m "test: trigger workflow"
git push

# 手动触发 deploy 工作流
gh workflow run deploy.yml
```

---

## 安全最佳实践

1. ✅ **永远不要将 Secrets 提交到 Git**
2. ✅ **定期轮换 SSH 密钥和 API Token**
3. ✅ **使用最小权限原则**（只授予必需的权限）
4. ✅ **启用 GitHub 仓库的 2FA**
5. ✅ **审计 Actions 日志**，确保没有泄露敏感信息
6. ⚠️ **不要在工作流日志中打印 Secret 值**
7. ⚠️ **限制对仓库 Secrets 的访问权限**

---

## 故障排除

### Secret 未生效

1. 检查 Secret 名称是否拼写正确（区分大小写）
2. 重新触发工作流（有时需要重新运行）
3. 检查工作流文件中的引用是否正确：`${{ secrets.SECRET_NAME }}`

### SSH 连接失败

1. 验证 `SSH_PRIVATE_KEY` 格式正确
2. 确认 `ANSIBLE_USER` 和 `ANSIBLE_PORT` 设置正确
3. 检查服务器 IP 地址是否可达
4. 验证公钥已添加到服务器 `~/.ssh/authorized_keys`

### SSL 证书问题

1. 检查 base64 编码是否正确（无换行符）
2. 验证证书和私钥是否匹配
3. 确认域名 DNS 记录正确

---

## 相关文档

- 📖 [GitHub Actions 配置指南](GITHUB_ACTIONS_SETUP.md)
- 🔐 [SSH 密钥管理方案](SSH_KEY_MANAGEMENT.md)
- 📊 [可观测性部署指南](OBSERVABILITY_SETUP.md)
- 🔒 [自定义 SSL 设置](CUSTOM_SSL_SETUP.md)

---

**最后更新：** 2025-10-23  
**版本：** v0.0.2
