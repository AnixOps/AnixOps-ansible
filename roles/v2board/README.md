# V2board Control Panel Role

部署 v2board 控制面板（二进制部署），用于管理 V2bX 代理节点。

## 部署方式

**二进制部署**（Binary Deployment）：
- 从 GitHub Releases 或指定 URL 下载二进制文件
- systemd 服务管理
- 不依赖 Docker

## 配置变量

| Secret | 说明 |
|--------|------|
| `V2BOARD_API_TOKEN` | **内部 API 令牌**（用于 Ansible 自动化、V2bX 注册） |
| `V2BOARD_JWT_SECRET` | JWT 密钥（32+ 字符随机） |
| `V2BOARD_ADMIN_EMAIL` | 管理员邮箱 |
| `V2BOARD_ADMIN_PASSWORD` | 管理员密码 |
| `V2BOARD_MESH_IP` | 面板 Mesh IP |
| `V2BOARD_DB_TYPE` | 数据库类型（sqlite/postgres） |
| `V2BOARD_BINARY_URL` | 二进制下载 URL（可选，默认从 GitHub Releases） |
| `V2BOARD_PG_HOST` | PostgreSQL 地址（postgres 模式） |
| `V2BOARD_PG_PASSWORD` | PostgreSQL 密码 |
| `V2BOARD_REDIS_HOST` | Redis 地址 |
| `V2BOARD_REDIS_PASSWORD` | Redis 密码（可选） |

## API_TOKEN 用途

同一个 `V2BOARD_API_TOKEN` 用于：

1. **写入面板 config.yaml** → 面板启动后验证内部 API
2. **Ansible 调用面板 API** → 自动生成 AuthKey
3. **V2bX 部署时** → 调用面板 `/api/v2/internal/auth-keys`

## 端口

| 端口 | 用途 |
|------|------|
| 3000 | 前端界面 |
| 8080 | API 端口 |
| 50051 | gRPC 端口 |
| 18081 | NodeX 端口 |

## 部署流程

```
部署 v2board (API_TOKEN 写入 config.yaml)
↓
部署 V2bX (用 API_TOKEN 调用面板生成 AuthKey)
↓
V2bX 注册 (获取 node_id + ApiKey + Secret)
```

## GitHub Secrets 配置

```
V2BOARD_API_TOKEN=your-random-token-here
V2BOARD_JWT_SECRET=your-jwt-secret-32chars
V2BOARD_ADMIN_EMAIL=admin@example.com
V2BOARD_ADMIN_PASSWORD=your-password
V2BOARD_MESH_IP=100.96.0.5
```