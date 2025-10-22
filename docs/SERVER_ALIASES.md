# Server Aliases Management

## 概述

服务器别名系统允许你为每台服务器设置友好的显示名称和标签，这些别名会自动应用到 Observability 栈的所有组件中。

## 功能特性

- **集中管理**: 所有服务器别名在 `inventory/server_aliases.yml` 中统一配置
- **自动更新**: 修改别名后，一条命令即可更新所有 Observability 配置
- **丰富标签**: 支持别名、位置、环境、描述等多维度标签
- **无缝集成**: 自动应用到 Prometheus、Grafana、Loki 配置中

## 配置文件

### 服务器别名配置文件

文件位置: `inventory/server_aliases.yml`

```yaml
server_aliases:
  # 服务器的 inventory hostname
  de-test-1:
    alias: "德国-测试-1"              # 友好显示名称
    description: "德国 Web 服务器"    # 服务器描述
    location: "Germany"               # 物理位置/区域
    environment: "test"               # 环境标签 (prod/staging/dev/test)
    
  pl-test-1:
    alias: "波兰-测试-1"
    description: "Observability 服务器"
    location: "Poland"
    environment: "test"
```

## 使用方法

### 1. 配置服务器别名

编辑 `inventory/server_aliases.yml`:

```bash
vim inventory/server_aliases.yml
```

添加或修改服务器配置:

```yaml
server_aliases:
  us-prod-1:
    alias: "美国-生产-1"
    description: "美国东部 Web 服务器"
    location: "US-East"
    environment: "production"
```

### 2. 更新 Observability 配置

运行更新命令:

```bash
# 使用脚本（推荐）
bash scripts/anixops.sh update-labels

# 或直接使用 ansible-playbook
ansible-playbook -i inventory/hosts.yml playbooks/update-observability-labels.yml
```

这个命令会：
1. ✓ 加载服务器别名配置
2. ✓ 更新 Prometheus 配置（添加标签）
3. ✓ 验证 Prometheus 配置语法
4. ✓ 更新 Grafana datasources
5. ✓ 更新 Loki 配置
6. ✓ 重启相关服务
7. ✓ 验证服务健康状态

### 3. 验证更新

访问 Prometheus 查询界面:

```
http://your-observability-server:9090
```

查询示例:

```promql
# 按别名查询
node_cpu_seconds_total{alias="德国-测试-1"}

# 按位置查询
node_cpu_seconds_total{location="Germany"}

# 按环境查询
node_cpu_seconds_total{environment="production"}
```

## 标签说明

### 必需字段

- **alias**: 服务器的友好显示名称，会在 Grafana 中显示
- **description**: 服务器的详细描述
- **location**: 物理位置或区域（如 Germany, US-East, China-Beijing）
- **environment**: 环境类型，建议使用:
  - `production`: 生产环境
  - `staging`: 预发布环境
  - `test`: 测试环境
  - `dev`: 开发环境

### 标签用途

在 Prometheus 中，这些标签会自动添加到所有指标上:

```yaml
- job_name: 'node_exporter'
  static_configs:
    - targets: ['192.168.1.10:9100']
      labels:
        instance: 'de-test-1'
        alias: '德国-测试-1'
        location: 'Germany'
        environment: 'test'
        description: '德国 Web 服务器'
```

## 应用场景

### 场景 1: 添加新服务器

1. 在 `inventory/hosts.yml` 添加新服务器
2. 在 `inventory/server_aliases.yml` 添加别名配置
3. 运行 `bash scripts/anixops.sh observability` 部署
4. 新服务器会自动带有标签

### 场景 2: 修改服务器别名

1. 编辑 `inventory/server_aliases.yml`
2. 运行 `bash scripts/anixops.sh update-labels`
3. 所有 Observability 配置自动更新

### 场景 3: 服务器迁移

服务器从测试环境迁移到生产环境:

```yaml
# 修改前
us-test-1:
  alias: "美国-测试-1"
  environment: "test"

# 修改后
us-test-1:
  alias: "美国-生产-1"
  environment: "production"
```

运行 `bash scripts/anixops.sh update-labels` 即可。

## 在 Grafana 中使用

### Dashboard 变量

在 Grafana Dashboard 中创建变量:

```
Label: Environment
Name: environment
Type: Query
Query: label_values(environment)
```

然后在查询中使用:

```promql
rate(node_cpu_seconds_total{environment="$environment"}[5m])
```

### 过滤器

使用标签过滤数据:

```promql
# 查看特定位置的服务器
node_load1{location="Germany"}

# 查看生产环境服务器
node_load1{environment="production"}

# 组合条件
node_load1{location="US-East", environment="production"}
```

## 最佳实践

### 1. 命名规范

**别名命名建议**:
- 使用清晰的地理位置 + 环境 + 序号
- 示例: `德国-生产-1`, `US-East-Prod-2`

**Location 建议**:
- 使用英文，保持一致性
- 示例: `Germany`, `US-East`, `China-Beijing`

**Environment 建议**:
- 使用标准值: `production`, `staging`, `test`, `dev`

### 2. 一致性

保持所有服务器配置的格式和标签一致:

```yaml
# 好的示例
server_aliases:
  de-prod-1:
    alias: "德国-生产-1"
    location: "Germany"
    environment: "production"
  
  de-prod-2:
    alias: "德国-生产-2"
    location: "Germany"
    environment: "production"
```

### 3. 文档化

在 `description` 字段中添加重要信息:

```yaml
us-prod-1:
  alias: "美国-生产-1"
  description: "主 API 服务器 - 处理用户请求"
  location: "US-East"
  environment: "production"
```

## 故障排查

### 配置验证失败

如果 Prometheus 配置验证失败:

```bash
# 手动验证配置
/opt/prometheus/promtool check config /opt/prometheus/prometheus.yml
```

### 服务启动失败

检查服务状态:

```bash
# 检查 Prometheus
systemctl status prometheus

# 检查 Grafana
systemctl status grafana-server

# 检查 Loki
systemctl status loki
```

### 标签未显示

1. 确认配置文件语法正确
2. 确认服务已重启
3. 检查 Prometheus targets 页面: `http://ip:9090/targets`

## 示例配置

### 多区域部署

```yaml
server_aliases:
  # 美国区域
  us-east-prod-1:
    alias: "美东-生产-1"
    description: "美国东部主服务器"
    location: "US-East"
    environment: "production"
  
  us-west-prod-1:
    alias: "美西-生产-1"
    description: "美国西部主服务器"
    location: "US-West"
    environment: "production"
  
  # 欧洲区域
  de-prod-1:
    alias: "德国-生产-1"
    description: "欧洲区域主服务器"
    location: "Germany"
    environment: "production"
  
  # 亚洲区域
  sg-prod-1:
    alias: "新加坡-生产-1"
    description: "亚太区域主服务器"
    location: "Singapore"
    environment: "production"
```

### 环境分离

```yaml
server_aliases:
  # 生产环境
  app-prod-1:
    alias: "应用-生产-1"
    description: "生产应用服务器"
    location: "US-East"
    environment: "production"
  
  # 预发布环境
  app-staging-1:
    alias: "应用-预发布-1"
    description: "预发布测试服务器"
    location: "US-East"
    environment: "staging"
  
  # 测试环境
  app-test-1:
    alias: "应用-测试-1"
    description: "自动化测试服务器"
    location: "US-East"
    environment: "test"
```

## 相关文件

- `inventory/server_aliases.yml` - 服务器别名配置
- `playbooks/update-observability-labels.yml` - 更新标签 playbook
- `roles/prometheus_server/templates/prometheus.yml.j2` - Prometheus 配置模板
- `scripts/anixops.sh` - 便捷脚本

## 参考链接

- [Prometheus 标签最佳实践](https://prometheus.io/docs/practices/naming/)
- [Grafana 变量文档](https://grafana.com/docs/grafana/latest/variables/)
