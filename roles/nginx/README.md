# Nginx Role

灵活的 Nginx 配置管理角色，支持按组配置和单机自定义。

## 功能

- 支持多站点配置。
- 支持按 Ansible 组定义站点 (`nginx_group_sites`)。
- 支持按单台主机定义站点 (`nginx_host_sites`)。
- 支持放置原生的主机特定配置文件 (`templates/hosts/{{ inventory_hostname }}.conf.j2`)。
- 可配置的全局 HTTP 参数。

## 变量说明

### 全局配置 (`nginx`)

```yaml
nginx:
  worker_processes: auto
  worker_connections: 1024
  keepalive_timeout: 65
  client_max_body_size: 16M
  extra_http_configs: |
    # 额外的 HTTP 层配置
    server_names_hash_bucket_size 64;
```

### 站点配置 (`nginx_sites`, `nginx_group_sites`, `nginx_host_sites`)

这三个列表会被合并。

```yaml
nginx_sites:
  - name: my-site
    server_name: example.com
    listen: 80
    root: /var/www/html
    locations:
      - path: /
        try_files: "$uri $uri/ =404"
      - path: /api
        proxy_pass: http://127.0.0.1:3000
```

### 主机特定原生文件

如果在 `roles/nginx/templates/hosts/` 目录下存在与 `inventory_hostname` 匹配的 `.conf.j2` 文件，它将自动部署。

## 使用示例

### 在 `group_vars/webservers.yml` 中：

```yaml
nginx_group_sites:
  - name: internal-app
    server_name: app.internal
    locations:
      - path: /
        proxy_pass: http://app_backend
```

### 在 `host_vars/server01.yml` 中：

```yaml
nginx_host_sites:
  - name: server01-specific
    server_name: debug.example.com
    root: /tmp/debug
```
