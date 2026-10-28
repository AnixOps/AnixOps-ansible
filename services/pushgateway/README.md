# Pushgateway

JumpServer 作业模板 `pushgateway`。结构与其他服务相同：`main.yml` 为入口，`templates/` 与其同级。

## 变量（在 JumpServer 变量表里填写，JumpServer 会加上 `jms_` 前缀）

没有必需变量，也没有敏感变量。

| 变量 | 默认 | 说明 |
|---|---|---|
| `pushgateway_port` | `9091` | 宿主机端口 |
| `pushgateway_image_tag` | `v1.9.0` | 镜像版本 |
| `pushgateway_dir` | `/opt/pushgateway` | 部署目录 |
| `pushgateway_persistence_interval` | `5m` | 指标写入磁盘的间隔，重启后保留 |

## 使用

- 推送指标：`echo "job_duration_seconds 3.2" | curl --data-binary @- http://<地址>:9091/metrics/job/<任务名>`。
- 让 Prometheus 抓取它：在 `prometheus` 模板里设置 `prometheus_pushgateway_targets`（例如 `10.0.0.5:9091`）并重跑。该任务使用 `honor_labels: true`，保留推送时的 `job` 和 `instance` 标签。

## 注意

- Pushgateway 没有鉴权，只应在内网开放该端口（防火墙限制来源）。
- 它会一直保留最后一次推送的值，任务停止后不会自己清掉，需要时用 `curl -X DELETE http://<地址>:9091/metrics/job/<任务名>` 删除。
- 持久化目录 `data/` 属主为 65534（容器内的 nobody 用户）。
- 这次只做了语法检查，没有在真实主机上运行。
