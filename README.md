# AnixOps Ansible

极简编排仓库：`inventory/hosts.yml` 是编排表（主机与分组），`playbooks/deploy.yml` 把仓库外的项目同步到主机并执行命令。

## 使用

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

# 编辑 inventory/hosts.yml 填入主机
ansible-playbook playbooks/deploy.yml --limit <group> \
  -e project_src=/path/to/project -e project_dest=/opt/app -e 'project_cmd=docker compose up -d'
```

## 变量

| 变量 | 必需 | 说明 |
|---|---|---|
| `project_src` | 是 | 本地项目目录（同步源） |
| `project_dest` | 是 | 远端目标目录 |
| `project_cmd` | 否 | 同步后在目标目录执行的命令 |

## SSH / JumpServer

通过 JumpServer 连接时，用环境变量指定 ProxyCommand，仓库里不写跳板地址：

```bash
export ANSIBLE_SSH_COMMON_ARGS='-o ProxyCommand="ssh -W %h:%p -p <port> <jump-user>@<jumpserver-host>"'
```
