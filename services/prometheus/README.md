# Prometheus

JumpServer 作业模板 `prometheus`。结构与 `services/grafana` 相同：`main.yml` 为入口，`templates/` 与其同级。

## 变量（在 JumpServer 变量表里填写，JumpServer 会加上 `jms_` 前缀）

| 变量 | 必需 | 默认 | 说明 |
|---|---|---|---|
| `prometheus_port` | 否 | `9090` | 宿主机端口 |
| `prometheus_scrape_targets` | 否 | 空 | 逗号分隔的 node_exporter 地址，如 `10.0.0.11:9100,10.0.0.12:9100`；为空时只抓取 Prometheus 自身 |
| `prometheus_pushgateway_targets` | 否 | 空 | 逗号分隔的 Pushgateway 地址，如 `10.0.0.5:9091`；为空则不添加该抓取任务（使用 `honor_labels: true`） |
| `prometheus_retention` | 否 | `30d` | 指标保留时长 |
| `prometheus_image_tag` | 否 | `v2.54.1` | Prometheus 镜像版本 |
| `prometheus_dir` | 否 | `/opt/prometheus` | 部署目录 |

## 行为

- 安装 Docker，写入 compose 与配置，启动容器；配置变化时自动重启。
- 健康检查 `/-/ready`。

## 注意

- Grafana 的 `grafana_prometheus_url` 填 `http://<本机地址>:9090`（Grafana 与 Prometheus 在同一台机器时，地址填宿主机的内网 IP，而不是 `localhost`）。
- Prometheus 没有鉴权，请只在内网开放 `9090` 端口（例如通过防火墙限制来源）。
- 抓取目标需要各自运行 node_exporter（`:9100`），本模板不安装它。
- 这次只做了语法检查，没有在真实主机上运行。
