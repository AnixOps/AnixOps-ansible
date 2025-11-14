# 静态网站部署指南 | Static Website Deployment Guide

## 快速开始 | Quick Start

### 1. 准备 SSL 证书 | Prepare SSL Certificates

从 Cloudflare 获取 Origin 证书:

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 选择你的域名
3. 进入 **SSL/TLS** → **Origin Server**
4. 点击 **Create Certificate**
5. 保存证书和私钥

### 2. 配置环境变量 | Configure Environment Variables

```bash
# 将证书内容进行 base64 编码
export CF_SSL_CERT="$(cat origin-certificate.pem | base64 -w 0)"
export CF_SSL_KEY="$(cat origin-private-key.pem | base64 -w 0)"

# 可选：自定义域名（默认: test-web-ansible.anixops.com）
export STATIC_SITE_DOMAIN="my-site.anixops.com"
```

### 3. 部署 | Deploy

```bash
# 方式 1: 使用 Makefile（推荐）
make deploy-static-web

# 方式 2: 直接使用 ansible-playbook
ansible-playbook -i inventory/hosts.yml playbooks/deployment/deploy-static-web.yml
```

### 4. 验证部署 | Verify Deployment

```bash
# 测试后端服务器
curl -I http://127.0.0.1:8080

# 测试反向代理（本地测试，需要配置 hosts）
curl -I https://test-web-ansible.anixops.com

# 查看 Nginx 状态
sudo systemctl status nginx

# 查看日志
sudo tail -f /var/log/nginx/test-web-ansible-*.log
```

## 架构说明 | Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    DNS Resolution
          test-web-ansible.anixops.com → Server IP
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Nginx Reverse Proxy                         │
│  - Port 443 (HTTPS) with SSL/TLS                            │
│  - Port 80 (HTTP) → 301 Redirect to HTTPS                  │
│  - Cloudflare Origin Certificate                            │
│  - Security Headers                                          │
│  - WebSocket Support                                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    Proxy Pass
                  http://127.0.0.1:8080
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Nginx Backend Server                        │
│  - Port 8080 (Local only)                                   │
│  - Serves Static Content                                     │
│  - Health Check Endpoint: /health                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    File System
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Static Files                                    │
│  /var/www/test-web-ansible/                                 │
│  ├── index.html                                             │
│  └── health                                                  │
└─────────────────────────────────────────────────────────────┘
```

## 配置文件位置 | Configuration Files

### Nginx 配置

```bash
# 后端服务器配置
/etc/nginx/sites-available/test-web-ansible-backend
/etc/nginx/sites-enabled/test-web-ansible-backend

# 反向代理配置
/etc/nginx/sites-available/test-web-ansible-proxy
/etc/nginx/sites-enabled/test-web-ansible-proxy
```

### SSL 证书

```bash
# SSL 证书位置
/etc/nginx/ssl/test-web-ansible.anixops.com.crt
/etc/nginx/ssl/test-web-ansible.anixops.com.key
```

### 网站文件

```bash
# 网站根目录
/var/www/test-web-ansible/
├── index.html
└── health
```

### 日志文件

```bash
# 后端日志
/var/log/nginx/test-web-ansible-backend-access.log
/var/log/nginx/test-web-ansible-backend-error.log

# 反向代理日志
/var/log/nginx/test-web-ansible-access.log
/var/log/nginx/test-web-ansible-error.log
```

## 自定义配置 | Custom Configuration

### 修改反向代理配置

编辑 `vars/reverse_proxy_configs.yml`:

```yaml
reverse_proxy_sites:
  - name: my-custom-site
    domain: my-site.anixops.com
    backend_host: 127.0.0.1
    backend_port: 8080
    ssl_enabled: true
    ssl_method: custom
    description: "My Custom Site"
```

### 修改静态网站内容

编辑模板 `roles/nginx/templates/static-site.html.j2` 或在 playbook 中设置变量:

```yaml
vars:
  site_title: "My Custom Title"
  site_description: "My Custom Description"
```

## DNS 配置 | DNS Configuration

在 Cloudflare 中添加 DNS 记录:

1. 登录 Cloudflare Dashboard
2. 选择域名
3. 进入 **DNS** 管理
4. 添加 A 记录:
   - **Name**: `test-web-ansible` 或你的子域名
   - **IPv4 address**: 你的服务器 IP
   - **Proxy status**: 启用（橙色云朵）或禁用（灰色云朵）
   - **TTL**: Auto

## 安全配置 | Security Configuration

### SSL/TLS 模式（Cloudflare）

推荐设置:
- **SSL/TLS encryption mode**: Full (strict)
- 使用 Origin Certificate 确保端到端加密

### 防火墙规则

```bash
# 允许 HTTP 和 HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 确保后端端口不对外开放
sudo ufw status | grep 8080  # 应该没有规则
```

### 安全头部

反向代理自动配置以下安全头部:
- `Strict-Transport-Security`: 强制 HTTPS
- `X-Frame-Options`: 防止点击劫持
- `X-Content-Type-Options`: 防止 MIME 类型嗅探
- `X-XSS-Protection`: XSS 保护

## 故障排除 | Troubleshooting

### 问题 1: 502 Bad Gateway

**原因**: 后端服务未运行

**解决**:
```bash
# 检查后端是否监听
sudo ss -tlnp | grep 8080

# 检查 Nginx 配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### 问题 2: SSL 证书错误

**原因**: 证书未正确部署

**解决**:
```bash
# 检查证书文件
ls -l /etc/nginx/ssl/

# 检查证书内容
sudo openssl x509 -in /etc/nginx/ssl/test-web-ansible.anixops.com.crt -text -noout

# 重新部署
export CF_SSL_CERT="$(cat cert.pem | base64 -w 0)"
export CF_SSL_KEY="$(cat key.pem | base64 -w 0)"
make deploy-static-web
```

### 问题 3: DNS 无法解析

**原因**: DNS 记录未正确配置

**解决**:
```bash
# 检查 DNS 解析
dig test-web-ansible.anixops.com
nslookup test-web-ansible.anixops.com

# 本地测试（添加到 /etc/hosts）
echo "SERVER_IP test-web-ansible.anixops.com" | sudo tee -a /etc/hosts
```

### 问题 4: WebSocket 连接失败

**原因**: Nginx 未配置 WebSocket 支持

**解决**:
```bash
# 检查 nginx.conf
grep "map.*http_upgrade" /etc/nginx/nginx.conf

# 如果缺失，重新运行 playbook
make deploy-static-web
```

## 性能优化 | Performance Optimization

### 启用缓存

在反向代理配置中添加缓存:

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=static_cache:10m max_size=1g;
proxy_cache static_cache;
proxy_cache_valid 200 1h;
```

### 启用 Gzip 压缩

在 Nginx 主配置中启用:

```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript;
gzip_min_length 1000;
```

## 监控和日志 | Monitoring and Logging

### 实时监控

```bash
# 实时查看访问日志
sudo tail -f /var/log/nginx/test-web-ansible-access.log

# 实时查看错误日志
sudo tail -f /var/log/nginx/test-web-ansible-error.log

# 统计访问量
sudo tail -1000 /var/log/nginx/test-web-ansible-access.log | wc -l
```

### 日志分析

```bash
# 查看最常访问的 URL
sudo awk '{print $7}' /var/log/nginx/test-web-ansible-access.log | sort | uniq -c | sort -rn | head -10

# 查看访问 IP
sudo awk '{print $1}' /var/log/nginx/test-web-ansible-access.log | sort | uniq -c | sort -rn | head -10

# 查看 HTTP 状态码
sudo awk '{print $9}' /var/log/nginx/test-web-ansible-access.log | sort | uniq -c | sort -rn
```

## 扩展功能 | Advanced Features

### 添加更多静态网站

1. 编辑 `vars/reverse_proxy_configs.yml`
2. 添加新的配置项
3. 重新运行 playbook

### 集成 Let's Encrypt

修改配置使用 ACME:

```yaml
ssl_enabled: true
ssl_method: acme  # 改为 acme
```

### 添加基本认证

在反向代理配置中添加:

```nginx
auth_basic "Restricted Access";
auth_basic_user_file /etc/nginx/.htpasswd;
```

## 相关文档 | Related Documentation

- [Role README](../roles/static_web_deploy/README.md)
- [反向代理配置](../vars/reverse_proxy_configs.yml)
- [Nginx 官方文档](https://nginx.org/en/docs/)
- [Cloudflare SSL/TLS 文档](https://developers.cloudflare.com/ssl/)

## 支持 | Support

如有问题，请:
1. 查看日志文件
2. 运行 `sudo nginx -t` 检查配置
3. 查看 [故障排除](#故障排除--troubleshooting) 部分
4. 提交 Issue 到 GitHub 仓库
