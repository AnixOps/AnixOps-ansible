# V2bX Proxy Node Role

閮ㄧ讲 V2bX 浠ｇ悊鑺傜偣锛岃嚜鍔ㄧ敓鎴?AuthKey 骞舵敞鍐屽埌 v2board 鎺у埗闈㈡澘銆?
## 渚濊禆


## 鑷姩 AuthKey 鐢熸垚

Ansible 鍦ㄩ儴缃?V2bX 鍓嶄細鑷姩璋冪敤闈㈡澘 API 鐢熸垚 AuthKey锛?
```
Ansible 鈫?闈㈡澘 /api/v2/internal/auth-keys 鈫?杩斿洖 AuthKey 鈫?V2bX 娉ㄥ唽
```

## 閰嶇疆鍙橀噺

| Secret | 璇存槑 |
|--------|------|
| `V2BX_API_HOST` | 闈㈡澘 API 鍦板潃锛圡esh IP锛屽 `http://100.96.0.5:8080`锛?|
| `V2BX_PANEL_API_TOKEN` | 闈㈡澘鐨?API_TOKEN锛堜粠 config.yaml 鑾峰彇锛?|
| `V2BX_NODE_NAME` | 鑺傜偣鍚嶇О锛堝 `UK-Node-01`锛?|
| `V2BX_CORE` | 鍐呮牳绫诲瀷锛坰ing/xray锛?|
| `V2BX_PROTOCOLS` | 鍗忚鍒楄〃锛孞SON鏁扮粍 |

**V2BX_PROTOCOLS 绀轰緥**锛?```json
["vmess", "vless", "shadowsocks", "hysteria2"]
```

## 闈㈡澘 API_TOKEN 閰嶇疆

闈㈡澘 config.yaml 涓渶瑕佽缃細

```yaml
app:
  api_token: "your-secure-token-here"
```

姝?token 鐢ㄤ簬 Ansible 璋冪敤鍐呴儴 API 绔偣銆?
## 閮ㄧ讲娴佺▼

```
1. Ansible 璋冪敤闈㈡澘 /api/v2/internal/auth-keys
2. 闈㈡澘鐢熸垚 AuthKey锛堜竴娆℃€т护鐗岋級
3. Ansible 閰嶇疆 V2bX 浣跨敤姝?AuthKey
4. V2bX 鍚姩锛岃嚜鍔ㄦ敞鍐岃幏鍙?ApiKey + Secret
5. V2bX 浠庨潰鏉挎媺鍙栧崗璁厤缃?```

## GitHub Secrets 閰嶇疆

```
V2BX_API_HOST=http://100.96.0.5:8080
V2BX_PANEL_API_TOKEN=your-api-token-from-config.yaml
V2BX_NODE_NAME=UK-Node-01
V2BX_CORE=sing
V2BX_PROTOCOLS=["vmess","vless","shadowsocks"]
```

## 鎵嬪姩 AuthKey锛堝彲閫夛級

濡傛灉闇€瑕佹墜鍔ㄧ鐞?AuthKey锛?
1. 璁剧疆 `V2BX_AUTO_GENERATE_AUTHKEY=false`
2. 鍦ㄩ潰鏉跨敓鎴?AuthKey锛屼繚瀛樺埌 `V2BX_AUTH_KEY`

## 閮ㄧ讲鍛戒护

```yaml
workflow_dispatch:
  inputs:
    role: v2bx
    target_group: v2bx_servers
```

## 闈㈡澘閰嶇疆鍗忚

閮ㄧ讲鍚庯紝鍦ㄩ潰鏉夸腑涓鸿妭鐐规坊鍔犲崗璁細

1. 鑺傜偣绠＄悊 > 閫夋嫨鑺傜偣
2. 娣诲姞鍗忚 > 閫夋嫨绫诲瀷
3. 閰嶇疆绔彛銆乀LS銆佷紶杈撳眰
4. V2bX 鑷姩鎷夊彇閰嶇疆骞跺惎鍔ㄦ湇鍔
