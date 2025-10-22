# 自定义 SSL 证书配置指南

本指南说明如何使用自定义 SSL 证书（而不是 Let's Encrypt）来保护可观测性服务。

## 概述

使用自定义 SSL 证书的优势：
- ✅ 使用已有的商业 SSL 证书（如 Cloudflare Origin Certificate）
- ✅ 无需开放 80/443 端口用于 ACME 验证
- ✅ 支持内网环境和自签名证书
- ✅ 更快的部署速度（无需等待证书签发）

## 前置要求

### 1. SSL 证书文件

您需要以下两个 PEM 格式的文件：

- **证书文件** (`cert.pem` 或 `fullchain.pem`)：包含完整证书链
- **私钥文件** (`privkey.pem` 或 `key.pem`)：证书私钥

### 2. 证书要求

证书必须包含所有三个域名：
- `grafana.anixops.com`
- `prometheus.anixops.com`
- `loki.anixops.com`

可以使用：
- **通配符证书**：`*.anixops.com`
- **多域名证书**（SAN）：包含以上三个域名
- **三个单独的证书**（不推荐）

## 配置步骤

### 步骤 1: 获取 SSL 证书

#### 选项 A: Cloudflare Origin Certificate（推荐）

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 选择您的域名
3. 进入 **SSL/TLS** → **Origin Server**
4. 点击 **Create Certificate**
5. 配置：
   - **Hostnames**: 输入 `*.anixops.com` 或具体域名
   - **Validity**: 选择有效期（建议 15 年）
   - **Private key type**: RSA (2048)
6. 点击 **Create**
7. **复制并保存**：
   - Origin Certificate → 保存为 `cert.pem`
   - Private Key → 保存为 `privkey.pem`

#### 选项 B: 商业 SSL 证书

从 SSL 证书提供商（Let's Encrypt, DigiCert, Sectigo 等）获取证书。

#### 选项 C: 自签名证书（仅测试）

```bash
# 生成自签名通配符证书
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout privkey.pem \
  -out cert.pem \
  -days 365 \
  -subj "/CN=*.anixops.com" \
  -addext "subjectAltName=DNS:*.anixops.com,DNS:anixops.com"
```

### 步骤 2: 编码证书为 Base64

使用提供的工具脚本：

```bash
cd /root/code/AnixOps-ansible
./tools/encode_ssl_cert.sh /path/to/cert.pem /path/to/privkey.pem
```

脚本会输出 base64 编码的证书内容，并提供选项直接写入 `.env` 文件。

**手动编码**（可选）：

```bash
# 编码证书
cat cert.pem | base64 -w 0

# 编码私钥
cat privkey.pem | base64 -w 0
```

### 步骤 3: 配置 .env 文件

编辑 `/root/code/AnixOps-ansible/.env`：

```bash
# 启用 SSL
OBSERVABILITY_SSL_ENABLED=true
OBSERVABILITY_SSL_METHOD=custom

# 配置域名
GRAFANA_DOMAIN=grafana.anixops.com
PROMETHEUS_DOMAIN=prometheus.anixops.com
LOKI_DOMAIN=loki.anixops.com

# 粘贴 base64 编码的证书
SSL_CERTIFICATE_PEM=LS0tLS1CRUdJTi...（完整的 base64 字符串）...
SSL_CERTIFICATE_KEY_PEM=LS0tLS1CRUdJTi...（完整的 base64 字符串）...
```

### 步骤 4: 配置防火墙白名单（可选）

限制哪些 IP 可以直接访问服务端口：

```bash
# 允许特定 IP 访问
OBSERVABILITY_WHITELIST_IPS=1.2.3.4,5.6.7.8

# 或留空只允许本地访问
OBSERVABILITY_WHITELIST_IPS=

# 或允许所有 IP（不推荐）
OBSERVABILITY_WHITELIST_IPS=any
```

### 步骤 5: 部署

```bash
cd /root/code/AnixOps-ansible/scripts
./anixops.sh observability
```

## 访问服务

部署完成后，通过 HTTPS 访问：

- **Grafana**: https://grafana.anixops.com
- **Prometheus**: https://prometheus.anixops.com
- **Loki**: https://loki.anixops.com

## 防火墙规则

部署后的防火墙配置：

| 端口 | 服务 | 访问权限 |
|------|------|----------|
| 22   | SSH  | 所有 IP |
| 80   | HTTP | 所有 IP（用于 HTTP 重定向） |
| 443  | HTTPS | 所有 IP |
| 9090 | Prometheus | 白名单 IP + localhost |
| 3100 | Loki | 白名单 IP + localhost |
| 3000 | Grafana | 白名单 IP + localhost |
| 9100 | Node Exporter | 白名单 IP + localhost |

**说明**：
- 所有服务通过 Nginx 反向代理，使用 HTTPS (443) 访问
- 直接端口访问受防火墙限制，只允许白名单 IP
- Prometheus 通过 localhost 访问其他服务（无需开放端口）

## 证书更新

证书到期前，重新执行以下步骤：

1. 获取新证书
2. 使用 `encode_ssl_cert.sh` 编码
3. 更新 `.env` 文件中的 `SSL_CERTIFICATE_PEM` 和 `SSL_CERTIFICATE_KEY_PEM`
4. 重新部署或仅更新 SSL：

```bash
./anixops.sh observability --tags ssl,nginx
```

## 故障排查

### 证书验证失败

```bash
# 在服务器上验证证书
openssl x509 -in /etc/nginx/ssl/grafana.anixops.com.crt -noout -text

# 检查证书域名
openssl x509 -in /etc/nginx/ssl/grafana.anixops.com.crt -noout -subject -ext subjectAltName
```

### Base64 解码测试

```bash
# 测试证书是否正确编码
echo "YOUR_BASE64_STRING" | base64 -d | openssl x509 -noout -text
```

### Nginx 配置测试

```bash
# 测试 Nginx 配置
nginx -t

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log
```

### 防火墙规则检查

```bash
# 查看 UFW 状态
ufw status verbose

# 测试端口连接
nc -zv localhost 9090
nc -zv localhost 3000
```

## 安全建议

1. **证书安全**：
   - 不要将 `.env` 文件提交到 Git
   - 定期更换证书
   - 使用强加密算法（RSA 2048+ 或 ECDSA）

2. **防火墙**：
   - 生产环境必须配置白名单
   - 定期审计防火墙规则
   - 考虑使用 VPN 或专用网络

3. **访问控制**：
   - 为 Grafana 设置强密码
   - 考虑为 Prometheus/Loki 添加基本认证
   - 启用 Grafana 的双因素认证

## 相关文档

- [可观测性栈部署指南](OBSERVABILITY_SETUP.md)
- [防火墙配置指南](FIREWALL_SETUP.md)
- [Cloudflare Origin Certificate 文档](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/)
