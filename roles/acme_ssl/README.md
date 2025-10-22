# ACME SSL Certificate Role

使用 ACME.sh 自动获取和续期 SSL 证书

## 功能

- 安装 acme.sh
- 支持多种验证方式（HTTP-01, DNS-01）
- 自动续期证书
- Cloudflare DNS API 支持

## 变量

```yaml
acme_email: "admin@example.com"
acme_ca_server: "letsencrypt"  # 或 letsencrypt_test
acme_domains: []
acme_dns_provider: "cloudflare"  # 可选
```
