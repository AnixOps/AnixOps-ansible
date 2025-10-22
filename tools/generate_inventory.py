#!/usr/bin/env python3
"""
Inventory Generator - 从统一配置生成 Ansible Inventory
从 servers-config.yml 读取配置，生成不同环境的 inventory
"""

import sys
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_file: str = "inventory/servers-config.yml") -> Dict[str, Any]:
    """加载服务器配置"""
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def generate_local_inventory(config: Dict[str, Any]) -> Dict[str, Any]:
    """生成本地环境的 inventory (使用环境变量)"""
    inventory = {
        'all': {
            'children': {},
            'vars': {
                "ansible_user": "{{ lookup('env', 'ANSIBLE_USER') | default('root') }}",
                "ansible_port": "{{ lookup('env', 'ANSIBLE_PORT') | default('22') }}",
                "ansible_ssh_private_key_file": "{{ lookup('env', 'SSH_KEY_PATH') | default('~/.ssh/id_rsa') }}",
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
        if 'environment' in server_info:
            host_config['environment'] = server_info['environment']
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
    """生成 GitHub Actions 的 inventory"""
    inventory = {
        'all': {
            'children': {},
            'vars': config['global_vars'].copy()
        }
    }
    
    if use_secrets:
        # 使用 GitHub Secrets
        inventory['all']['vars'].update({
            'ansible_user': "${{ secrets.ANSIBLE_USER }}",
            'ansible_port': "${{ secrets.ANSIBLE_PORT }}",
            'ansible_ssh_private_key_file': "~/.ssh/id_rsa",
            'deployment_timestamp': "${{ github.run_number }}",
            'deployed_by': "${{ github.actor }}"
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
        if use_secrets:
            ansible_host = f"${{{{ secrets.{server_info['secret_name']} }}}}"
        else:
            ansible_host = f"{{{{ lookup('env', '{server_info['secret_name']}') }}}}"
        
        host_config = {
            'ansible_host': ansible_host
        }
        
        # 添加元数据
        if 'alias' in server_info:
            host_config['server_alias'] = server_info['alias']
        if 'location' in server_info:
            host_config['location'] = server_info['location']
        if 'environment' in server_info:
            host_config['environment'] = server_info['environment']
        
        # 将服务器添加到所有属于的组
        for group in server_info['groups']:
            if group in groups:
                groups[group]['hosts'][server_name] = host_config
    
    inventory['all']['children'] = groups
    return inventory


def generate_inventory_yaml(inventory: Dict[str, Any]) -> str:
    """生成 YAML 格式的 inventory"""
    # 使用 Dumper 禁用别名/锚点，确保在 GitHub Actions 中正常工作
    class NoAliasDumper(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True
    
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
