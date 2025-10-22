# 可观测性栈部署指南

本指南说明如何部署 Prometheus + Loki + Grafana (PLG) 可观测性栈。

## 目录

- [概述](#概述)
- [前置要求](#前置要求)
- [SSL/TLS 配置](#ssltls-配置)
- [快速开始](#快速开始)
- [Cloudflare DNS 管理](#cloudflare-dns-管理)
- [常见问题](#常见问题)

## 概述

可观测性栈包含三个核心组件：

- **Prometheus**: 监控指标收集和存储
- **Loki**: 日志聚合和查询
- **Grafana**: 统一可视化仪表盘

支持的部署模式：

1. **HTTP 模式**：无加密，适用于内网或开发环境
2. **HTTPS + ACME.sh**：自动获取 Let's Encrypt 证书
3. **HTTPS + Cloudflare**：使用 Cloudflare API 获取证书并管理 DNS

## 前置要求

### 基础要求

- 一台专用服务器（建议 4GB+ 内存）
- Linux 操作系统（Ubuntu 20.04+ / Debian 11+ / CentOS 8+）
- 已配置 Ansible 控制节点
- SSH 密钥已部署到目标服务器

### SSL/TLS 要求（可选）

#### 方式 1: ACME.sh (Let's Encrypt)

- 可公网访问的域名
- 域名已解析到服务器 IP
- 80/443 端口可访问

#### 方式 2: Cloudflare

- Cloudflare 账户
- 域名托管在 Cloudflare
- Cloudflare API Token 或 Global API Key

## SSL/TLS 配置

### 选项 1: 不使用 SSL（默认）

适用于内网或开发环境。

```bash
# .env 配置
OBSERVABILITY_SSL_ENABLED=false
```

访问地址：
- Grafana: `http://<server-ip>:3000`
- Prometheus: `http://<server-ip>:9090`
- Loki: `http://<server-ip>:3100`

### 选项 2: ACME.sh (Let's Encrypt)

自动获取免费 SSL 证书。

#### 配置步骤

1. **编辑 .env 文件**：

```bash
# 启用 SSL
OBSERVABILITY_SSL_ENABLED=true
OBSERVABILITY_SSL_METHOD=acme

# 配置域名
GRAFANA_DOMAIN=grafana.yourdomain.com
PROMETHEUS_DOMAIN=prometheus.yourdomain.com
LOKI_DOMAIN=loki.yourdomain.com

# ACME 配置
ACME_EMAIL=your-email@example.com
ACME_CA_SERVER=letsencrypt  # 生产环境
# ACME_CA_SERVER=letsencrypt_test  # 测试环境（推荐先测试）
```

2. **DNS 解析**：

确保域名已正确解析到服务器 IP：

```bash
dig +short grafana.yourdomain.com
# 应返回服务器 IP
```

3. **部署**：

```bash
./scripts/anixops.sh observability
```

#### ACME.sh 工作流程

1. 在服务器上安装 acme.sh
2. 使用 HTTP-01 验证方式获取证书
3. 配置 Nginx 反向代理启用 HTTPS
4. 自动设置证书续期（60 天检查一次）

访问地址：
- Grafana: `https://grafana.yourdomain.com`
- Prometheus: `https://prometheus.yourdomain.com`
- Loki: `https://loki.yourdomain.com`

### 选项 3: Cloudflare SSL

使用 Cloudflare API 管理 DNS 和证书。

#### 优势

- 自动 DNS 管理
- DNS-01 验证（无需开放 80/443 端口）
- 可选 Cloudflare 代理（CDN/DDoS 防护）
- 更快的证书签发

#### 配置步骤

1. **获取 Cloudflare API Token**：

登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) → My Profile → API Tokens

创建 Token，权限：
- Zone - DNS - Edit
- Zone - Zone - Read

或使用 Global API Key（不推荐）。

2. **编辑 .env 文件**：

```bash
# 启用 SSL
OBSERVABILITY_SSL_ENABLED=true
OBSERVABILITY_SSL_METHOD=cloudflare

# 配置域名
GRAFANA_DOMAIN=grafana.yourdomain.com
PROMETHEUS_DOMAIN=prometheus.yourdomain.com
LOKI_DOMAIN=loki.yourdomain.com

# Cloudflare 认证（选择一种）
# 方式 1: API Token (推荐)
CLOUDFLARE_API_TOKEN=your-api-token-here
CLOUDFLARE_ZONE_ID=your-zone-id-here

# 方式 2: Global API Key (备选)
CLOUDFLARE_EMAIL=your-email@example.com
CLOUDFLARE_API_KEY=your-global-api-key
CLOUDFLARE_ZONE_ID=your-zone-id-here
```

3. **（可选）自动配置 DNS**：

```bash
# 从 .env 批量创建 DNS 记录
./scripts/anixops.sh cf-setup

# 手动创建单个记录
python3 tools/cloudflare_manager.py upsert \
  -z $CLOUDFLARE_ZONE_ID \
  -n grafana.yourdomain.com \
  -c <服务器IP> \
  --proxy  # 启用小黄云代理
```

4. **部署可观测性栈**：

```bash
./scripts/anixops.sh observability
```

#### Cloudflare 代理（小黄云加速）

Cloudflare 代理提供：
- 全球 CDN 加速
- DDoS 防护
- 自动 SSL/TLS
- 流量分析

**启用代理**：

```bash
# 启用 Grafana 代理
./scripts/anixops.sh cf-proxy-on grafana.yourdomain.com

# 启用所有服务代理
./scripts/anixops.sh cf-proxy-on grafana.yourdomain.com
./scripts/anixops.sh cf-proxy-on prometheus.yourdomain.com
./scripts/anixops.sh cf-proxy-on loki.yourdomain.com
```

**禁用代理**：

```bash
./scripts/anixops.sh cf-proxy-off grafana.yourdomain.com
```

**注意事项**：

- 启用代理后，Cloudflare 会缓存静态资源
- Grafana/Prometheus/Loki 的实际 IP 会被隐藏
- WebSocket 连接可能需要额外配置
- 适合公网暴露的服务；内网使用建议禁用代理

## 快速开始

### 1. 准备 Inventory

编辑 `inventory/hosts.yml`，添加可观测性服务器组：

```yaml
all:
  children:
    observability:
      hosts:
        obs-server-1:
          ansible_host: "{{ lookup('env', 'OBS_1_V4') | regex_replace('/.*', '') }}"
          internal_ip: "{{ lookup('env', 'OBS_1_V4') | regex_replace('/.*', '') }}"
```

在 `.env` 中配置服务器 IP：

```bash
OBS_1_V4=203.0.113.100/31
```

### 2. 选择 SSL 模式

根据需求编辑 `.env`（参见上面的 SSL 配置章节）。

### 3. 配置 Grafana 认证（可选）

默认情况下，Grafana 使用 `admin/admin` 作为初始凭据。你可以在 `.env` 中自定义：

```bash
# Grafana 认证配置
GRAFANA_ADMIN_USER=admin                     # 管理员用户名
GRAFANA_ADMIN_PASSWORD=YourSecurePassword    # 管理员密码
```

**注意**：
- 如果不配置 `GRAFANA_ADMIN_PASSWORD`，将使用默认密码 `admin`
- 建议在生产环境中设置强密码
- 配置的密码会在部署时直接设置，无需首次登录后修改

### 4. 部署

```bash
# 完整部署
./scripts/anixops.sh observability

# 仅部署特定组件
./scripts/anixops.sh observability --tags prometheus
./scripts/anixops.sh observability --tags loki
./scripts/anixops.sh observability --tags grafana
```

### 5. 访问服务

部署完成后，根据配置访问：

**HTTP 模式**：
```
Grafana: http://<server-ip>:3000
Prometheus: http://<server-ip>:9090
Loki: http://<server-ip>:3100
```

**HTTPS 模式**：
```
Grafana: https://grafana.yourdomain.com
Prometheus: https://prometheus.yourdomain.com
Loki: https://loki.yourdomain.com
```

**登录凭据**：
- 用户名: 使用 `.env` 中配置的 `GRAFANA_ADMIN_USER`（默认 `admin`）
- 密码: 使用 `.env` 中配置的 `GRAFANA_ADMIN_PASSWORD`（默认 `admin`）

如果使用默认密码，建议登录后立即修改。

### 6. 配置数据源

Grafana 会自动配置 Prometheus 和 Loki 数据源。验证：

1. 登录 Grafana
2. 左侧菜单 → Configuration → Data Sources
3. 检查 Prometheus 和 Loki 状态

### 6. 导入仪表盘

预定义的仪表盘位于 `observability/grafana/dashboards/`：

1. Grafana → Dashboards → Import
2. 上传 JSON 文件或使用仪表盘 ID
3. 选择 Prometheus 数据源

推荐仪表盘：
- Node Exporter Full（ID: 1860）
- Loki Dashboard（ID: 13639）

## Cloudflare DNS 管理

### 命令行工具

`tools/cloudflare_manager.py` 提供完整的 DNS 管理功能。

#### 查看所有区域

```bash
python3 tools/cloudflare_manager.py zones
```

#### 列出 DNS 记录

```bash
python3 tools/cloudflare_manager.py list -z $CLOUDFLARE_ZONE_ID
```

#### 创建 DNS 记录

```bash
# 基本 A 记录
python3 tools/cloudflare_manager.py add \
  -z $CLOUDFLARE_ZONE_ID \
  -n www.example.com \
  -c 1.2.3.4

# 启用代理（小黄云）
python3 tools/cloudflare_manager.py add \
  -z $CLOUDFLARE_ZONE_ID \
  -n www.example.com \
  -c 1.2.3.4 \
  --proxy
```

#### 更新 DNS 记录

```bash
python3 tools/cloudflare_manager.py upsert \
  -z $CLOUDFLARE_ZONE_ID \
  -n www.example.com \
  -c 1.2.3.5 \
  --proxy
```

#### 删除 DNS 记录

```bash
python3 tools/cloudflare_manager.py delete \
  -z $CLOUDFLARE_ZONE_ID \
  -n www.example.com
```

#### 切换代理状态

```bash
# 启用小黄云
python3 tools/cloudflare_manager.py proxy-on \
  -z $CLOUDFLARE_ZONE_ID \
  -n www.example.com

# 禁用小黄云
python3 tools/cloudflare_manager.py proxy-off \
  -z $CLOUDFLARE_ZONE_ID \
  -n www.example.com
```

#### 从环境变量批量配置

```bash
# 读取 .env 中的所有服务器配置，自动创建 DNS 记录
python3 tools/cloudflare_manager.py from-env -z $CLOUDFLARE_ZONE_ID
```

### Python API 示例

```python
from tools.cloudflare_manager import CloudflareManager

# 初始化
manager = CloudflareManager(api_token="your-token")

# 创建 DNS 记录并启用代理
manager.create_dns_record(
    zone_id="your-zone-id",
    record_type="A",
    name="grafana.example.com",
    content="1.2.3.4",
    proxied=True  # 启用小黄云
)

# 切换代理状态
manager.toggle_proxy(
    zone_id="your-zone-id",
    name="grafana.example.com",
    proxied=True  # 启用/禁用
)
```

## 常见问题

### Q1: ACME.sh 证书获取失败

**症状**：`Failed to verify domain ownership`

**解决方案**：

1. 确认域名已正确解析到服务器
2. 检查防火墙是否开放 80 端口
3. 使用测试环境验证：`ACME_CA_SERVER=letsencrypt_test`
4. 查看日志：`/root/.acme.sh/<domain>/acme.log`

### Q2: Cloudflare API 认证失败

**症状**：`API Error: Invalid credentials`

**解决方案**：

1. 验证 API Token 权限（Zone DNS Edit + Zone Read）
2. 检查 Zone ID 是否正确
3. 使用命令测试：`python3 tools/cloudflare_manager.py zones`

### Q3: 小黄云代理后无法访问

**症状**：启用代理后服务无响应

**解决方案**：

1. 检查 Cloudflare SSL/TLS 模式：Dashboard → SSL/TLS → 设置为 "Full" 或 "Full (strict)"
2. 确认服务器防火墙允许 Cloudflare IP 段
3. 临时禁用代理测试：`./scripts/anixops.sh cf-proxy-off <domain>`

### Q4: Grafana 无法连接数据源

**症状**：Prometheus/Loki 数据源显示红色

**解决方案**：

1. 检查服务状态：`systemctl status prometheus loki`
2. 验证端口监听：`netstat -tlnp | grep -E '(9090|3100)'`
3. 检查防火墙规则
4. 查看 Grafana 日志：`journalctl -u grafana-server -f`

### Q5: 证书续期失败

**症状**：HTTPS 证书过期

**解决方案**：

1. 手动续期：`/root/.acme.sh/acme.sh --renew -d <domain>`
2. 检查 cron 任务：`crontab -l | grep acme`
3. 查看续期日志：`/root/.acme.sh/acme.sh --list`

## 相关文档

- [Prometheus 官方文档](https://prometheus.io/docs/)
- [Loki 官方文档](https://grafana.com/docs/loki/)
- [Grafana 官方文档](https://grafana.com/docs/grafana/)
- [ACME.sh 使用指南](https://github.com/acmesh-official/acme.sh)
- [Cloudflare API 文档](https://developers.cloudflare.com/api/)

## 支持

如有问题，请访问：
- GitHub Issues: https://github.com/AnixOps/AnixOps-ansible/issues
- 文档: https://github.com/AnixOps/AnixOps-ansible/tree/main/docs
