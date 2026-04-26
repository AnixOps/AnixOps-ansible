# 稳定性基础设施 | Stability Infrastructure

本文档记录 AnixOps 项目的稳定性判别框架，确保自动化运维在可控的前提下运行。

## 判别框架 | Decision Framework

每个角色的自动化操作通过以下三个维度判别是否适合全自动执行：

| 维度 | 标准 | 判别方法 |
|------|------|----------|
| **幂等性** | 重复执行是否产生相同结果 | 使用 `template`/`copy` 的角色天然幂等；使用 `shell`/`command` 的需要 `creates`/`removes` 或 `changed_when` |
| **可观测性** | 部署失败能否快速发现 | 角色是否有健康检查、日志输出、服务状态验证 |
| **可回滚性** | 配置错误能否恢复到已知良好状态 | 配置文件是否有 `backup: yes`，备份是否可用回滚 playbook 恢复 |

### 变更审批级别

| 级别 | 适用场景 | 要求 |
|------|---------|------|
| **LOW** | 单台服务器、本地测试、只读操作 | 自动执行 |
| **MEDIUM** | 少量服务器（<5）、可回滚的配置变更 | `serial: "30%"` + `backup: yes` |
| **HIGH** | 全部生产服务器、核心服务变更 | `serial: "30%"` + `max_fail_percentage: 25` + `backup: yes` + 回滚预案 |

---

## 角色清单 | Role Registry

### 基础设施角色

| 角色 | 幂等性 | 回滚方法 | 验证步骤 |
|------|--------|---------|---------|
| `common` | template 任务天然幂等；shell 任务有 ignore_errors | `rollback_role=common` | `systemctl status ssh chrony fail2ban` |
| `nginx` | template 任务天然幂等 | `rollback_role=nginx` | `nginx -t` + `curl localhost` |
| `cloudflare_mesh` | shell 命令有 creates 检查 | Dashboard 端移除节点 | `warp-cli status` |

### 监控角色

| 角色 | 幂等性 | 回滚方法 | 验证步骤 |
|------|--------|---------|---------|
| `prometheus` | template 任务天然幂等 | `rollback_role=prometheus` | `curl localhost:9090/-/healthy` |
| `loki` | template 任务天然幂等 | `rollback_role=loki` | `curl localhost:3100/ready` |
| `grafana` | template 任务天然幂等 | `rollback_role=grafana` | `curl localhost:3000/api/health` |
| `node_exporter` | template 任务天然幂等 | `rollback_role=node_exporter` | `curl localhost:9100/metrics` |
| `promtail` | template 任务天然幂等 | `rollback_role=promtail` | `systemctl status promtail` |

### 安全角色

| 角色 | 幂等性 | 回滚方法 | 验证步骤 |
|------|--------|---------|---------|
| `acme_ssl` | 证书签发有 block/rescue | 手动恢复旧证书 | `nginx -t` + 证书有效期检查 |
| `firewall` | UFW 规则幂等 | 手动恢复规则 | `ufw status` |

---

## 回滚机制 | Rollback Mechanism

### 使用方法

```bash
# 列出可用备份（干运行）
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=nginx rollback_dry_run=yes"

# 回滚到最近的备份
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=prometheus"

# 回滚到指定时间戳的备份
ansible-playbook playbooks/maintenance/rollback.yml \
  -e "rollback_role=nginx rollback_timestamp=20260426_120000"
```

### 备份文件命名规则

配置文件部署时通过 `backup: yes` 自动生成：
```
/etc/nginx/nginx.conf.backup.2026-04-26T12:00:00Z
/etc/prometheus/prometheus.yml.backup.2026-04-26T12:00:00Z
```

### 支持的角色

`nginx`, `common`, `prometheus`, `loki`, `grafana`, `node_exporter`, `promtail`

---

## 批量安全限速 | Batch Safety Limits

所有生产 playbook 在 play 级别设置：

| 参数 | 值 | 说明 |
|------|-----|------|
| `serial` | `"30%"` 或 `1` | 每批操作的服务器比例（健康检查逐台） |
| `max_fail_percentage` | `25` 或 `0` | 失败率超过此值即停止（SSH 为零容忍） |

### 例外

| Playbook | 原因 |
|----------|------|
| `platform/k3s.yml` | K8s 专用，串行逻辑不同 |
| `platform/kind.yml` | 本地测试环境 |
| `platform/k3s-test.yml` | 测试环境 |

---

## CI 稳定性检查 | CI Stability Checks

CI 流程自动检查：

1. **YAML 语法** — `yamllint` 验证所有 YAML 文件格式
2. **Ansible 语法** — `ansible-playbook --syntax-check` 验证 playbook
3. **备份覆盖率** — `scripts/check-backup-coverage.py` 扫描 template 任务是否缺少 `backup: yes`
4. **密钥扫描** — TruffleHog 检测提交的密钥和凭据

---

## 自动化与手动介入的边界

### 全自动（无需人工审批）

- 本地测试环境部署（`local.yml`）
- 健康检查和状态查询（`health-check.yml`）
- 单台服务器的配置变更（`serial: 1`）
- 只读操作（事实收集、日志查看）

### 自动执行 + 监控（事后审查）

- 生产环境批量部署（`site.yml`、`quick-setup.yml`）
- 防火墙规则更新
- 证书续签（`acme_ssl`）

### 需要手动介入

- 数据库迁移或数据删除
- 操作系统升级（内核更新、大版本升级）
- 网络拓扑变更（Cloudflare Mesh 路由配置）
- 回滚失败后的故障排查
- 新服务器首次初始化（需要验证网络、存储、权限）

### 紧急情况下的手动操作

当自动化失败时：
1. 先用 `rollback.yml` 尝试回滚
2. 回滚失败则手动 SSH 到服务器修复
3. 修复后手动运行 `health-check.yml` 验证
