# Speedtest Role

部署 Speedtest CLI 工具，用于节点性能测试。

## 配置变量

| 变量 | 默认值 | 说明 |
|------|------|------|
| `speedtest_install_dir` | `/usr/local/bin` | 安装路径 |
| `speedtest_bin_name` | `speedtest` | 二进制名称 |

## 使用方法

### GitHub Actions

```yaml
workflow_dispatch:
  inputs:
    role: speedtest
    target_group: all
```

### 本地部署

```bash
ansible-playbook playbooks/provision/site.yml \
  --tags speedtest
```

## 部署流程

1. 从 GitHub Releases 下载二进制
2. 安装到 `/usr/local/bin/speedtest`
3. 验证安装

## 使用

```bash
speedtest --help
speedtest --server <server_id>
```