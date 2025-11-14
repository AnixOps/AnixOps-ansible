# Static Web Deploy Role

## 概述 | Overview

此 Role 用于在服务器上部署静态网站，并配置 Nginx 反向代理和 SSL 证书。

This role deploys static websites on servers with Nginx reverse proxy and SSL certificate configuration.

## 功能 | Features

- ✅ 部署静态网站内容
- ✅ 配置 Nginx 作为后端服务器（监听指定端口）
- ✅ 配置 Nginx 反向代理（可选）
- ✅ 支持 SSL/TLS（使用 Cloudflare 证书或 Let's Encrypt）
- ✅ 自动配置健康检查端点
- ✅ 支持 WebSocket 连接
- ✅ 安全头部配置

## 使用方法 | Usage

### 基本部署 | Basic Deployment

```bash
# 部署到 dev_servers
ansible-playbook -i inventory/hosts.yml playbooks/deployment/deploy-static-web.yml

# 或使用 Makefile
make deploy-static-web
```

### 环境变量配置 | Environment Variables

```bash
# SSL 证书（必需，如果启用 SSL）
export CF_SSL_CERT="$(cat certificate.pem | base64 -w 0)"
export CF_SSL_KEY="$(cat private-key.pem | base64 -w 0)"

# 可选：自定义域名
export STATIC_SITE_DOMAIN="my-site.example.com"

# 部署
make deploy-static-web
```

## 变量说明 | Variables

### 默认变量 (defaults/main.yml)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `static_site_name` | `test-web-ansible` | 网站名称 |
| `static_site_port` | `8080` | 后端监听端口 |
| `static_site_root` | `/var/www/{{ static_site_name }}` | 网站根目录 |
| `static_site_domain` | `{{ static_site_name }}.anixops.com` | 域名 |
| `enable_reverse_proxy` | `true` | 是否启用反向代理 |
| `ssl_enabled` | `true` | 是否启用 SSL |
| `ssl_method` | `custom` | SSL 证书方式: `custom` 或 `acme` |
| `site_title` | `AnixOps 测试静态网站` | 网站标题 |
| `site_description` | `Ansible 自动化部署...` | 网站描述 |

### SSL 配置

SSL 证书通过 `vars/reverse_proxy_configs.yml` 中的 `ssl_config` 配置：

```yaml
ssl_config:
  certificate_pem: "{{ lookup('env', 'CF_SSL_CERT') }}"
  certificate_key_pem: "{{ lookup('env', 'CF_SSL_KEY') }}"
  certificate_dir: /etc/nginx/ssl
  protocols: "TLSv1.2 TLSv1.3"
  ciphers: "ECDHE-ECDSA-AES128-GCM-SHA256:..."
```

## 架构说明 | Architecture

### 部署架构

```
Internet
    ↓
[Nginx Reverse Proxy]  ← HTTPS (443) / HTTP (80)
    ↓
[Nginx Backend Server] ← HTTP (8080)
    ↓
[Static Files]         ← /var/www/test-web-ansible/
```

### 文件结构

```
/var/www/test-web-ansible/
├── index.html          # 主页
└── health              # 健康检查端点

/etc/nginx/
├── sites-available/
│   ├── test-web-ansible-backend   # 后端配置
│   └── test-web-ansible-proxy     # 反向代理配置
├── sites-enabled/
│   ├── test-web-ansible-backend → sites-available/...
│   └── test-web-ansible-proxy → sites-available/...
└── ssl/
    ├── test-web-ansible.anixops.com.crt
    └── test-web-ansible.anixops.com.key
```

## 任务说明 | Tasks

### 主任务 (tasks/main.yml)

1. 安装 Nginx
2. 创建网站根目录
3. 部署静态网站内容
4. 配置 Nginx 后端服务器
5. 调用反向代理配置（如果启用）
6. 启动和启用 Nginx 服务
7. 健康检查

### 反向代理任务 (tasks/setup_reverse_proxy.yml)

1. 创建 SSL 证书目录
2. 部署 SSL 证书（base64 解码）
3. 配置 WebSocket 支持
4. 部署后端 Nginx 配置
5. 部署反向代理 Nginx 配置
6. 测试 Nginx 配置
7. 重新加载 Nginx

## 模板说明 | Templates

### static-site.html.j2

美观的静态网站首页模板，包含：
- 响应式设计
- 服务器信息显示
- SSL 状态显示
- 部署时间戳
- 健康状态指示

### static-site-nginx.conf.j2

Nginx 后端服务器配置：
- 监听指定端口（默认 8080）
- 提供静态文件服务
- 健康检查端点
- 访问日志和错误日志

### reverse-proxy.conf.j2

Nginx 反向代理配置：
- HTTP 到 HTTPS 重定向
- SSL/TLS 配置
- 安全头部
- WebSocket 支持
- 代理设置和超时配置

## 测试 | Testing

### 本地测试

```bash
# 测试后端
curl -I http://127.0.0.1:8080
curl http://127.0.0.1:8080/health

# 测试反向代理
curl -I https://test-web-ansible.anixops.com
curl https://test-web-ansible.anixops.com/health
```

### 健康检查

```bash
# 检查 Nginx 状态
sudo systemctl status nginx

# 检查 Nginx 配置
sudo nginx -t

# 查看日志
sudo tail -f /var/log/nginx/test-web-ansible-backend-access.log
sudo tail -f /var/log/nginx/test-web-ansible-access.log
```

## 故障排除 | Troubleshooting

### 问题 1: SSL 证书未部署

**症状**: Nginx 启动失败，提示找不到证书文件

**解决方案**:
```bash
# 检查证书环境变量
echo $CF_SSL_CERT | wc -c
echo $CF_SSL_KEY | wc -c

# 确保证书已正确 base64 编码
cat certificate.pem | base64 -w 0 > cert.b64
export CF_SSL_CERT="$(cat cert.b64)"
```

### 问题 2: 反向代理无法访问后端

**症状**: 502 Bad Gateway

**解决方案**:
```bash
# 检查后端是否运行
curl http://127.0.0.1:8080

# 检查 Nginx 错误日志
sudo tail -50 /var/log/nginx/test-web-ansible-error.log

# 检查防火墙
sudo ufw status
```

### 问题 3: WebSocket 连接失败

**症状**: WebSocket 升级失败

**解决方案**:
```bash
# 检查 nginx.conf 中的 map 配置
grep -A 3 "map \$http_upgrade" /etc/nginx/nginx.conf

# 手动添加（如果缺失）
sudo nginx -t
sudo systemctl reload nginx
```

## 依赖 | Dependencies

- Nginx
- Python 3
- Ansible 2.9+

## 标签 | Tags

- `static_web`: 静态网站部署
- `nginx`: Nginx 配置
- `reverse_proxy`: 反向代理配置

## 作者 | Author

AnixOps Team

## 许可证 | License

MIT
