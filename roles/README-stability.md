# 绋冲畾鎬у熀纭€璁炬柦 | Stability Infrastructure

鏈枃妗ｈ褰?AnixOps 椤圭洰鐨勭ǔ瀹氭€у垽鍒鏋讹紝纭繚鑷姩鍖栬繍缁村湪鍙帶鐨勫墠鎻愪笅杩愯銆?

## 鍒ゅ埆妗嗘灦 | Decision Framework

姣忎釜瑙掕壊鐨勮嚜鍔ㄥ寲鎿嶄綔閫氳繃浠ヤ笅涓変釜缁村害鍒ゅ埆鏄惁閫傚悎鍏ㄨ嚜鍔ㄦ墽琛岋細

| 缁村害 | 鏍囧噯 | 鍒ゅ埆鏂规硶 |
|------|------|----------|
| **骞傜瓑鎬?* | 閲嶅鎵ц鏄惁浜х敓鐩稿悓缁撴灉 | 浣跨敤 `template`/`copy` 鐨勮鑹插ぉ鐒跺箓绛夛紱浣跨敤 `shell`/`command` 鐨勯渶瑕?`creates`/`removes` 鎴?`changed_when` |
| **鍙娴嬫€?* | 閮ㄧ讲澶辫触鑳藉惁蹇€熷彂鐜?| 瑙掕壊鏄惁鏈夊仴搴锋鏌ャ€佹棩蹇楄緭鍑恒€佹湇鍔＄姸鎬侀獙璇?|
| **鍙洖婊氭€?* | 閰嶇疆閿欒鑳藉惁鎭㈠鍒板凡鐭ヨ壇濂界姸鎬?| 閰嶇疆鏂囦欢鏄惁鏈?`backup: yes`锛屽浠芥槸鍚﹀彲鐢ㄥ洖婊?playbook 鎭㈠ |

### 鍙樻洿瀹℃壒绾у埆

| 绾у埆 | 閫傜敤鍦烘櫙 | 瑕佹眰 |
|------|---------|------|
| **LOW** | 鍗曞彴鏈嶅姟鍣ㄣ€佹湰鍦版祴璇曘€佸彧璇绘搷浣?| 鑷姩鎵ц |
| **MEDIUM** | 灏戦噺鏈嶅姟鍣紙<5锛夈€佸彲鍥炴粴鐨勯厤缃彉鏇?| `serial: "30%"` + `backup: yes` |
| **HIGH** | 鍏ㄩ儴鐢熶骇鏈嶅姟鍣ㄣ€佹牳蹇冩湇鍔″彉鏇?| `serial: "30%"` + `max_fail_percentage: 25` + `backup: yes` + 鍥炴粴棰勬 |

---

## 瑙掕壊娓呭崟 | Role Registry

### 鍩虹璁炬柦瑙掕壊

| 瑙掕壊 | 骞傜瓑鎬?| 鍥炴粴鏂规硶 | 楠岃瘉姝ラ |
|------|--------|---------|---------|
| `common` | template 浠诲姟澶╃劧骞傜瓑锛泂hell 浠诲姟鏈?ignore_errors | `rollback_role=common` | `systemctl status ssh chrony fail2ban` |
| `nginx` | template 浠诲姟澶╃劧骞傜瓑 | `rollback_role=nginx` | `nginx -t` + `curl localhost` |

### 鐩戞帶瑙掕壊

| 瑙掕壊 | 骞傜瓑鎬?| 鍥炴粴鏂规硶 | 楠岃瘉姝ラ |
|------|--------|---------|---------|
| `prometheus` | template 浠诲姟澶╃劧骞傜瓑 | `rollback_role=prometheus` | `curl localhost:9090/-/healthy` |
| `loki` | template 浠诲姟澶╃劧骞傜瓑 | `rollback_role=loki` | `curl localhost:3100/ready` |
| `grafana` | template 浠诲姟澶╃劧骞傜瓑 | `rollback_role=grafana` | `curl localhost:3000/api/health` |
| `node_exporter` | template 浠诲姟澶╃劧骞傜瓑 | `rollback_role=node_exporter` | `curl localhost:9100/metrics` |
| `promtail` | template 浠诲姟澶╃劧骞傜瓑 | `rollback_role=promtail` | `systemctl status promtail` |

### 瀹夊叏瑙掕壊

| 瑙掕壊 | 骞傜瓑鎬?| 鍥炴粴鏂规硶 | 楠岃瘉姝ラ |
|------|--------|---------|---------|
| `acme_ssl` | 璇佷功绛惧彂鏈?block/rescue | 鎵嬪姩鎭㈠鏃ц瘉涔?| `nginx -t` + 璇佷功鏈夋晥鏈熸鏌?|
| `firewall` | UFW 瑙勫垯骞傜瓑 | 鎵嬪姩鎭㈠瑙勫垯 | `ufw status` |

---

## 鍥炴粴鏈哄埗 | Rollback Mechanism

### 浣跨敤鏂规硶

```bash
# 鍒楀嚭鍙敤澶囦唤锛堝共杩愯锛?
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=nginx rollback_dry_run=yes"

# 鍥炴粴鍒版渶杩戠殑澶囦唤
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=prometheus"

# 鍥炴粴鍒版寚瀹氭椂闂存埑鐨勫浠?
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=nginx rollback_timestamp=20260426_120000"
```

### 澶囦唤鏂囦欢鍛藉悕瑙勫垯

閰嶇疆鏂囦欢閮ㄧ讲鏃堕€氳繃 `backup: yes` 鑷姩鐢熸垚锛?
```
/etc/nginx/nginx.conf.backup.2026-04-26T12:00:00Z
/etc/prometheus/prometheus.yml.backup.2026-04-26T12:00:00Z
```

### 鏀寔鐨勮鑹?

`nginx`, `common`, `prometheus`, `loki`, `grafana`, `node_exporter`, `promtail`

---

## 鎵归噺瀹夊叏闄愰€?| Batch Safety Limits

鎵€鏈夌敓浜?playbook 鍦?play 绾у埆璁剧疆锛?

| 鍙傛暟 | 鍊?| 璇存槑 |
|------|-----|------|
| `serial` | `"30%"` 鎴?`1` | 姣忔壒鎿嶄綔鐨勬湇鍔″櫒姣斾緥锛堝仴搴锋鏌ラ€愬彴锛?|
| `max_fail_percentage` | `25` 鎴?`0` | 澶辫触鐜囪秴杩囨鍊煎嵆鍋滄锛圫SH 涓洪浂瀹瑰繊锛?|

### 渚嬪

| Playbook | 鍘熷洜 |
|----------|------|
| `platform/k3s.yml` | K8s 涓撶敤锛屼覆琛岄€昏緫涓嶅悓 |
| `platform/kind.yml` | 鏈湴娴嬭瘯鐜 |
| `platform/k3s-test.yml` | 娴嬭瘯鐜 |

---

## CI 绋冲畾鎬ф鏌?| CI Stability Checks

CI 娴佺▼鑷姩妫€鏌ワ細

1. **YAML 璇硶** 鈥?`yamllint` 楠岃瘉鎵€鏈?YAML 鏂囦欢鏍煎紡
2. **Ansible 璇硶** 鈥?`ansible-playbook --syntax-check` 楠岃瘉 playbook
3. **澶囦唤瑕嗙洊鐜?* 鈥?`scripts/check-backup-coverage.py` 鎵弿 template 浠诲姟鏄惁缂哄皯 `backup: yes`
4. **瀵嗛挜鎵弿** 鈥?TruffleHog 妫€娴嬫彁浜ょ殑瀵嗛挜鍜屽嚟鎹?

---

## 鑷姩鍖栦笌鎵嬪姩浠嬪叆鐨勮竟鐣?

### 鍏ㄨ嚜鍔紙鏃犻渶浜哄伐瀹℃壒锛?

- 鏈湴娴嬭瘯鐜閮ㄧ讲锛坄local.yml`锛?
- 鍋ュ悍妫€鏌ュ拰鐘舵€佹煡璇紙`health-check.yml`锛?
- 鍗曞彴鏈嶅姟鍣ㄧ殑閰嶇疆鍙樻洿锛坄serial: 1`锛?
- 鍙鎿嶄綔锛堜簨瀹炴敹闆嗐€佹棩蹇楁煡鐪嬶級

### 鑷姩鎵ц + 鐩戞帶锛堜簨鍚庡鏌ワ級

- 鐢熶骇鐜鎵归噺閮ㄧ讲锛坄site.yml`銆乣quick-setup.yml`锛?
- 闃茬伀澧欒鍒欐洿鏂?
- 璇佷功缁锛坄acme_ssl`锛?

### 闇€瑕佹墜鍔ㄤ粙鍏?

- 鏁版嵁搴撹縼绉绘垨鏁版嵁鍒犻櫎
- 鎿嶄綔绯荤粺鍗囩骇锛堝唴鏍告洿鏂般€佸ぇ鐗堟湰鍗囩骇锛?
- 缃戠粶鎷撴墤鍙樻洿锛圕loudflare Mesh 璺敱閰嶇疆锛?
- 鍥炴粴澶辫触鍚庣殑鏁呴殰鎺掓煡
- 鏂版湇鍔″櫒棣栨鍒濆鍖栵紙闇€瑕侀獙璇佺綉缁溿€佸瓨鍌ㄣ€佹潈闄愶級

### 绱ф€ユ儏鍐典笅鐨勬墜鍔ㄦ搷浣?

褰撹嚜鍔ㄥ寲澶辫触鏃讹細
1. 鍏堢敤 `rollback.yml` 灏濊瘯鍥炴粴
2. 鍥炴粴澶辫触鍒欐墜鍔?SSH 鍒版湇鍔″櫒淇
3. 淇鍚庢墜鍔ㄨ繍琛?`health-check.yml` 楠岃瘉
