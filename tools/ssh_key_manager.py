#!/usr/bin/env python3
"""
AnixOps SSH Key Manager
=======================
安全管理 SSH 私钥并将其上传到 GitHub Secrets

功能：
1. 读取本地生成的 SSH 私钥
2. 验证私钥格式
3. 通过 GitHub API 加密并上传私钥到 GitHub Secrets
4. 支持交互式输入或命令行参数

使用方法：
    python ssh_key_manager.py
    python ssh_key_manager.py --key-file ~/.ssh/id_rsa --repo owner/repo --token ghp_xxx

依赖：
    pip install PyNaCl requests
"""

import argparse
import base64
import getpass
import json
import os
import sys
from pathlib import Path

try:
    from nacl import encoding, public
    import requests
except ImportError:
    print("❌ 缺少必需的依赖包")
    print("请运行: pip install PyNaCl requests")
    sys.exit(1)


class Colors:
    """终端颜色代码"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_banner():
    """打印欢迎横幅"""
    banner = f"""
{Colors.OKCYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           AnixOps SSH Key Manager v1.0                    ║
║                                                           ║
║     安全管理 SSH 密钥并上传到 GitHub Secrets              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)


def validate_private_key(key_content):
    """
    验证 SSH 私钥格式
    
    Args:
        key_content: SSH 私钥内容
        
    Returns:
        bool: 私钥是否有效
    """
    valid_headers = [
        '-----BEGIN RSA PRIVATE KEY-----',
        '-----BEGIN OPENSSH PRIVATE KEY-----',
        '-----BEGIN EC PRIVATE KEY-----',
        '-----BEGIN PRIVATE KEY-----'
    ]
    
    return any(header in key_content for header in valid_headers)


def read_private_key(key_file_path):
    """
    读取 SSH 私钥文件
    
    Args:
        key_file_path: 私钥文件路径
        
    Returns:
        str: 私钥内容
    """
    try:
        with open(key_file_path, 'r') as f:
            content = f.read()
        
        if not validate_private_key(content):
            print(f"{Colors.FAIL}❌ 无效的 SSH 私钥格式{Colors.ENDC}")
            return None
        
        print(f"{Colors.OKGREEN}✓ 成功读取私钥文件{Colors.ENDC}")
        return content
    
    except FileNotFoundError:
        print(f"{Colors.FAIL}❌ 文件不存在: {key_file_path}{Colors.ENDC}")
        return None
    except PermissionError:
        print(f"{Colors.FAIL}❌ 没有权限读取文件: {key_file_path}{Colors.ENDC}")
        return None
    except Exception as e:
        print(f"{Colors.FAIL}❌ 读取文件时出错: {e}{Colors.ENDC}")
        return None


def get_public_key(github_token, repo_owner, repo_name):
    """
    获取 GitHub 仓库的 Public Key (用于加密 Secrets)
    
    Args:
        github_token: GitHub Personal Access Token
        repo_owner: 仓库所有者
        repo_name: 仓库名称
        
    Returns:
        tuple: (key_id, public_key)
    """
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/public-key"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        print(f"{Colors.OKGREEN}✓ 成功获取仓库 Public Key{Colors.ENDC}")
        return data['key_id'], data['key']
    except requests.exceptions.RequestException as e:
        print(f"{Colors.FAIL}❌ 获取 Public Key 失败: {e}{Colors.ENDC}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None, None


def encrypt_secret(public_key, secret_value):
    """
    使用 GitHub Public Key 加密 Secret
    
    Args:
        public_key: GitHub 仓库的 Public Key
        secret_value: 要加密的值
        
    Returns:
        str: Base64 编码的加密值
    """
    try:
        public_key_obj = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        print(f"{Colors.FAIL}❌ 加密失败: {e}{Colors.ENDC}")
        return None


def upload_secret(github_token, repo_owner, repo_name, secret_name, encrypted_value, key_id):
    """
    上传 Secret 到 GitHub
    
    Args:
        github_token: GitHub Personal Access Token
        repo_owner: 仓库所有者
        repo_name: 仓库名称
        secret_name: Secret 名称
        encrypted_value: 加密后的值
        key_id: Public Key ID
        
    Returns:
        bool: 是否成功
    """
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/{secret_name}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }
    
    try:
        response = requests.put(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"{Colors.OKGREEN}✓ 成功上传 Secret: {secret_name}{Colors.ENDC}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"{Colors.FAIL}❌ 上传 Secret 失败: {e}{Colors.ENDC}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return False


def interactive_mode():
    """交互式模式"""
    print(f"\n{Colors.OKBLUE}📝 请输入以下信息：{Colors.ENDC}\n")
    
    # 获取 SSH 私钥路径
    default_key_path = str(Path.home() / ".ssh" / "id_rsa")
    key_path = input(f"SSH 私钥路径 [{default_key_path}]: ").strip() or default_key_path
    
    # 读取私钥
    private_key = read_private_key(key_path)
    if not private_key:
        return False
    
    # 获取 GitHub 信息
    repo_full = input("GitHub 仓库 (格式: owner/repo): ").strip()
    if '/' not in repo_full:
        print(f"{Colors.FAIL}❌ 无效的仓库格式{Colors.ENDC}")
        return False
    
    repo_owner, repo_name = repo_full.split('/', 1)
    
    # 获取 GitHub Token
    print(f"\n{Colors.WARNING}需要具有 'repo' 权限的 GitHub Personal Access Token")
    print(f"创建 Token: https://github.com/settings/tokens/new{Colors.ENDC}\n")
    github_token = getpass.getpass("GitHub Token: ").strip()
    
    if not github_token:
        print(f"{Colors.FAIL}❌ Token 不能为空{Colors.ENDC}")
        return False
    
    # 获取 Secret 名称
    secret_name = input("Secret 名称 [SSH_PRIVATE_KEY]: ").strip() or "SSH_PRIVATE_KEY"
    
    # 执行上传
    return upload_ssh_key(github_token, repo_owner, repo_name, private_key, secret_name)


def upload_ssh_key(github_token, repo_owner, repo_name, private_key, secret_name):
    """
    上传 SSH 密钥到 GitHub Secrets
    
    Args:
        github_token: GitHub Token
        repo_owner: 仓库所有者
        repo_name: 仓库名称
        private_key: SSH 私钥内容
        secret_name: Secret 名称
        
    Returns:
        bool: 是否成功
    """
    print(f"\n{Colors.OKBLUE}🔐 开始上传 SSH 密钥到 GitHub Secrets...{Colors.ENDC}\n")
    
    # 获取 Public Key
    key_id, public_key = get_public_key(github_token, repo_owner, repo_name)
    if not key_id or not public_key:
        return False
    
    # 加密私钥
    print(f"{Colors.OKBLUE}🔒 正在加密私钥...{Colors.ENDC}")
    encrypted_value = encrypt_secret(public_key, private_key)
    if not encrypted_value:
        return False
    
    print(f"{Colors.OKGREEN}✓ 私钥加密成功{Colors.ENDC}")
    
    # 上传到 GitHub
    print(f"{Colors.OKBLUE}☁️  正在上传到 GitHub...{Colors.ENDC}")
    success = upload_secret(github_token, repo_owner, repo_name, secret_name, encrypted_value, key_id)
    
    if success:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ 成功！SSH 密钥已安全上传到 GitHub Secrets{Colors.ENDC}")
        print(f"\n{Colors.OKCYAN}下一步：{Colors.ENDC}")
        print(f"1. 在 GitHub Actions 中使用: ${{{{ secrets.{secret_name} }}}}")
        print(f"2. 运行 Ansible 部署 workflow")
        return True
    else:
        print(f"\n{Colors.FAIL}❌ 上传失败{Colors.ENDC}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AnixOps SSH Key Manager - 安全管理并上传 SSH 密钥到 GitHub Secrets"
    )
    parser.add_argument('--key-file', help='SSH 私钥文件路径')
    parser.add_argument('--repo', help='GitHub 仓库 (格式: owner/repo)')
    parser.add_argument('--token', help='GitHub Personal Access Token')
    parser.add_argument('--secret-name', default='SSH_PRIVATE_KEY', help='Secret 名称')
    
    args = parser.parse_args()
    
    print_banner()
    
    # 如果提供了所有参数，使用非交互模式
    if args.key_file and args.repo and args.token:
        private_key = read_private_key(args.key_file)
        if not private_key:
            sys.exit(1)
        
        if '/' not in args.repo:
            print(f"{Colors.FAIL}❌ 无效的仓库格式{Colors.ENDC}")
            sys.exit(1)
        
        repo_owner, repo_name = args.repo.split('/', 1)
        success = upload_ssh_key(args.token, repo_owner, repo_name, private_key, args.secret_name)
        sys.exit(0 if success else 1)
    else:
        # 交互模式
        success = interactive_mode()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
