# V2bX Proxy Node Role

部署 V2bX 代理节点，用于连接 v2board 控制面板并提供代理服务。

## 依赖

- `cloudflare_mesh`: 通过 Mesh IP 与面板通信

## 配置变量

| 变量 | 来源 | 说明 |
|------|------|------|
| `V2BX_CORE` | GitHub Secrets | 内核类型 (sing/xray/hysteria2) |
| `V2BX_NODE_ID` | GitHub Secrets | 面板中的节点 ID |
| `V2BX_NODE_TYPE` | GitHub Secrets | 节点类型 (vmess/vless/trojan) |
| `V2BX_API_HOST` | GitHub Secrets | 面板 API 地址 (Mesh IP) |
| `V2BX_API_KEY` | GitHub Secrets | 面板 API 密钥 |
| `V2BX_LISTEN_PORT` | GitHub Secrets | 监听端口 |
| `V2BX_TRANSPORT` | GitHub Secrets |传输协议 (ws/http/grpc) |
| `V2BX_CERT_MODE` | GitHub Secrets |证书模式 (self/cloudflare) |
| `V2BX_CERT_DOMAIN` | GitHub Secrets |证书域名 |

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
  --limit v2bx_servers
```

## 部署流程

1. 验证必需变量
2. 创建安装目录 `/usr/local/V2bX`
3. 下载 V2bX 二进制和 geo 数据文件
4. 生成 `config.json` 配置
5. 安装 systemd 服务
6. 启动服务并验证状态

## Mesh 通信

V2bX 通过 Cloudflare Mesh IP 与 v2board 面板通信:

- `V2BX_API_HOST` 应设置为面板的 Mesh IP (如 `100.96.x.x:8080`)
- 部署顺序: Mesh → v2board → V2bX