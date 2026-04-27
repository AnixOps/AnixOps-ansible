# V2board Control Panel Role

部署 v2board 控制面板，用于管理 V2bX 代理节点。

## 依赖

- `cloudflare_mesh`: 为 V2bX 节点提供 Mesh IP 访问
- Docker: 自动安装

## 配置变量

| 变量 | 来源 | 说明 |
|------|------|------|
| `V2BOARD_DB_TYPE` | GitHub Secrets | 数据库类型 (sqlite/postgres) |
| `V2BOARD_PG_*` | GitHub Secrets | PostgreSQL 配置 |
| `V2BOARD_REDIS_*` | GitHub Secrets | Redis 配置 |
| `V2BOARD_JWT_SECRET` | GitHub Secrets | JWT 密钥 |
| `V2BOARD_API_KEY` | GitHub Secrets | API 密钥 |
| `V2BOARD_ADMIN_EMAIL` | GitHub Secrets | 管理员邮箱 |
| `V2BOARD_ADMIN_PASSWORD` | GitHub Secrets | 管理员密码 |
| `V2BOARD_MESH_IP` | GitHub Secrets | Mesh IP 地址 |
| `V2BOARD_REPO_OWNER` | GitHub Secrets | GitHub repo owner |

## 端口

| 端口 |用途 |
|------|------|
| 3000 |前端界面 |
| 8080 | API 端口 |
| 50051 | gRPC 端口 |
| 18081 | NodeX 端口 |

## 使用方法

### GitHub Actions

```yaml
workflow_dispatch:
  inputs:
    role: v2board
    target_group: v2board_servers
```

### 本地部署

```bash
ansible-playbook playbooks/provision/site.yml \
  --tags v2board \
  --limit v2board_servers
```

## 部署流程

1. 验证必需变量
2. 安装 Docker 和 Docker Compose
3. 创建 `/opt/v2board` 目录
4. 生成 `config.yaml` 和 `docker-compose.yml`
5. 启动 Docker 容器
6. 验证健康检查

## Mesh 通信

V2board 向 V2bX 提供 Mesh IP 访问:

- `V2BOARD_MESH_IP` 用于配置文件中标识
- V2bX 通过 Mesh IP `100.96.x.x:8080` 访问 API