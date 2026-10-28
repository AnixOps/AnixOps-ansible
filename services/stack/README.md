# Monitoring stack | 监控全量安装

JumpServer 作业模板 `stack`：一次作业装好 Prometheus、Pushgateway、Grafana，并可选 node_exporter。
结构：`main.yml` 为入口，`templates/` 与 `files/` 与其同级。

它们在同一个 compose 项目里，共用一个 Docker 网络：

- Grafana 通过 `http://prometheus:9090` 访问 Prometheus，数据源已自动配置，**不需要填任何地址**。
- Prometheus 通过 `pushgateway:9091` 抓取 Pushgateway（`honor_labels: true`）。
- node_exporter 运行在宿主机网络上，Prometheus 通过 `host.docker.internal:9100` 抓取它。

## 变量（在 JumpServer 变量表里填写，JumpServer 会加上 `jms_` 前缀；全部可选）

| 变量 | 默认 | 说明 |
|---|---|---|
| `stack_dir` | `/opt/stack` | 部署目录 |
| `stack_grafana_port` | `3000` | Grafana 宿主机端口 |
| `stack_prometheus_port` | `9090` | Prometheus 宿主机端口 |
| `stack_pushgateway_port` | `9091` | Pushgateway 宿主机端口 |
| `stack_node_exporter_port` | `9100` | node_exporter 端口 |
| `stack_node_exporter_enabled` | `true` | 是否在宿主机上运行 node_exporter（面板需要它） |
| `stack_scrape_targets` | 空 | 额外的 node_exporter 目标，逗号分隔的 `host:port` |
| `stack_retention` | `30d` | Prometheus 指标保留时长 |
| `stack_grafana_admin_user` | `admin` | Grafana 管理员用户名 |
| `stack_grafana_admin_password` | 空 | 只用于**创建** `<stack_dir>/.env`；该文件已存在时永远不会被覆盖 |

## Grafana 管理员密码

JumpServer 传敏感参数时可能给出掩码（`********`），所以密码不强制通过参数传入：

1. 推荐：在主机上先创建一次 `/opt/stack/.env`（root，权限 0600）：
   ```bash
   sudo install -d -m 0755 /opt/stack
   sudo sh -c 'umask 077; printf "GRAFANA_ADMIN_USER=admin\nGRAFANA_ADMIN_PASSWORD=%s\n" "<密码>" > /opt/stack/.env'
   ```
   然后**不要**定义 `stack_grafana_admin_password` 变量。
2. 或者通过变量传入合法密码，剧本只在 `.env` 不存在时用它创建文件。纯星号会被拒绝。

没有 `.env` 又没有合法密码时，作业在第一步就失败并说明原因。Grafana 只在**第一次启动（数据卷为空）**时读取密码，之后改 `.env` 不会改变已有密码，需要用
`docker exec <grafana容器> grafana cli admin reset-admin-password '<新密码>'`。

## 清空并重装（测试用）

```bash
cd /opt/stack && sudo docker compose down -v   # 删除容器和数据卷（Grafana、Prometheus 的数据都会丢失）
```

然后重新运行作业。不要用 `docker volume prune`。

## 注意

- 同一台机器上已经单独部署了 `grafana`、`prometheus`、`pushgateway` 模板时，端口会冲突，请先清理旧的或者换端口。
- Prometheus、Pushgateway、node_exporter 都没有鉴权，请用防火墙只对内网开放这些端口。node_exporter 监听在 `0.0.0.0`，因为 Prometheus 容器需要通过宿主网关访问它。
- 容器启动是否“变化”按 compose 的实际输出判断（有容器被创建、启动、重建或镜像被拉取才算 changed）。
- 这次只做了语法检查、模板渲染和断言逻辑验证，没有在真实主机上运行过完整部署。
