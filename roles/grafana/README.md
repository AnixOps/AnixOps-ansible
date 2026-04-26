# Grafana Server Role

部署 Grafana 可视化平台

## 功能

- 安装 Grafana 服务器
- 自动配置 Prometheus 和 Loki 数据源
- 导入预定义仪表盘
- 可选 SSL/TLS 支持

## 变量

```yaml
grafana_version: "10.0.0"
grafana_port: 3000
grafana_admin_password: "admin"  # 首次登录后修改
```
