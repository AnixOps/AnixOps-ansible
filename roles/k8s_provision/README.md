# k8s_provision

Provision a Kubernetes cluster and verify that it is ready to receive workloads.
Two providers are supported:

| Provider | Use case | What the role does |
|---|---|---|
| `kind` | local development (`playbooks/platform/kind.yml`) | installs a pinned, checksum-verified `kind` + `kubectl`, renders a cluster config to a temporary file and creates the cluster only when `kind get clusters` does not list it |
| `k3s` | remote test / production (`playbooks/platform/k3s-test.yml`, `k3s.yml`) | downloads the k3s installer to a temporary file, runs it once (`creates:`) with `INSTALL_K3S_VERSION` / `INSTALL_K3S_EXEC`, optionally manages `/etc/rancher/k3s/config.yaml` with rollback, waits for the API, the kubeconfig and `Ready` nodes |

部署 Kubernetes 集群（本地 kind 或生产 k3s）并验证集群就绪。

## Behaviour | 行为

1. **Prerequisites** - installs `ca-certificates` + `curl`, checks that a Docker daemon is reachable (kind only),
   installs `kubectl` (kind only; k3s ships its own) and optionally Helm. All downloads are pinned, retried
   (`5 x 10s`) and checksum-verified against the upstream `.sha256` / `.sha256sum` side files by default.
2. **Provision** - `provision_kind.yml` or `provision_k3s.yml` depending on `k8s_provision_provider`.
   k3s hosts with `k8s_role: worker|agent` are installed as agents (`k3s-agent`) and need `k3s_url` + `k3s_token`.
3. **Verify** - `kubectl cluster-info`, `kubectl wait --for=condition=Ready node --all` and
   `kubectl -n kube-system wait --for=condition=Available deployment --all`, each retried
   (`k8s_provision_ready_retries x k8s_provision_ready_delay`). Agents verify that `k3s-agent` is active.

A second run reports `changed=0`: binaries are only downloaded when the installed version differs from the pin,
the k3s installer only runs when `/usr/local/bin/k3s` is missing and the kind cluster is only created when absent.
The role never upgrades a running k3s automatically; it prints a drift notice instead.

## Variables | 变量

Every knob is prefixed `k8s_provision_`; the historical inventory names are still honoured as fallbacks.

| Variable | Default | Fallback (legacy name) | Description |
|---|---|---|---|
| `k8s_provision_provider` | `kind` | `k8s_provider` | `kind` or `k3s` |
| `k8s_provision_role` | `master` | `k8s_role` | `master`/`server` -> k3s server, `worker`/`agent` -> k3s agent |
| `k8s_provision_k3s_version` | `v1.31.5+k3s1` | `k3s_version` | k3s release (`INSTALL_K3S_VERSION`) |
| `k8s_provision_kind_version` | `v0.26.0` | `kind_version` | kind release |
| `k8s_provision_kubectl_version` | `v1.31.5` | `kubectl_version` | kubectl release (kind only) |
| `k8s_provision_helm_version` | `v3.16.4` | `helm_version` | Helm release (only when `k8s_provision_install_helm: true`) |
| `k8s_provision_k3s_server_args` | `--disable traefik --write-kubeconfig-mode 644` | `k3s_server_args`, `k3s_server_options` | flags appended to `k3s server` at install time |
| `k8s_provision_k3s_agent_args` | `""` | `k3s_agent_args` | flags appended to `k3s agent` |
| `k8s_provision_k3s_url` / `k8s_provision_k3s_token` | `""` / `$K3S_TOKEN` | `k3s_url`, `k3s_token` | agent join settings (token is never logged) |
| `k8s_provision_k3s_config` | `{}` | - | optional dict written to `/etc/rancher/k3s/config.yaml` (`backup: true`, restart + health check + rollback on failure) |
| `k8s_provision_k3s_kubeconfig_path` | `/etc/rancher/k3s/k3s.yaml` | `kubeconfig_remote_path` | kubeconfig written by k3s |
| `k8s_provision_kubeconfig_copy_path` | `""` | - | optional extra copy of the kubeconfig (mode 0600) |
| `k8s_provision_kind_cluster_name` | `anixops-dev` | `kind_cluster_name`, `cluster_name` | kind cluster name |
| `k8s_provision_kind_node_image` | `""` | - | pin a `kindest/node` image |
| `k8s_provision_kind_api_server_port` | `0` (random) | `kind_api_server_port` | host port for the kind API server |
| `k8s_provision_kind_nodes` | `[{role: control-plane}]` | - | node list rendered into the kind config |
| `k8s_provision_kind_extra_port_mappings` | `[]` | - | `extraPortMappings` for the first node |
| `k8s_provision_kubeconfig_path` | k3s: `/etc/rancher/k3s/k3s.yaml`, kind: `~/.kube/config` | `kubeconfig_path` | kubeconfig used for verification |
| `k8s_provision_*_checksum` | upstream side file URL | - | `sha256:<hex>` to pin, `""` to skip (`k3s_install_script_checksum` is empty by default because upstream publishes none) |
| `k8s_provision_install_kubectl` / `_install_helm` | kind only / `false` | - | tool toggles |
| `k8s_provision_download_retries` / `_download_delay` | `5` / `10` | - | retry policy for downloads |
| `k8s_provision_wait_timeout`, `_ready_retries`, `_ready_delay` | `300`, `30`, `10` | - | readiness waits |

Lifecycle contract (consumed by `roles/lifecycle`): `k8s_provision_port: 6443`, `k8s_provision_health_url: ""`,
`k8s_provision_backup_files: [/etc/rancher/k3s/config.yaml]`, `k8s_provision_config_dirs: [/etc/rancher/k3s]`,
`k8s_provision_packages: []`, `k8s_provision_service_name: k3s` (`k3s-agent` on workers).

Release URLs are architecture-aware (`x86_64 -> amd64`, `aarch64 -> arm64`, `armv7l -> arm`).

## Usage | 使用

```yaml
- name: Local kind cluster
  hosts: k8s_local
  become: false
  gather_facts: true
  roles:
    - role: k8s_provision
      vars:
        k8s_provision_provider: kind
        k8s_provision_kind_cluster_name: my-dev

- name: k3s server
  hosts: k8s_servers
  become: true
  gather_facts: true
  roles:
    - role: k8s_provision
      vars:
        k8s_provision_provider: k3s
        k8s_provision_k3s_config:
          tls-san: [k3s.example.com]
```

Tags: `prerequisites`, `kind`, `k3s`, `verification`.

## Verification | 验证

```bash
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get nodes -o wide     # k3s
kubectl cluster-info --context kind-anixops-dev                       # kind
systemctl status k3s                                                  # k3s service
```

## Rollback | 回滚

* k3s: `/usr/local/bin/k3s-uninstall.sh` (server) or `/usr/local/bin/k3s-agent-uninstall.sh` (agent) removes
  the installation; a failed `config.yaml` change is rolled back automatically from the `backup: true` copy.
* kind: `kind delete cluster --name <name>`.
