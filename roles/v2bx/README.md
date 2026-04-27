# V2bX Proxy Node Role

部署 V2bX 代理节点，使用自动注册模式连接 v2board 控制面板。

## 依赖

- `cloudflare_mesh`: 通过 Mesh IP 与面板通信

## 自动注册模式

V2bX 使用 AuthKey 自动注册，无需预先在面板创建节点：

1. 管理员在 v2board 面板生成 AuthKey
2. Ansible 部署 V2bX 时传入 AuthKey
3. V2bX 启动时自动注册，获取 ApiKey + Secret
4. 凭证本地保存（可加密）

## 配置变量

| 变量 | 来源 | 说明 |
|------|------|------|
| `V2BX_AUTH_KEY` | GitHub Secrets | 一次性注册令牌（面板生成） |
| `V2BX_API_HOST` | GitHub Secrets | 面板 API 地址（Mesh IP，如 `http://100.96.x.x:8080`） |
| `V2BX_NODE_NAME` | GitHub Secrets | 节点名称（如 `UK-Node-01`） |
| `V2BX_CORE` | GitHub Secrets | 内核类型（sing/xray/hysteria2） |
| `V2BX_NODE_TYPE` | GitHub Secrets | 节点类型（vmess/vless/trojan） |
| `V2BX_LISTEN_PORT` | GitHub Secrets | 监听端口（默认 443） |
| `V2BX_TRANSPORT` | GitHub Secrets |传输协议（ws/http/grpc） |
| `V2BX_CERT_MODE` | GitHub Secrets | 证书模式（self/cloudflare） |
| `V2BX_CERT_DOMAIN` | GitHub Secrets | 证书域名 |

## 如何获取 AuthKey

1. 登录 v2board 管理面板
2. 进入 **节点管理 > 授权密钥**
3. 点击 **生成新密钥**
4. 将密钥保存到 GitHub Secrets > NodeX > `V2BX_AUTH_KEY`

## 使用方法

### GitHub Actions

```yaml
workflow_dispatch:
  inputs:
    role: v2bx
    target_group: v2bx_servers
```

### 本地部署

```bash
ansible-playbook playbooks/provision/site.yml \
  --tags v2bx \
  --limit v2bx_servers \
  -e V2BX_AUTH_KEY=your-auth-key \
  -e V2BX_API_HOST=http://100.96.x.x:8080
```

## 部署流程

1. 验证 AuthKey 和 API Host
2. 创建目录 `/usr/local/V2bX`, `/etc/V2bX`, `/var/lib/V2bX`
3. 下载 V2bX 二进制和 geo 数据文件
4. 生成 `config.json`（自动注册模式）
5. 安装 systemd 服务
6. 启动服务，等待自动注册完成
7. 验证凭证文件生成

## Mesh 通信

V2bX 通过 Cloudflare Mesh IP 与 v2board 面板通信：

- `V2BX_API_HOST` 使用面板的 Mesh IP（如 `http://100.96.0.5:8080`）
- 部署顺序: Mesh → v2board → V2bX
- 所有流量通过 Mesh 内网传输，无需公网暴露