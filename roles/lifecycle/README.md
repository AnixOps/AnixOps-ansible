# Lifecycle Role

统一的服务生命周期管理 Role，支持部署前备份、部署后验证、回滚、清理等操作。

## 功能特性

- **Pre-Deploy Hook**: 备份关键文件、验证依赖、检查当前状态
- **Post-Deploy Hook**: 验证服务健康、写入状态文件、发送通知
- **Pre-Rollback Hook**: 记录当前状态、停止服务
- **Post-Rollback Hook**: 恢复服务、验证、更新状态文件
- **Status Hook**: 查询服务状态、显示部署历史
- **Cleanup Hook**: 停止服务、删除配置、清理备份

## 状态文件

状态文件存储在 `/var/lib/anixops/state/` 目录：

```
/var/lib/anixops/state/
├── nginx_state.json       # 当前状态
├── nginx_history.json     # 部署历史
└── nginx_pre_deploy.log   # 部署前状态记录
```

## 使用方法

```yaml
# 在 playbook 中调用
- role: lifecycle
  vars:
    lifecycle_target_role: nginx
    lifecycle_hook_type: post_deploy
```

```bash
# 通过 lifecycle.yml playbook
ansible-playbook playbooks/maintenance/lifecycle.yml \
  -e "lifecycle_target_role=prometheus" --tags status

# 回滚到上一版本
ansible-playbook playbooks/maintenance/lifecycle.yml \
  -e "lifecycle_target_role=nginx lifecycle_version=prev" --tags rollback

# 清理（需确认）
ansible-playbook playbooks/maintenance/lifecycle.yml \
  -e "lifecycle_target_role=loki cleanup_confirm=yes" --tags cleanup
```

## Role 配置变量

各 Role 需要在 defaults/main.yml 中定义以下变量以支持 hooks：

```yaml
# nginx/defaults/main.yml 示例
nginx_port: 80
nginx_health_url: "http://localhost"
nginx_backup_files:
  - /etc/nginx/nginx.conf
  - /etc/nginx/sites-available/default
nginx_packages:
  - nginx
nginx_config_dirs:
  - /etc/nginx
```

## 清理策略

- **conservative**: 只删除明确孤立的资源
- **aggressive**: 删除所有可能的孤立资源

参数：
- `cleanup_keep_data`: 保留数据目录（归档）
- `cleanup_keep_package`: 保留已安装的包
- `cleanup_keep_backups`: 保留最近 N 个备份