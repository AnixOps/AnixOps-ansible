# Cloudflare Tunnel Helm 部署快速参考

## 🚀 快速命令

### 部署

```bash
# 方法 1: 命令行传递 token
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=YOUR_TOKEN"

# 方法 2: 环境变量
export CLOUDFLARE_TUNNEL_TOKEN="YOUR_TOKEN"
ansible-playbook playbooks/cloudflared_k8s_helm.yml

# 方法 3: Ansible Vault
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  -e @vars/cloudflare_secrets.yml \
  --vault-password-file ~/.vault_pass
```

### 验证

```bash
# 查看 Pod
kubectl get pods -n cloudflare-tunnel

# 查看日志
kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared -f

# 查看 Helm release
helm list -n cloudflare-tunnel

# 查看 Helm values
helm get values cloudflared -n cloudflare-tunnel
```

### 更新

```bash
# 更新到新版本
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=YOUR_TOKEN helm_chart_version=0.4.0"

# 修改副本数
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=YOUR_TOKEN replica_count=3"
```

### 卸载

```bash
# 使用脚本（推荐）
./scripts/cleanup_cloudflared.sh

# 手动卸载
helm uninstall cloudflared -n cloudflare-tunnel
kubectl delete namespace cloudflare-tunnel
```

## 📋 常用变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `cloudflare_tunnel_token` | （必需） | Cloudflare Tunnel Token |
| `k8s_namespace` | `cloudflare-tunnel` | Kubernetes 命名空间 |
| `replica_count` | `2` | Pod 副本数 |
| `helm_chart_version` | 最新 | Helm Chart 版本 |
| `log_level` | `info` | 日志级别 |

## 🏷️ Tags

```bash
# 只运行验证
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX" \
  --tags validation

# 跳过验证
ansible-playbook playbooks/cloudflared_k8s_helm.yml \
  --extra-vars "cloudflare_tunnel_token=XXX" \
  --skip-tags verification
```

可用 tags:
- `validation` - 验证任务
- `namespace` - 命名空间管理
- `helm` - Helm 操作
- `cloudflared` - Cloudflared 相关
- `deploy` - 部署任务
- `verification` - 验证部署

## 🔍 故障排查

```bash
# Pod 启动失败
kubectl describe pod <pod-name> -n cloudflare-tunnel
kubectl logs <pod-name> -n cloudflare-tunnel

# Helm 部署失败
helm history cloudflared -n cloudflare-tunnel
helm rollback cloudflared -n cloudflare-tunnel

# 检查资源
kubectl top pods -n cloudflare-tunnel
kubectl get events -n cloudflare-tunnel
```

## 📚 文档链接

- 完整文档: [docs/CLOUDFLARED_K8S_HELM.md](CLOUDFLARED_K8S_HELM.md)
- Role README: [roles/cloudflared_k8s/README.md](../roles/cloudflared_k8s/README.md)
- 示例: [examples/](../examples/)
