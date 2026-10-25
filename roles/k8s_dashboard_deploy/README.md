# k8s_dashboard_deploy

Deploy the upstream [Kubernetes Dashboard](https://github.com/kubernetes/dashboard) on a k3s node, grant an
admin service account, store its token in a root-only file and expose the dashboard on `127.0.0.1:8443`
through a hardened `kubectl port-forward` systemd service.

在 k3s 节点上部署 Kubernetes Dashboard，创建管理员服务账号并把令牌写入 root 专属文件，通过
`kubectl port-forward` systemd 服务暴露到 `127.0.0.1:8443`。

The public HTTPS vhost is **not** part of this role: `roles/nginx` renders
`roles/nginx/templates/k8s/k8s-dashboard.conf.j2`, which proxies `https://{{ k8s_dashboard_domain }}` to the
`127.0.0.1:8443` upstream created here. Keep `k8s_dashboard_domain` identical for both roles.

## Behaviour | 行为

1. Asserts k3s is installed (`/usr/local/bin/k3s`).
2. Downloads the pinned `recommended.yaml` (retries, optional sha256) into `/usr/local/share/k8s-dashboard/`
   and renders `admin-user.yaml` (ServiceAccount + `cluster-admin` ClusterRoleBinding, plus a
   `service-account-token` Secret in `secret` mode).
3. Renders `kustomization.yaml` next to the two manifests and runs `kubectl apply --kustomize=<manifest_dir>`;
   `changed` only when kubectl reports `created`/`configured`. The kustomization drops the placeholder `data`
   of the `kubernetes-dashboard-csrf` Secret, so a re-run no longer blanks the CSRF key the dashboard generated.
   On an existing cluster the first run after this change reports that Secret `configured` once (its data is
   removed and the dashboard regenerates the key at the next pod start); later runs are unchanged.
4. Waits for `deployment/kubernetes-dashboard` to roll out (retried).
5. Token:
   * `bound` (default) - `kubectl create token admin-user --duration 8760h`, generated only when the token
     file is missing or `k8s_dashboard_deploy_token_rotate: true`.
   * `secret` - long-lived token read from the `admin-user-token` Secret (never expires).
   The token is written to `/root/k8s-dashboard-token.txt` with mode `0600`; every task that touches it runs
   with `no_log: true`.
6. Installs `kubectl-port-forward.service` (`backup: true`, `Restart=always`, `NoNewPrivileges`,
   `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, start-limit guard), flushes handlers, waits for the
   listener and checks `https://127.0.0.1:8443/` returns 200. On failure the previous unit file is restored,
   the service restarted and the play fails with a clear message.

A second run reports `changed=0`.

## Variables | 变量

| Variable | Default | Description |
|---|---|---|
| `k8s_dashboard_deploy_domain` | `{{ k8s_dashboard_domain \| default('dashboard.local') }}` | public name used by the nginx vhost |
| `k8s_dashboard_deploy_version` | `v2.7.0` | dashboard release (last one with `aio/deploy/recommended.yaml`) |
| `k8s_dashboard_deploy_manifest_url` | upstream raw URL for the version | manifest source |
| `k8s_dashboard_deploy_manifest_checksum` | `""` | `sha256:<hex>` to verify the manifest |
| `k8s_dashboard_deploy_manifest_dir` | `/usr/local/share/k8s-dashboard` | where manifests are kept |
| `k8s_dashboard_deploy_kubeconfig_path` | `{{ kubeconfig_path \| default('/etc/rancher/k3s/k3s.yaml') }}` | kubeconfig for kubectl |
| `k8s_dashboard_deploy_kubectl_bin` / `_k3s_bin` | `/usr/local/bin/kubectl` / `/usr/local/bin/k3s` | binaries |
| `k8s_dashboard_deploy_k3s_service_name` | `k3s` | unit the port-forward depends on |
| `k8s_dashboard_deploy_namespace` / `_service_account` | `kubernetes-dashboard` / `admin-user` | RBAC identities |
| `k8s_dashboard_deploy_token_mode` | `bound` | `bound` or `secret` (see above) |
| `k8s_dashboard_deploy_token_duration` | `8760h` | lifetime of a bound token |
| `k8s_dashboard_deploy_token_rotate` | `false` | force a new bound token on this run |
| `k8s_dashboard_deploy_token_file` | `/root/k8s-dashboard-token.txt` | token destination (mode 0600) |
| `k8s_dashboard_deploy_bind_address` | `127.0.0.1` | port-forward listen address |
| `k8s_dashboard_deploy_rollout_timeout`, `_ready_retries`, `_ready_delay` | `120s`, `5`, `10` | wait policy |
| `k8s_dashboard_deploy_download_retries` / `_download_delay` | `5` / `10` | download retry policy |

Lifecycle contract: `k8s_dashboard_deploy_port: 8443`, `k8s_dashboard_deploy_health_url: https://127.0.0.1:8443/`,
`k8s_dashboard_deploy_service_name: kubectl-port-forward`,
`k8s_dashboard_deploy_backup_files: [/etc/systemd/system/kubectl-port-forward.service]`,
`k8s_dashboard_deploy_config_dirs: [/usr/local/share/k8s-dashboard]`, `k8s_dashboard_deploy_packages: []`.

## Usage | 使用

```yaml
- name: Kubernetes Dashboard
  hosts: k8s_servers
  become: true
  gather_facts: true
  roles:
    - role: k8s_dashboard_deploy
      vars:
        k8s_dashboard_domain: k8s-dashboard.example.com
```

## Verification | 验证

```bash
systemctl status kubectl-port-forward
curl -k -o /dev/null -w '%{http_code}\n' https://127.0.0.1:8443/
kubectl -n kubernetes-dashboard get pods
cat /root/k8s-dashboard-token.txt          # paste into the dashboard login form
```

## Rollback | 回滚

* A failed port-forward change is rolled back automatically from the `backup: true` copy of the unit file.
* Remove everything: `systemctl disable --now kubectl-port-forward`,
  `kubectl delete -f /usr/local/share/k8s-dashboard/admin-user.yaml -f /usr/local/share/k8s-dashboard/recommended-v2.7.0.yaml`,
  then delete `/root/k8s-dashboard-token.txt`.
