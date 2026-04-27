# V2bX Proxy Node Role

部署 V2bX 代理节点，自动生成 AuthKey 并注册到 v2board 控制面板。

## 依赖

- `cloudflare_mesh`: 通过 Mesh IP 与面板通信

## 自动 AuthKey 生成

Ansible 在部署 V2bX 前会自动调用面板 API 生成 AuthKey：

```
Ansible → 面板 /api/v2/internal/auth-keys → 返回 AuthKey → V2bX 注册
```

## 配置变量

| Secret | 说明 |
|--------|------|
| `V2BX_API_HOST` | 面板 API 地址（Mesh IP，如 `http://100.96.0.5:8080`） |
| `V2BX_PANEL_API_TOKEN` | 面板的 API_TOKEN（从 config.yaml 获取） |
| `V2BX_NODE_NAME` | 节点名称（如 `UK-Node-01`） |
| `V2BX_CORE` | 内核类型（sing/xray） |
| `V2BX_PROTOCOLS` | 协议列表，JSON数组 |

**V2BX_PROTOCOLS 示例**：
```json
["vmess", "vless", "shadowsocks", "hysteria2"]
```

## 面板 API_TOKEN 配置

面板 config.yaml 中需要设置：

```yaml
app:
  api_token: "your-secure-token-here"
```

此 token 用于 Ansible 调用内部 API 端点。

## 部署流程

```
1. Ansible 调用面板 /api/v2/internal/auth-keys
2. 面板生成 AuthKey（一次性令牌）
3. Ansible 配置 V2bX 使用此 AuthKey
4. V2bX 启动，自动注册获取 ApiKey + Secret
5. V2bX 从面板拉取协议配置
```

## GitHub Secrets 配置

```
V2BX_API_HOST=http://100.96.0.5:8080
V2BX_PANEL_API_TOKEN=your-api-token-from-config.yaml
V2BX_NODE_NAME=UK-Node-01
V2BX_CORE=sing
V2BX_PROTOCOLS=["vmess","vless","shadowsocks"]
```

## 手动 AuthKey（可选）

如果需要手动管理 AuthKey：

1. 设置 `V2BX_AUTO_GENERATE_AUTHKEY=false`
2. 在面板生成 AuthKey，保存到 `V2BX_AUTH_KEY`

## 部署命令

```yaml
workflow_dispatch:
  inputs:
    role: v2bx
    target_group: v2bx_servers
```

## 面板配置协议

部署后，在面板中为节点添加协议：

1. 节点管理 > 选择节点
2. 添加协议 > 选择类型
3. 配置端口、TLS、传输层
4. V2bX 自动拉取配置并启动服务