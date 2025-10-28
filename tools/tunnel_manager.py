#!/usr/bin/env python3
"""
Cloudflare Tunnel Manager
=========================
自动化管理 Cloudflare Tunnel 的创建、Token 获取和部署

Features:
  - 通过 Cloudflare API 自动创建 Tunnel
  - 自动获取 Tunnel Token
  - 支持 Ansible 和 Kubernetes 部署
  - 遵循零秘密入库原则
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from typing import Dict, Optional

try:
    import requests
except ImportError:
    print("❌ 请先安装依赖: pip install requests")
    sys.exit(1)


class CloudflareTunnelManager:
    """Cloudflare Tunnel 管理器"""

    def __init__(self, account_id: str, api_token: Optional[str] = None,
                 email: Optional[str] = None, api_key: Optional[str] = None):
        self.account_id = account_id
        self.base_url = "https://api.cloudflare.com/client/v4"
        
        # 支持两种认证方式
        if api_token:
            self.headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
        elif email and api_key:
            self.headers = {
                "X-Auth-Email": email,
                "X-Auth-Key": api_key,
                "Content-Type": "application/json"
            }
        else:
            raise ValueError("必须提供 API Token 或 Email + API Key")

    def list_tunnels(self, tunnel_type: str = "cfd_tunnel") -> list:
        """列出所有 Tunnel"""
        endpoint = f"{self.base_url}/accounts/{self.account_id}/cfd_tunnel"
        
        response = requests.get(endpoint, headers=self.headers)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise Exception(f"API 错误: {result.get('errors')}")
        
        return result.get("result", [])

    def get_tunnel(self, tunnel_id: str) -> Dict:
        """获取指定 Tunnel 的详细信息"""
        endpoint = f"{self.base_url}/accounts/{self.account_id}/cfd_tunnel/{tunnel_id}"
        
        response = requests.get(endpoint, headers=self.headers)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise Exception(f"API 错误: {result.get('errors')}")
        
        return result.get("result")

    def create_tunnel(self, name: str, tunnel_secret: Optional[str] = None) -> Dict:
        """创建新的 Tunnel"""
        endpoint = f"{self.base_url}/accounts/{self.account_id}/cfd_tunnel"
        
        payload = {"name": name, "config_src": "cloudflare"}
        if tunnel_secret:
            payload["tunnel_secret"] = tunnel_secret
        
        response = requests.post(endpoint, headers=self.headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise Exception(f"API 错误: {result.get('errors')}")
        
        return result.get("result")

    def delete_tunnel(self, tunnel_id: str) -> Dict:
        """删除 Tunnel"""
        endpoint = f"{self.base_url}/accounts/{self.account_id}/cfd_tunnel/{tunnel_id}"
        
        response = requests.delete(endpoint, headers=self.headers)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise Exception(f"API 错误: {result.get('errors')}")
        
        return result.get("result")

    def get_tunnel_token(self, tunnel_id: str) -> str:
        """获取 Tunnel Token (关键方法!)"""
        endpoint = f"{self.base_url}/accounts/{self.account_id}/cfd_tunnel/{tunnel_id}/token"
        
        response = requests.get(endpoint, headers=self.headers)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise Exception(f"API 错误: {result.get('errors')}")
        
        return result.get("result")

    def update_tunnel(self, tunnel_id: str, name: Optional[str] = None,
                     tunnel_secret: Optional[str] = None) -> Dict:
        """更新 Tunnel"""
        endpoint = f"{self.base_url}/accounts/{self.account_id}/cfd_tunnel/{tunnel_id}"
        
        payload = {}
        if name:
            payload["name"] = name
        if tunnel_secret:
            payload["tunnel_secret"] = tunnel_secret
        
        response = requests.patch(endpoint, headers=self.headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise Exception(f"API 错误: {result.get('errors')}")
        
        return result.get("result")


def print_success(msg: str):
    """打印成功信息"""
    print(f"\033[92m✅ {msg}\033[0m")


def print_error(msg: str):
    """打印错误信息"""
    print(f"\033[91m❌ {msg}\033[0m", file=sys.stderr)


def print_info(msg: str):
    """打印信息"""
    print(f"\033[94mℹ️  {msg}\033[0m")


def print_warning(msg: str):
    """打印警告"""
    print(f"\033[93m⚠️  {msg}\033[0m")


def create_and_deploy(args):
    """创建 Tunnel 并部署"""
    print_info(f"开始创建 Tunnel: {args.name}")
    
    # 初始化管理器
    try:
        if args.api_token:
            manager = CloudflareTunnelManager(args.account_id, api_token=args.api_token)
        else:
            manager = CloudflareTunnelManager(
                args.account_id,
                email=args.email,
                api_key=args.api_key
            )
    except Exception as e:
        print_error(f"初始化失败: {e}")
        return 1
    
    # 创建 Tunnel
    try:
        print_info("正在创建 Tunnel...")
        tunnel = manager.create_tunnel(args.name)
        tunnel_id = tunnel["id"]
        print_success(f"Tunnel 创建成功! ID: {tunnel_id}")
    except Exception as e:
        print_error(f"创建 Tunnel 失败: {e}")
        return 1
    
    # 获取 Token
    try:
        print_info("正在获取 Tunnel Token...")
        token = manager.get_tunnel_token(tunnel_id)
        print_success("Token 获取成功!")
        print_info(f"Token (前10字符): {token[:10]}...")
    except Exception as e:
        print_error(f"获取 Token 失败: {e}")
        return 1
    
    # 根据部署类型执行相应操作
    if args.deploy_type == "ansible":
        return deploy_ansible(token, args)
    elif args.deploy_type == "kubernetes":
        return deploy_kubernetes(token, tunnel_id, args)
    elif args.deploy_type == "none":
        print_info("\n" + "="*60)
        print_success("Tunnel 创建完成!")
        print_info(f"Tunnel ID: {tunnel_id}")
        print_info(f"Tunnel Name: {args.name}")
        print_info(f"\n请将以下 Token 安全保存:")
        print(f"\n{token}\n")
        print_warning("注意: 此 Token 不会再次显示，请妥善保管!")
        print_info("="*60)
        return 0


def deploy_ansible(token: str, args):
    """部署到 Ansible"""
    print_info("\n开始 Ansible 部署...")
    
    # 设置环境变量（使用新的变量名）
    os.environ["CLOUDFLARE_TUNNEL_TOKEN"] = token
    
    # 可选: 写入 .env 文件
    if args.save_env:
        try:
            with open(".env", "a") as f:
                f.write(f"\n# Cloudflare Tunnel Token (Created: {args.name})\n")
                f.write(f"export CLOUDFLARE_TUNNEL_TOKEN=\"{token}\"\n")
            print_success(".env 文件已更新")
            print_warning("请确保 .env 在 .gitignore 中!")
        except Exception as e:
            print_error(f"写入 .env 失败: {e}")
    
    # 运行 Ansible Playbook
    if args.auto_deploy:
        try:
            print_info("正在运行 Ansible Playbook...")
            cmd = [
                "ansible-playbook",
                "playbooks/cloudflared_playbook.yml"
            ]
            if args.limit:
                cmd.extend(["--limit", args.limit])
            
            subprocess.run(cmd, check=True, env=os.environ)
            print_success("Ansible 部署成功!")
        except subprocess.CalledProcessError as e:
            print_error(f"Ansible 部署失败: {e}")
            return 1
    else:
        print_info("\n下一步: 运行以下命令部署")
        print(f"\n  export CLOUDFLARE_TUNNEL_TOKEN=\"{token[:10]}...\"")
        print("  ansible-playbook playbooks/cloudflared_playbook.yml\n")
    
    return 0


def deploy_kubernetes(token: str, tunnel_id: str, args):
    """部署到 Kubernetes"""
    print_info("\n开始 Kubernetes 部署...")
    
    # 检查 kubectl 是否可用
    try:
        subprocess.run(["kubectl", "version", "--client"], 
                      capture_output=True, check=True)
    except FileNotFoundError:
        print_error("kubectl 未安装！")
        print("\n安装方法:")
        print("  curl -LO \"https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl\"")
        print("  chmod +x kubectl && mv kubectl /usr/local/bin/kubectl")
        return 1
    except subprocess.CalledProcessError:
        print_error("kubectl 不可用！")
        return 1
    
    # 检查 Kubernetes 集群连接
    print_info("检查 Kubernetes 集群连接...")
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            raise Exception("无法连接到 K8s 集群")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
        print_error("无法连接到 Kubernetes 集群！")
        print_error("请确保:")
        print("  1. Kubernetes 集群正在运行")
        print("  2. kubectl 配置正确 (~/.kube/config)")
        print("  3. 设置了 KUBECONFIG 环境变量（如果需要）")
        print("\n测试连接: kubectl cluster-info")
        return 1
    
    print_success("Kubernetes 集群连接正常!")
    
    # 创建 Namespace
    try:
        print_info("正在创建 Namespace: cloudflare-tunnel...")
        subprocess.run(
            ["kubectl", "create", "namespace", "cloudflare-tunnel"],
            capture_output=True,
            text=True,
            check=False  # 如果已存在不报错
        )
        print_success("Namespace 已就绪!")
    except Exception as e:
        print_warning(f"Namespace 创建警告 (可能已存在): {e}")
    
    # 创建 Kubernetes Secret
    try:
        print_info("正在创建 Kubernetes Secret...")
        cmd = [
            "kubectl", "create", "secret", "generic", "cloudflared-token",
            f"--from-literal=token={token}",
            "--namespace=cloudflare-tunnel",
            "--dry-run=client", "-o", "yaml"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # 应用 Secret
        subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=result.stdout,
            text=True,
            check=True
        )
        print_success("Kubernetes Secret 创建成功!")
    except subprocess.CalledProcessError as e:
        print_error(f"创建 Secret 失败: {e}")
        return 1
    
    # 自动部署（如果启用）
    if args.auto_deploy:
        try:
            print_info("正在部署到 Kubernetes...")
            
            # 获取脚本所在目录的父目录（项目根目录）
            script_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(script_dir)
            manifests_dir = os.path.join(repo_root, "k8s_manifests", "cloudflared")
            
            if not os.path.exists(manifests_dir):
                print_error(f"找不到 manifests 目录: {manifests_dir}")
                return 1
            
            # 按顺序应用清单
            for manifest in [
                "00-namespace.yaml",
                "02-configmap.yaml",
                "03-deployment.yaml",
                "04-hpa.yaml",
                "05-pdb.yaml"
            ]:
                path = os.path.join(manifests_dir, manifest)
                if os.path.exists(path):
                    print_info(f"应用 {manifest}...")
                    subprocess.run(["kubectl", "apply", "-f", path], 
                                 capture_output=True, check=True)
                else:
                    print_warning(f"文件不存在: {manifest}")
            
            print_success("Kubernetes 部署成功!")
            
            # 等待 Pods 就绪
            print_info("等待 Pods 就绪...")
            subprocess.run([
                "kubectl", "wait", "--for=condition=available",
                "--timeout=120s", "deployment/cloudflared",
                "-n", "cloudflare-tunnel"
            ], check=True)
            
            print_success("所有 Pods 已就绪!")
        except subprocess.CalledProcessError as e:
            print_error(f"Kubernetes 部署失败: {e}")
            return 1
    else:
        print_info("\n下一步: 运行以下命令部署")
        print("\n  cd k8s_manifests/cloudflared")
        print("  kubectl apply -f .\n")
    
    return 0


def list_tunnels_cmd(args):
    """列出所有 Tunnel"""
    try:
        if args.api_token:
            manager = CloudflareTunnelManager(args.account_id, api_token=args.api_token)
        else:
            manager = CloudflareTunnelManager(
                args.account_id,
                email=args.email,
                api_key=args.api_key
            )
        
        tunnels = manager.list_tunnels()
        
        if not tunnels:
            print_info("没有找到任何 Tunnel")
            return 0
        
        print_info(f"找到 {len(tunnels)} 个 Tunnel:\n")
        
        for tunnel in tunnels:
            print(f"  • Name: {tunnel.get('name')}")
            print(f"    ID: {tunnel.get('id')}")
            print(f"    Status: {tunnel.get('status')}")
            print(f"    Created: {tunnel.get('created_at')}")
            print(f"    Connections: {len(tunnel.get('connections', []))}")
            print()
        
        return 0
    except Exception as e:
        print_error(f"列出 Tunnel 失败: {e}")
        return 1


def get_token_cmd(args):
    """获取指定 Tunnel 的 Token"""
    try:
        if args.api_token:
            manager = CloudflareTunnelManager(args.account_id, api_token=args.api_token)
        else:
            manager = CloudflareTunnelManager(
                args.account_id,
                email=args.email,
                api_key=args.api_key
            )
        
        print_info(f"正在获取 Tunnel {args.tunnel_id} 的 Token...")
        token = manager.get_tunnel_token(args.tunnel_id)
        
        print_success("Token 获取成功!")
        print(f"\n{token}\n")
        
        return 0
    except Exception as e:
        print_error(f"获取 Token 失败: {e}")
        return 1


def delete_tunnel_cmd(args):
    """删除 Tunnel"""
    try:
        if args.api_token:
            manager = CloudflareTunnelManager(args.account_id, api_token=args.api_token)
        else:
            manager = CloudflareTunnelManager(
                args.account_id,
                email=args.email,
                api_key=args.api_key
            )
        
        # 确认删除
        if not args.force:
            confirm = input(f"确定要删除 Tunnel {args.tunnel_id}? (yes/no): ")
            if confirm.lower() != "yes":
                print_info("取消删除")
                return 0
        
        print_info(f"正在删除 Tunnel {args.tunnel_id}...")
        manager.delete_tunnel(args.tunnel_id)
        
        print_success("Tunnel 删除成功!")
        return 0
    except Exception as e:
        print_error(f"删除 Tunnel 失败: {e}")
        return 1


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Cloudflare Tunnel 自动化管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:

  1. 创建 Tunnel 并部署到 Kubernetes:
     ./tunnel_manager.py create my-tunnel \\
       --account-id YOUR_ACCOUNT_ID \\
       --api-token YOUR_API_TOKEN \\
       --deploy-type kubernetes \\
       --auto-deploy

  2. 列出所有 Tunnel:
     ./tunnel_manager.py list \\
       --account-id YOUR_ACCOUNT_ID \\
       --api-token YOUR_API_TOKEN

  3. 获取已有 Tunnel 的 Token:
     ./tunnel_manager.py get-token TUNNEL_ID \\
       --account-id YOUR_ACCOUNT_ID \\
       --api-token YOUR_API_TOKEN

环境变量:
  CLOUDFLARE_ACCOUNT_ID    Cloudflare Account ID
  CLOUDFLARE_API_TOKEN     API Token (推荐)
  CLOUDFLARE_EMAIL         Email (与 API Key 配合使用)
  CLOUDFLARE_API_KEY       Global API Key (不推荐)
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 通用参数
    def add_auth_args(p):
        p.add_argument("--account-id", required=True,
                      help="Cloudflare Account ID")
        p.add_argument("--api-token",
                      help="API Token (推荐)")
        p.add_argument("--email",
                      help="Email (与 --api-key 配合)")
        p.add_argument("--api-key",
                      help="Global API Key (不推荐)")
    
    # create 子命令
    create_parser = subparsers.add_parser("create", help="创建新的 Tunnel")
    create_parser.add_argument("name", help="Tunnel 名称")
    add_auth_args(create_parser)
    create_parser.add_argument("--deploy-type", choices=["ansible", "kubernetes", "none"],
                              default="none", help="部署类型")
    create_parser.add_argument("--auto-deploy", action="store_true",
                              help="自动执行部署")
    create_parser.add_argument("--save-env", action="store_true",
                              help="将 Token 保存到 .env 文件")
    create_parser.add_argument("--limit", help="Ansible: 限制部署目标主机")
    
    # list 子命令
    list_parser = subparsers.add_parser("list", help="列出所有 Tunnel")
    add_auth_args(list_parser)
    
    # get-token 子命令
    get_token_parser = subparsers.add_parser("get-token", help="获取 Tunnel Token")
    get_token_parser.add_argument("tunnel_id", help="Tunnel ID")
    add_auth_args(get_token_parser)
    
    # delete 子命令
    delete_parser = subparsers.add_parser("delete", help="删除 Tunnel")
    delete_parser.add_argument("tunnel_id", help="Tunnel ID")
    add_auth_args(delete_parser)
    delete_parser.add_argument("--force", action="store_true",
                              help="不确认直接删除")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 从环境变量读取认证信息（如果未提供）
    if not args.account_id:
        args.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    if not args.api_token:
        args.api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not args.email:
        args.email = os.getenv("CLOUDFLARE_EMAIL")
    if not args.api_key:
        args.api_key = os.getenv("CLOUDFLARE_API_KEY")
    
    # 验证认证信息
    if not args.api_token and not (args.email and args.api_key):
        print_error("必须提供认证信息: --api-token 或 --email + --api-key")
        return 1
    
    # 执行命令
    if args.command == "create":
        return create_and_deploy(args)
    elif args.command == "list":
        return list_tunnels_cmd(args)
    elif args.command == "get-token":
        return get_token_cmd(args)
    elif args.command == "delete":
        return delete_tunnel_cmd(args)


if __name__ == "__main__":
    sys.exit(main())
