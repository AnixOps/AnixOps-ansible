#!/usr/bin/env python3
"""
Inventory Generator - 从统一配置生成 Ansible Inventory
从 servers-config.yml 读取配置，生成不同环境的 inventory
"""

import sys
import os
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_file: str = "inventory/servers-config.yml") -> Dict[str, Any]:
    """加载服务器配置"""
    # 获取脚本所在目录的父目录（项目根目录）
    # Get the parent directory of the script (project root)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    config_path = project_root / config_file
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def generate_local_inventory(config: Dict[str, Any]) -> Dict[str, Any]:
    """生成本地环境的 inventory (使用环境变量)"""
    inventory = {
        'all': {
            'children': {},
            'vars': {
                "ansible_user": "{{ lookup('env', 'ANSIBLE_USER') | default('root', true) }}",
                "ansible_port": "{{ lookup('env', 'ANSIBLE_PORT') | default('22', true) | int }}",
                "ansible_ssh_private_key_file": "{{ lookup('env', 'SSH_KEY_PATH') | default('~/.ssh/id_rsa', true) }}",
                **config['global_vars']
            }
        }
    }
    
    # 创建所有组
    groups = {}
    for group_name, group_def in config['group_definitions'].items():
        groups[group_name] = {
            'hosts': {},
            'vars': group_def.get('vars', {})
        }
    
    # 添加服务器到对应的组
    for server_name, server_info in config['production_servers'].items():
        host_config = {
            'ansible_host': f"{{{{ lookup('env', '{server_info['env_var']}') }}}}"
        }
        
        # 添加元数据
        if 'alias' in server_info:
            host_config['server_alias'] = server_info['alias']
        if 'location' in server_info:
            host_config['location'] = server_info['location']
        if 'server_environment' in server_info:
            host_config['server_environment'] = server_info['server_environment']
        if 'description' in server_info:
            host_config['description'] = server_info['description']
        
        # 将服务器添加到所有属于的组
        for group in server_info['groups']:
            if group in groups:
                groups[group]['hosts'][server_name] = host_config
    
    inventory['all']['children'] = groups
    return inventory


def generate_github_actions_inventory(config: Dict[str, Any], 
                                      use_secrets: bool = True) -> Dict[str, Any]:
    """生成 GitHub Actions 的 inventory
    
    注意：GitHub Actions 只在 workflow 文件中处理 ${{ secrets.xxx }} 语法
    在 inventory 文件中必须使用 Ansible 的 lookup('env', ...) 语法
    Secrets 应该在 workflow 中设置为环境变量
    
    Note: GitHub Actions only processes ${{ secrets.xxx }} syntax in workflow files
    In inventory files, must use Ansible's lookup('env', ...) syntax
    Secrets should be set as environment variables in the workflow
    """
    inventory = {
        'all': {
            'children': {},
            'vars': config['global_vars'].copy()
        }
    }
    
    # 使用环境变量查找 (在 GitHub Actions 中，secrets 会被设置为环境变量)
    # Use environment variable lookups (in GitHub Actions, secrets are set as env vars)
    inventory['all']['vars'].update({
        'ansible_user': "{{ lookup('env', 'ANSIBLE_USER') | default('root', true) }}",
        'ansible_port': "{{ lookup('env', 'ANSIBLE_PORT') | default('22', true) | int }}",
        'ansible_ssh_private_key_file': "~/.ssh/id_rsa"
    })
    
    # 创建所有组
    groups = {}
    for group_name, group_def in config['group_definitions'].items():
        groups[group_name] = {
            'hosts': {},
            'vars': group_def.get('vars', {})
        }
    
    # 添加 GitHub Actions 服务器
    for server_name, server_info in config['github_actions_servers'].items():
        # 使用 Ansible 环境变量查找语法
        # Use Ansible environment variable lookup syntax
        ansible_host = f"{{{{ lookup('env', '{server_info['secret_name']}') }}}}"
        
        host_config = {
            'ansible_host': ansible_host
        }
        
        # 添加元数据
        if 'alias' in server_info:
            host_config['server_alias'] = server_info['alias']
        if 'location' in server_info:
            host_config['location'] = server_info['location']
        if 'server_environment' in server_info:
            host_config['server_environment'] = server_info['server_environment']
        
        # 将服务器添加到所有属于的组
        for group in server_info['groups']:
            if group in groups:
                groups[group]['hosts'][server_name] = host_config
    
    inventory['all']['children'] = groups
    return inventory


def generate_inventory_yaml(inventory: Dict[str, Any]) -> str:
    """生成 YAML 格式的 inventory"""
    
    # Custom dumper to handle Jinja2 templates properly
    class NoAliasDumper(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True
    
    # 自定义字符串表示器，对 Jinja2 模板使用双引号
    # Custom string representer: use double quotes for Jinja2 templates
    def represent_str(dumper, data):
        # 如果字符串包含 Jinja2 模板语法，使用双引号样式
        # If string contains Jinja2 template syntax, use double-quoted style
        if '{{' in data and '}}' in data:
            # 使用双引号样式 (") 而不是单引号 (')
            # Use double-quoted style (") instead of single-quoted (')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
        # 对于普通字符串，使用默认样式
        # For regular strings, use default style
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
    
    # 注册自定义的字符串表示器
    # Register custom string representer
    NoAliasDumper.add_representer(str, represent_str)
    
    return yaml.dump(inventory, 
                     Dumper=NoAliasDumper,
                     default_flow_style=False, 
                     allow_unicode=True,
                     sort_keys=False,
                     indent=2)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python generate_inventory.py [local|github-actions]")
        print("\nExamples:")
        print("  python generate_inventory.py local")
        print("  python generate_inventory.py github-actions")
        sys.exit(1)
    
    mode = sys.argv[1]
    config = load_config()
    
    if mode == 'local':
        print("# 本地环境 Inventory (使用环境变量)")
        print("# 从 servers-config.yml 生成")
        print()
        inventory = generate_local_inventory(config)
        print(generate_inventory_yaml(inventory))
        
    elif mode == 'github-actions':
        print("# GitHub Actions Inventory (使用 Secrets)")
        print("# 从 servers-config.yml 生成")
        print()
        inventory = generate_github_actions_inventory(config, use_secrets=True)
        print(generate_inventory_yaml(inventory))
        
    else:
        print(f"Unknown mode: {mode}")
        print("Available modes: local, github-actions")
        sys.exit(1)


if __name__ == '__main__':
    main()
