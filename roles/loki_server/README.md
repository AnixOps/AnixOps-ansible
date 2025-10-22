# Loki Server Role

部署 Loki 日志聚合服务器

## 功能

- 安装 Loki 服务器
- 配置日志保留策略
- 可选 SSL/TLS 支持（通过 Nginx 反向代理）

## 变量

```yaml
loki_version: "2.9.0"
loki_port: 3100
loki_data_dir: "/var/lib/loki"
```
