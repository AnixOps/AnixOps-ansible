# Prometheus Server Role

部署 Prometheus 监控服务器

## 功能

- 安装 Prometheus 服务器
- 配置监控目标（自动发现）
- 设置告警规则
- 可选 SSL/TLS 支持（通过 Nginx 反向代理）

## 变量

```yaml
prometheus_version: "2.45.0"
prometheus_port: 9090
prometheus_data_dir: "/var/lib/prometheus"
```
