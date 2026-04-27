# V2bX Proxy Node Role

部署 V2bX 代理节点，使用自动注册模式连接 v2board 控制面板。

## 依赖

- `cloudflare_mesh`: 通过 Mesh IP 与面板通信

## 架构说明

**面板管理协议配置**：
- 一个 Node (物理服务器) 可以有多个 NodeProtocol
- 每个协议有独立的端口、TLS、传输层配置
- V2bX 从面板拉取每个协议的完整配置

```
Node (uk-1)
├── Protocol: vmess@443 (WebSocket + TLS)
├── Protocol: vless-reality@8443
├── Protocol: shadowsocks@8388
└── Protocol: hysteria2@443/udp
```

## 配置变量

| 变量 | 来源 | 说明 |
|------|------|------|
| `V2BX_AUTH_KEY` | GitHub Secrets | 一次性注册令牌（面板生成） |
| `V2BX_API_HOST` | GitHub Secrets | 面板 API 地址（Mesh IP） |
| `V2BX_NODE_NAME` | GitHub Secrets | 节点名称 |
| `V2BX_CORE` | GitHub Secrets | 内核类型（sing/xray） |
| `V2BX_PROTOCOLS` | GitHub Secrets | 支持的协议列表，JSON数组 |

**V2BX_PROTOCOLS 示例**：
```json
["vmess", "vless", "shadowsocks", "hysteria2"]
```

## 部署流程

1. Ansible 部署 V2bX，配置支持的协议列表
2. V2bX 使用 AuthKey 自动注册，获取 node_id + ApiKey + Secret
3. V2bX 定期从面板拉取每个协议的配置（端口、TLS等）
4. 在面板中配置具体协议参数

## 如何配置

### 1. 面板生成 AuthKey

1. 登录 v2board 管理面板
2. 进入 **节点管理 > 授权密钥**
3. 点击 **生成新密钥**
4. 保存到 GitHub Secrets > `V2BX_AUTH_KEY`

### 2. GitHub Secrets 配置

```
V2BX_AUTH_KEY=your-auth-key
V2BX_API_HOST=http://100.96.0.5:8080
V2BX_NODE_NAME=UK-Node-01
V2BX_CORE=sing
V2BX_PROTOCOLS=["vmess","vless","shadowsocks"]
```

### 3. 部署 V2bX

```yaml
workflow_dispatch:
  inputs:
    role: v2bx
    target_group: v2bx_servers
```

### 4. 面板配置协议

部署后，在面板中为节点添加协议：

1. 节点管理 > 选择节点
2. 添加协议 > 选择类型（vmess/vless/ss等）
3. 配置端口、TLS、传输层
4. V2bX 会自动拉取配置并启动对应服务

## Mesh 通信

- `V2BX_API_HOST` 使用面板的 Mesh IP
- 部署顺序: Mesh → v2board → V2bX
- 所有面板通信通过 Mesh 内网