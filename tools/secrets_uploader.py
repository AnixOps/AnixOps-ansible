#!/usr/bin/env python3
"""
GitHub Secrets Uploader - 从 .env 文件批量上传 Secrets 到 GitHub

功能：
- 读取 .env 文件中的环境变量
- 自动上传到 GitHub Repository Secrets
- 支持交互式和命令行模式
- 显示上传进度和结果
- 支持跳过空值和注释

作者：AnixOps Team
版本：v0.0.2
"""

import os
import sys
import argparse
import base64
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import requests
from nacl import encoding, public


class GitHubSecretsUploader:
    """GitHub Secrets 上传工具"""
    
    def __init__(self, repo: str, token: str):
        """
        初始化上传器
        
        Args:
            repo: GitHub 仓库，格式：owner/repo
            token: GitHub Personal Access Token (需要 repo 权限)
        """
        self.repo = repo
        self.token = token
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
    def get_public_key(self) -> Tuple[str, str]:
        """
        获取仓库的公钥（用于加密 secrets）
        
        Returns:
            (key_id, public_key) 元组
        """
        url = f"{self.api_base}/repos/{self.repo}/actions/secrets/public-key"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            raise Exception(f"获取公钥失败: {response.status_code} - {response.text}")
        
        data = response.json()
        return data["key_id"], data["key"]
    
    def encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """
        使用公钥加密 secret 值
        
        Args:
            public_key: Base64 编码的公钥
            secret_value: 要加密的值
            
        Returns:
            Base64 编码的加密后的值
        """
        public_key_obj = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")
    
    def upload_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        上传单个 secret
        
        Args:
            secret_name: Secret 名称
            secret_value: Secret 值
            
        Returns:
            是否成功
        """
        try:
            # 获取公钥
            key_id, public_key = self.get_public_key()
            
            # 加密 secret
            encrypted_value = self.encrypt_secret(public_key, secret_value)
            
            # 上传 secret
            url = f"{self.api_base}/repos/{self.repo}/actions/secrets/{secret_name}"
            payload = {
                "encrypted_value": encrypted_value,
                "key_id": key_id
            }
            
            response = requests.put(url, headers=self.headers, json=payload)
            
            if response.status_code in [201, 204]:
                return True
            else:
                print(f"  ✗ 上传失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"  ✗ 错误: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """
        测试 GitHub API 连接和权限
        
        Returns:
            连接是否正常
        """
        try:
            url = f"{self.api_base}/repos/{self.repo}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                print(f"✗ 错误: 仓库 {self.repo} 不存在或无权访问")
                return False
            elif response.status_code == 401:
                print("✗ 错误: Token 无效或已过期")
                return False
            else:
                print(f"✗ 错误: API 请求失败 ({response.status_code})")
                return False
        except Exception as e:
            print(f"✗ 错误: 连接失败 - {str(e)}")
            return False


def parse_env_file(env_file: Path) -> Dict[str, str]:
    """
    解析 .env 文件
    
    Args:
        env_file: .env 文件路径
        
    Returns:
        环境变量字典
    """
    if not env_file.exists():
        raise FileNotFoundError(f"文件不存在: {env_file}")
    
    env_vars = {}
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            
            # 解析 KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 移除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # 只添加非空值
                if value:
                    env_vars[key] = value
    
    return env_vars


def filter_secrets(env_vars: Dict[str, str], exclude_patterns: List[str] = None) -> Dict[str, str]:
    """
    过滤需要上传的 secrets
    
    Args:
        env_vars: 所有环境变量
        exclude_patterns: 要排除的模式列表
        
    Returns:
        过滤后的 secrets
    """
    if exclude_patterns is None:
        exclude_patterns = []
    
    filtered = {}
    
    for key, value in env_vars.items():
        # 检查是否匹配排除模式
        should_exclude = False
        for pattern in exclude_patterns:
            if pattern in key:
                should_exclude = True
                break
        
        if not should_exclude:
            filtered[key] = value
    
    return filtered


def print_banner():
    """打印横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           GitHub Secrets Uploader v0.0.2                     ║
║           从 .env 文件批量上传 Secrets                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_summary(total: int, success: int, failed: int):
    """打印上传摘要"""
    print("\n" + "="*60)
    print("📊 上传摘要")
    print("="*60)
    print(f"  总计: {total}")
    print(f"  ✓ 成功: {success}")
    print(f"  ✗ 失败: {failed}")
    print("="*60)


def interactive_mode():
    """交互式模式"""
    print_banner()
    print("🔧 交互式配置模式\n")
    
    # 获取脚本所在目录，默认 .env 在上一级（项目根目录）
    script_dir = Path(__file__).parent
    default_env = script_dir.parent / ".env"
    
    # 获取输入
    env_file = input(f"📁 .env 文件路径 [{default_env}]: ").strip() or str(default_env)
    repo = input("📦 GitHub 仓库 (owner/repo): ").strip()
    
    if not repo or '/' not in repo:
        print("✗ 错误: 仓库格式无效，应为 owner/repo")
        sys.exit(1)
    
    token = input("🔑 GitHub Token (ghp_...): ").strip()
    
    if not token:
        print("✗ 错误: Token 不能为空")
        sys.exit(1)
    
    # 询问是否排除某些变量
    print("\n是否要排除某些变量？(输入关键词，用逗号分隔，留空则全部上传)")
    exclude_input = input("排除模式 [留空]: ").strip()
    exclude_patterns = [p.strip() for p in exclude_input.split(',')] if exclude_input else []
    
    # 执行上传
    upload_secrets(env_file, repo, token, exclude_patterns, interactive=True)


def check_gitignore(env_file: Path) -> bool:
    """
    检查 .env 是否在 .gitignore 中

    Args:
        env_file: .env 文件路径

    Returns:
        .env 是否已在 .gitignore 中
    """
    search_dir = env_file.resolve().parent

    while True:
        gitignore = search_dir / ".gitignore"
        if gitignore.exists():
            try:
                with open(gitignore, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if line == '.env' or line.endswith('/.env'):
                                return True
            except Exception:
                pass

            print(f"  WARNING: .gitignore found at {gitignore}, but '.env' is not listed.")
            print(f"  Your .env file may be accidentally committed to version control.")
            return False

        parent = search_dir.parent
        if parent == search_dir:
            break

        # Stop if we reach a .git directory root
        if (search_dir / ".git").exists():
            print(f"  WARNING: No .gitignore found in the repository root.")
            print(f"  Consider adding '.env' to .gitignore to prevent accidental commits.")
            return False

        search_dir = parent

    # Reached filesystem root
    print(f"  WARNING: No .gitignore found. Consider creating one with '.env' listed.")
    return False


def upload_secrets(env_file: str, repo: str, token: str,
                   exclude_patterns: List[str] = None,
                   interactive: bool = False,
                   dry_run: bool = False):
    """
    执行 secrets 上传

    Args:
        env_file: .env 文件路径
        repo: GitHub 仓库
        token: GitHub Token
        exclude_patterns: 排除模式列表
        interactive: 是否交互式确认
        dry_run: 仅测试，不实际上传
    """
    try:
        env_path = Path(env_file)

        # Security check: verify .env is in .gitignore
        if not check_gitignore(env_path):
            if interactive:
                confirm = input("\nContinue anyway? (yes/no): ").strip().lower()
                if confirm not in ['yes', 'y']:
                    print("Operation cancelled.")
                    sys.exit(0)
            else:
                print("  Proceeding (non-interactive mode).")

        # 解析 .env 文件
        print(f"\n📖 读取文件: {env_file}")
        env_vars = parse_env_file(env_path)
        print(f"✓ 找到 {len(env_vars)} 个环境变量")
        
        # 过滤 secrets
        secrets = filter_secrets(env_vars, exclude_patterns)
        
        if not secrets:
            print("✗ 没有找到需要上传的 secrets")
            sys.exit(1)
        
        print(f"\n📋 准备上传 {len(secrets)} 个 secrets:")
        for i, key in enumerate(secrets.keys(), 1):
            value_preview = secrets[key][:20] + "..." if len(secrets[key]) > 20 else secrets[key]
            print(f"  {i}. {key} = {value_preview}")
        
        # 确认
        if interactive:
            confirm = input(f"\n确认上传到 {repo}? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("✗ 操作已取消")
                sys.exit(0)
        
        if dry_run:
            print("\n🔍 Dry run 模式，不实际上传")
            return
        
        # 初始化上传器
        print(f"\n🔗 连接到 GitHub: {repo}")
        uploader = GitHubSecretsUploader(repo, token)
        
        # 测试连接
        if not uploader.test_connection():
            sys.exit(1)
        print("✓ 连接成功")
        
        # 上传 secrets
        print(f"\n🚀 开始上传 secrets...\n")
        success_count = 0
        failed_count = 0
        
        for i, (key, value) in enumerate(secrets.items(), 1):
            print(f"[{i}/{len(secrets)}] 上传 {key}...", end=" ")
            
            if uploader.upload_secret(key, value):
                print("✓")
                success_count += 1
            else:
                failed_count += 1
        
        # 打印摘要
        print_summary(len(secrets), success_count, failed_count)
        
        if failed_count == 0:
            print("\n🎉 所有 secrets 上传成功！")
        else:
            print(f"\n⚠️  {failed_count} 个 secrets 上传失败，请检查错误信息")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"✗ 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="从 .env 文件批量上传 GitHub Secrets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 交互式模式
  python secrets_uploader.py
  
  # 命令行模式
  python secrets_uploader.py --env .env --repo AnixOps/AnixOps-ansible --token ghp_xxxxx
  
  # 排除某些变量
  python secrets_uploader.py --env .env --repo owner/repo --token ghp_xxx --exclude LOCAL,TEST
  
  # Dry run（测试模式）
  python secrets_uploader.py --env .env --repo owner/repo --token ghp_xxx --dry-run
        """
    )
    
    parser.add_argument(
        '--env',
        default=None,
        help='.env 文件路径（默认：.env）'
    )
    
    parser.add_argument(
        '--repo',
        help='GitHub 仓库，格式：owner/repo'
    )
    
    parser.add_argument(
        '--token',
        help='[DEPRECATED] GitHub Personal Access Token. Use --token-env instead.'
    )

    parser.add_argument(
        '--token-env',
        action='store_true',
        help='Read GitHub token from GITHUB_TOKEN environment variable'
    )
    
    parser.add_argument(
        '--exclude',
        help='要排除的变量关键词，用逗号分隔（如：LOCAL,TEST）'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅测试，不实际上传'
    )
    
    parser.add_argument(
        '--yes',
        action='store_true',
        help='跳过确认，直接上传'
    )
    
    args = parser.parse_args()
    
    # 获取脚本所在目录，默认 .env 在上一级（项目根目录）
    script_dir = Path(__file__).parent
    default_env = script_dir.parent / ".env"
    
    # 检查是否需要交互式模式
    if not args.env and not args.repo and not args.token and not args.token_env:
        interactive_mode()
    else:
        # 命令行模式 — resolve token
        token: Optional[str] = None
        if args.token_env:
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                print("✗ 错误: --token-env 已指定，但 GITHUB_TOKEN 环境变量未设置")
                sys.exit(1)
        if args.token:
            warnings.warn(
                "--token is deprecated. Use --token-env with GITHUB_TOKEN env var instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            print("WARNING: --token is deprecated. Use --token-env with GITHUB_TOKEN instead.")
            token = args.token

        if not args.repo or not token:
            print("✗ 错误: --repo 和认证（--token 或 --token-env）是必需的")
            parser.print_help()
            sys.exit(1)
        
        env_file = args.env or str(default_env)
        exclude_patterns = [p.strip() for p in args.exclude.split(',')] if args.exclude else []
        
        print_banner()
        upload_secrets(
            env_file,
            args.repo,
            token,
            exclude_patterns,
            interactive=not args.yes,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    # 检查依赖
    try:
        import requests
        from nacl import encoding, public
    except ImportError as e:
        print("✗ 错误: 缺少依赖库")
        print("\n请安装依赖:")
        print("  pip install requests PyNaCl")
        sys.exit(1)
    
    main()
