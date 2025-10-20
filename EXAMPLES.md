# 使用示例

本文档提供 AnixOps Ansible 项目的实际使用示例。

---

## 场景 1: 初始化一台新的 Web 服务器

### 目标
将一台新的 Ubuntu 服务器初始化为 Web 服务器，包括基础配置、监控和 Nginx。

### 步骤

1. **添加服务器到 inventory**

编辑 `inventory/hosts.yml`:

```yaml
all:
  children:
    web_servers:
      hosts:
        tokyo-web-01:
          ansible_host: 103.45.67.89  # 你的服务器 IP
```

2. **测试连接**

```bash
ansible tokyo-web-01 -m ping
```

3. **执行完整部署**

```bash
ansible-playbook playbooks/site.yml --limit tokyo-web-01
```

4. **验证结果**

```bash
# 访问 Web 服务器
curl http://103.45.67.89

# 检查监控指标
curl http://103.45.67.89:9100/metrics

# 查看服务状态
ansible tokyo-web-01 -m shell -a "systemctl status nginx node_exporter promtail"
```

---

## 场景 2: 更新 Nginx 配置

### 目标
更新某个 Web 服务器的 Nginx 配置，例如修改 worker_processes。

### 步骤

1. **创建功能分支**

```bash
git checkout -b feature/update-nginx-config
```

2. **修改配置**

编辑 `inventory/group_vars/all/main.yml`:

```yaml
nginx:
  worker_processes: 4  # 从 auto 改为 4
  worker_connections: 2048  # 从 1024 改为 2048
```

3. **提交变更**

```bash
git add inventory/group_vars/all/main.yml
git commit -m "feat(nginx): Increase worker processes and connections"
git push origin feature/update-nginx-config
```

4. **创建 Pull Request**

在 GitHub 上创建 PR，等待 CI 检查通过。

5. **合并并自动部署**

管理员审查后合并到 main 分支，GitHub Actions 自动部署。

6. **验证**

在 Grafana 中检查 Nginx 的连接数和性能指标。

---

## 场景 3: 批量部署多台服务器

### 目标
同时初始化 5 台新服务器。

### 步骤

1. **批量添加到 inventory**

```yaml
all:
  children:
    web_servers:
      hosts:
        web-01:
          ansible_host: 10.0.1.10
        web-02:
          ansible_host: 10.0.1.11
        web-03:
          ansible_host: 10.0.1.12
    
    app_servers:
      hosts:
        app-01:
          ansible_host: 10.0.2.10
        app-02:
          ansible_host: 10.0.2.11
```

2. **分批部署**

```bash
# 先部署 web 服务器
ansible-playbook playbooks/site.yml --limit web_servers

# 再部署 app 服务器
ansible-playbook playbooks/site.yml --limit app_servers
```

3. **并行部署（提高速度）**

编辑 `ansible.cfg`:

```ini
[defaults]
forks = 10  # 同时处理 10 台主机
```

---

## 场景 4: 紧急修复 - SSH 端口被误改

### 目标
快速回滚一个导致 SSH 无法连接的配置错误。

### 步骤

1. **识别问题提交**

在 GitHub 上找到导致问题的 commit。

2. **Revert 提交**

点击 commit 旁边的 "Revert" 按钮，创建 revert PR。

3. **紧急合并**

立即合并 revert PR，触发自动部署。

4. **手动回滚（如果 GitHub Actions 无法连接）**

```bash
# 使用旧的 SSH 端口临时连接
ansible all -e "ansible_port=2222" -m shell -a "sed -i 's/Port 2222/Port 22/' /etc/ssh/sshd_config && systemctl restart sshd"
```

---

## 场景 5: 添加新的告警规则

### 目标
添加一个新的告警规则：当磁盘 I/O 等待时间超过 30% 时告警。

### 步骤

1. **创建告警规则文件**

编辑 `observability/prometheus/rules/host-alerts.yml`，添加：

```yaml
  - alert: HighDiskIOWait
    expr: rate(node_cpu_seconds_total{mode="iowait"}[5m]) * 100 > 30
    for: 10m
    labels:
      severity: warning
      category: performance
    annotations:
      summary: "High disk I/O wait on {{ $labels.instance }}"
      description: "I/O wait time is {{ $value }}%"
```

2. **提交并部署**

```bash
git add observability/prometheus/rules/host-alerts.yml
git commit -m "feat(monitoring): Add high disk I/O wait alert"
git push origin feature/add-iowait-alert
```

3. **验证告警**

在 Prometheus UI 中检查新规则是否加载：
```
http://prometheus.example.com:9090/alerts
```

---

## 场景 6: 健康检查和故障排查

### 目标
定期检查所有服务器的健康状态。

### 步骤

1. **运行健康检查 playbook**

```bash
ansible-playbook playbooks/health-check.yml
```

输出示例：
```
═══════════════════════════════════════════════════════════
Health Check Report for tokyo-web-01
═══════════════════════════════════════════════════════════

System Info:
- Hostname: tokyo-web-01
- IP: 103.45.67.89
- OS: Ubuntu 22.04
- Uptime:  12:34:56 up 30 days,  5:12

Resource Usage:
- Disk Usage: 65%
- Memory Usage: 42%

Services:
- Node Exporter: active
- Promtail: active
- Nginx: active

═══════════════════════════════════════════════════════════
```

2. **查看特定服务器的详细信息**

```bash
ansible tokyo-web-01 -m setup
```

3. **检查日志**

```bash
ansible tokyo-web-01 -m shell -a "tail -50 /var/log/nginx/error.log"
```

---

## 场景 7: 使用 GitHub Actions 手动部署

### 目标
通过 GitHub Actions UI 手动触发部署到特定服务器组。

### 步骤

1. **打开 GitHub Actions**

进入仓库的 Actions 标签页。

2. **选择 Deploy to Production workflow**

3. **点击 "Run workflow"**

4. **选择参数**
- Branch: `main`
- Target hosts: `web_servers`

5. **点击 "Run workflow" 确认**

6. **监控执行**

实时查看部署日志和结果。

---

## 场景 8: 环境变量管理

### 目标
通过环境变量动态配置服务器信息，而不是硬编码在代码中。

### GitHub Actions 中设置

在 workflow 中使用：

```yaml
env:
  WEB_01_IP: ${{ secrets.WEB_01_IP }}
  WEB_02_IP: ${{ secrets.WEB_02_IP }}
  PROMETHEUS_URL: ${{ secrets.PROMETHEUS_URL }}
```

### 本地开发中使用

创建 `.env` 文件（不提交到 Git）:

```bash
export WEB_01_IP="103.45.67.89"
export WEB_02_IP="103.45.67.90"
export ANSIBLE_USER="root"
export SSH_KEY_PATH="~/.ssh/anixops_rsa"
```

加载环境变量：

```bash
source .env
ansible-playbook playbooks/site.yml
```

---

## 场景 9: 只更新特定服务

### 目标
只重启 Nginx，不执行其他任务。

### 步骤

```bash
# 使用 tags
ansible-playbook playbooks/site.yml --tags nginx

# 或直接执行特定 playbook
ansible-playbook playbooks/web-servers.yml

# 或使用 ad-hoc 命令
ansible web_servers -m service -a "name=nginx state=restarted"
```

---

## 场景 10: 测试模式（Dry Run）

### 目标
在不实际执行的情况下，检查 playbook 会做什么改动。

### 步骤

```bash
# Check 模式
ansible-playbook playbooks/site.yml --check

# Diff 模式（显示文件差异）
ansible-playbook playbooks/site.yml --check --diff

# 仅语法检查
ansible-playbook playbooks/site.yml --syntax-check
```

---

## 常用技巧

### 1. 调试模式

```bash
# 详细输出
ansible-playbook playbooks/site.yml -v

# 更详细
ansible-playbook playbooks/site.yml -vvv

# 极度详细（包括 SSH 调试）
ansible-playbook playbooks/site.yml -vvvv
```

### 2. 限制执行范围

```bash
# 只对一台主机
ansible-playbook playbooks/site.yml --limit tokyo-web-01

# 对多台主机
ansible-playbook playbooks/site.yml --limit "tokyo-web-01,tokyo-web-02"

# 对一个组
ansible-playbook playbooks/site.yml --limit web_servers
```

### 3. 跳过某些任务

```bash
# 跳过 tags
ansible-playbook playbooks/site.yml --skip-tags nginx

# 从某个任务开始
ansible-playbook playbooks/site.yml --start-at-task="Install Nginx"
```

### 4. 交互式执行

```bash
# 逐步确认
ansible-playbook playbooks/site.yml --step
```

---

**更多使用技巧，请参考 Ansible 官方文档！**
