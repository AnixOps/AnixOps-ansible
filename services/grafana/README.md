# Grafana

JumpServer 作业模板 `grafana` 的内容。文件夹结构要与 JumpServer 工作区一致：

```
grafana/
├── main.yml                      入口剧本
├── templates/                    env.j2, docker-compose.yml.j2, datasources.yml.j2, dashboards-provider.yml.j2
└── files/dashboards/             node-overview.json
```

## 变量（在 JumpServer 变量表里填写）

在变量表里填写下面的名称，JumpServer 会加上固定前缀 `jms_` 后交给剧本，例如 `grafana_admin_password` 在剧本中是 `jms_grafana_admin_password`。剧本内部已经做了映射，这里只需要填写不带前缀的名字。

| 变量 | 必需 | 默认 | 说明 |
|---|---|---|---|
| `grafana_admin_password` | 是 | - | 管理员密码（作为 secret 填写） |
| `grafana_prometheus_url` | 是 | - | Prometheus 地址，如 `http://10.0.0.5:9090` |
| `grafana_port` | 否 | `3000` | 宿主机端口 |
| `grafana_admin_user` | 否 | `admin` | 管理员用户名 |
| `grafana_image_tag` | 否 | `11.2.0` | Grafana 镜像版本 |

## 行为

- 按顺序安装 Docker（官方脚本）、写入配置、`docker compose up -d` 启动，最后检查 `/api/health`。
- 每次执行都会重新写入配置，因此修改变量后重跑即可生效。
- 仪表盘以只读方式通过文件 provisioning 加载，目录为 `AnixOps`。
- 运行前需要 Prometheus 已经能被 Grafana 所在机器访问，否则面板没有数据（健康检查不依赖它）。

## 注意

- 仓库内的文件需要手动复制到 JumpServer 的模板工作区。
- 这次没有在真实主机上运行过完整的部署，只做了语法检查。
- Prometheus 本身和 node_exporter 的安装不在本模板内。
