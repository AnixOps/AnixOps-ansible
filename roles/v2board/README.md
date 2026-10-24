# V2board Control Panel Role

閮ㄧ讲 v2board 鎺у埗闈㈡澘锛堜簩杩涘埗閮ㄧ讲锛夛紝鐢ㄤ簬绠＄悊 V2bX 浠ｇ悊鑺傜偣銆?
## 閮ㄧ讲鏂瑰紡

**浜岃繘鍒堕儴缃?*锛圔inary Deployment锛夛細
- 浠?GitHub Releases 鎴栨寚瀹?URL 涓嬭浇浜岃繘鍒舵枃浠?- systemd 鏈嶅姟绠＄悊
- 涓嶄緷璧?Docker

## 閰嶇疆鍙橀噺

| Secret | 璇存槑 |
|--------|------|
| `V2BOARD_API_TOKEN` | **鍐呴儴 API 浠ょ墝**锛堢敤浜?Ansible 鑷姩鍖栥€乂2bX 娉ㄥ唽锛?|
| `V2BOARD_JWT_SECRET` | JWT 瀵嗛挜锛?2+ 瀛楃闅忔満锛?|
| `V2BOARD_ADMIN_EMAIL` | 绠＄悊鍛橀偖绠?|
| `V2BOARD_ADMIN_PASSWORD` | 绠＄悊鍛樺瘑鐮?|
| `V2BOARD_DB_TYPE` | 鏁版嵁搴撶被鍨嬶紙sqlite/postgres锛?|
| `V2BOARD_BINARY_URL` | 浜岃繘鍒朵笅杞?URL锛堝彲閫夛紝榛樿浠?GitHub Releases锛?|
| `V2BOARD_PG_HOST` | PostgreSQL 鍦板潃锛坧ostgres 妯″紡锛?|
| `V2BOARD_PG_PASSWORD` | PostgreSQL 瀵嗙爜 |
| `V2BOARD_REDIS_HOST` | Redis 鍦板潃 |
| `V2BOARD_REDIS_PASSWORD` | Redis 瀵嗙爜锛堝彲閫夛級 |

## API_TOKEN 鐢ㄩ€?
鍚屼竴涓?`V2BOARD_API_TOKEN` 鐢ㄤ簬锛?
1. **鍐欏叆闈㈡澘 config.yaml** 鈫?闈㈡澘鍚姩鍚庨獙璇佸唴閮?API
2. **Ansible 璋冪敤闈㈡澘 API** 鈫?鑷姩鐢熸垚 AuthKey
3. **V2bX 閮ㄧ讲鏃?* 鈫?璋冪敤闈㈡澘 `/api/v2/internal/auth-keys`

## 绔彛

| 绔彛 | 鐢ㄩ€?|
|------|------|
| 3000 | 鍓嶇鐣岄潰 |
| 8080 | API 绔彛 |
| 50051 | gRPC 绔彛 |
| 18081 | NodeX 绔彛 |

## 閮ㄧ讲娴佺▼

```
閮ㄧ讲 v2board (API_TOKEN 鍐欏叆 config.yaml)
鈫?閮ㄧ讲 V2bX (鐢?API_TOKEN 璋冪敤闈㈡澘鐢熸垚 AuthKey)
鈫?V2bX 娉ㄥ唽 (鑾峰彇 node_id + ApiKey + Secret)
```

## GitHub Secrets 閰嶇疆

```
V2BOARD_API_TOKEN=your-random-token-here
V2BOARD_JWT_SECRET=your-jwt-secret-32chars
V2BOARD_ADMIN_EMAIL=admin@example.com
V2BOARD_ADMIN_PASSWORD=your-password
```
