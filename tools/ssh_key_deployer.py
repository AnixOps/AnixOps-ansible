#!/usr/bin/env python3
"""
AnixOps SSH Key Deployer
========================
交互式部署 SSH 公钥到远程服务器

功能：
1. 支持 IPv4 和 IPv6 地址
2. 交互式用户界面
3. 使用 ssh-copy-id 或 scp + ssh 部署公钥
4. 批量部署到多台服务器
5. 支持从 .env 文件读取服务器列表

使用方法：
    python tools/ssh_key_deployer.py
    python tools/ssh_key_deployer.py --key-file ~/.ssh/id_rsa.pub --host 203.0.113.10
    
依赖：
    pip install paramiko scp
"""

import argparse
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import paramiko
    from scp import SCPClient
except ImportError:
    print("❌ 缺少必需的依赖包")
    print("请运行: pip install paramiko scp")
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
║           AnixOps SSH Key Deployer v1.0                   ║
║                                                           ║
║       交互式部署 SSH 公钥到远程服务器                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)


def print_separator():
    """打印分隔线"""
    print(f"{Colors.OKCYAN}{'─' * 63}{Colors.ENDC}")


def validate_ip(ip_str):
    """
    验证 IP 地址格式（IPv4 或 IPv6）
    
    Args:
        ip_str: IP 地址字符串
        
    Returns:
        tuple: (bool, str) 是否有效及 IP 类型
    """
    # IPv4 正则
    ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    # IPv6 正则 (简化版)
    ipv6_pattern = r'^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}|[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4})$'
    
    if re.match(ipv4_pattern, ip_str):
        return True, "IPv4"
    elif re.match(ipv6_pattern, ip_str):
        return True, "IPv6"
    else:
        return False, None


def read_public_key(key_file_path):
    """
    读取 SSH 公钥文件
    
    Args:
        key_file_path: 公钥文件路径
        
    Returns:
        str: 公钥内容
    """
    try:
        with open(key_file_path, 'r') as f:
            content = f.read().strip()
        
        # 验证是否为有效的公钥
        if not (content.startswith('ssh-rsa') or 
                content.startswith('ssh-ed25519') or 
                content.startswith('ecdsa-')):
            print(f"{Colors.FAIL}❌ 无效的 SSH 公钥格式{Colors.ENDC}")
            return None
        
        print(f"{Colors.OKGREEN}✓ 成功读取公钥文件{Colors.ENDC}")
        return content
    
    except FileNotFoundError:
        print(f"{Colors.FAIL}❌ 文件不存在: {key_file_path}{Colors.ENDC}")
        return None
    except Exception as e:
        print(f"{Colors.FAIL}❌ 读取文件时出错: {e}{Colors.ENDC}")
        return None


def deploy_key_ssh_copy_id(host, username, password, key_file):
    """
    使用 ssh-copy-id 部署公钥（推荐方式）
    
    Args:
        host: 服务器地址
        username: SSH 用户名
        password: SSH 密码
        key_file: 公钥文件路径
        
    Returns:
        bool: 是否成功
    """
    try:
        # 检查是否安装了 sshpass
        result = subprocess.run(['which', 'sshpass'], 
                              capture_output=True, 
                              text=True)
        
        if result.returncode != 0:
            print(f"{Colors.WARNING}⚠️  未找到 sshpass 工具{Colors.ENDC}")
            print(f"{Colors.OKBLUE}尝试使用备用方案...{Colors.ENDC}")
            return False
        
        # 使用 sshpass + ssh-copy-id
        cmd = [
            'sshpass', '-p', password,
            'ssh-copy-id',
            '-i', key_file,
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{host}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"{Colors.OKGREEN}✓ 公钥部署成功（使用 ssh-copy-id）{Colors.ENDC}")
            return True
        else:
            print(f"{Colors.FAIL}❌ ssh-copy-id 失败: {result.stderr}{Colors.ENDC}")
            return False
            
    except Exception as e:
        print(f"{Colors.WARNING}⚠️  ssh-copy-id 方式失败: {e}{Colors.ENDC}")
        return False


def deploy_key_paramiko(host, port, username, password, public_key_content):
    """
    使用 Paramiko 部署公钥（备用方式）
    
    Args:
        host: 服务器地址
        port: SSH 端口
        username: SSH 用户名
        password: SSH 密码
        public_key_content: 公钥内容
        
    Returns:
        bool: 是否成功
    """
    ssh = None
    try:
        print(f"{Colors.OKBLUE}📡 正在连接到 {host}...{Colors.ENDC}")
        
        # 创建 SSH 客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
        
        # IPv6 地址需要去掉方括号（如果有）
        connect_host = host.strip('[]')
        
        # 连接
        ssh.connect(
            hostname=connect_host,
            port=port,
            username=username,
            password=password,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        
        print(f"{Colors.OKGREEN}✓ SSH 连接成功{Colors.ENDC}")
        
        # 确保 .ssh 目录存在
        commands = [
            'mkdir -p ~/.ssh',
            'chmod 700 ~/.ssh',
            'touch ~/.ssh/authorized_keys',
            'chmod 600 ~/.ssh/authorized_keys'
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.channel.recv_exit_status()  # 等待命令执行完成
        
        print(f"{Colors.OKBLUE}📝 正在写入公钥...{Colors.ENDC}")

        # Use SFTP to safely write the public key without shell injection risk
        sftp = ssh.open_sftp()

        # Read existing authorized_keys if present
        try:
            with sftp.open('/root/.ssh/authorized_keys', 'r') as f:
                existing_keys = f.read()
        except IOError:
            existing_keys = b''

        # Check if key already exists
        if public_key_content.encode() in existing_keys:
            print(f"{Colors.WARNING}⚠️  公钥已存在，跳过添加{Colors.ENDC}")
            sftp.close()
            return True

        # Append the new public key
        with sftp.open('/root/.ssh/authorized_keys', 'a') as f:
            f.write(public_key_content + '\n')

        sftp.close()

        print(f"{Colors.OKGREEN}✓ 公钥部署成功{Colors.ENDC}")
        return True
        
    except paramiko.AuthenticationException:
        print(f"{Colors.FAIL}❌ 认证失败：用户名或密码错误{Colors.ENDC}")
        return False
    except paramiko.SSHException as e:
        print(f"{Colors.FAIL}❌ SSH 连接错误: {e}{Colors.ENDC}")
        return False
    except Exception as e:
        print(f"{Colors.FAIL}❌ 部署失败: {e}{Colors.ENDC}")
        return False
    finally:
        if ssh:
            ssh.close()


def deploy_to_single_host():
    """单台服务器部署模式"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}📋 单台服务器部署{Colors.ENDC}\n")
    print_separator()
    
    # 1. 获取公钥路径
    default_key = str(Path.home() / ".ssh" / "id_rsa.pub")
    key_file = input(f"\n公钥文件路径 [{default_key}]: ").strip() or default_key
    
    if not Path(key_file).exists():
        print(f"{Colors.FAIL}❌ 公钥文件不存在: {key_file}{Colors.ENDC}")
        print(f"{Colors.OKBLUE}提示：先生成密钥对或使用 ssh_key_manager.py{Colors.ENDC}")
        return False
    
    public_key = read_public_key(key_file)
    if not public_key:
        return False
    
    # 2. 获取服务器信息
    print(f"\n{Colors.OKBLUE}🌐 服务器信息{Colors.ENDC}")
    print_separator()
    
    while True:
        host = input("\n服务器地址 (IPv4/IPv6): ").strip()
        if not host:
            print(f"{Colors.FAIL}❌ 服务器地址不能为空{Colors.ENDC}")
            continue
        
        is_valid, ip_type = validate_ip(host)
        if is_valid:
            print(f"{Colors.OKGREEN}✓ 有效的 {ip_type} 地址{Colors.ENDC}")
            break
        else:
            print(f"{Colors.WARNING}⚠️  无效的 IP 地址格式，请重新输入{Colors.ENDC}")
    
    username = input(f"SSH 用户名 [root]: ").strip() or "root"
    port = input(f"SSH 端口 [22]: ").strip() or "22"
    
    try:
        port = int(port)
    except ValueError:
        print(f"{Colors.FAIL}❌ 无效的端口号{Colors.ENDC}")
        return False
    
    password = getpass.getpass(f"SSH 密码: ")
    
    if not password:
        print(f"{Colors.FAIL}❌ 密码不能为空{Colors.ENDC}")
        return False
    
    # 3. 部署公钥
    print(f"\n{Colors.OKBLUE}🚀 开始部署公钥...{Colors.ENDC}")
    print_separator()
    
    # 尝试 ssh-copy-id 方式
    success = deploy_key_ssh_copy_id(host, username, password, key_file)
    
    # 如果失败，使用 Paramiko 方式
    if not success:
        print(f"{Colors.OKBLUE}🔄 使用备用方案（Paramiko）...{Colors.ENDC}")
        success = deploy_key_paramiko(host, port, username, password, public_key)
    
    if success:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ 成功！公钥已部署到服务器{Colors.ENDC}")
        print(f"\n{Colors.OKCYAN}测试连接：{Colors.ENDC}")
        print(f"ssh -i {key_file.replace('.pub', '')} {username}@{host}")
    
    return success


def deploy_to_multiple_hosts():
    """批量部署模式"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}📋 批量部署模式{Colors.ENDC}\n")
    print_separator()
    
    # 1. 获取公钥路径
    default_key = str(Path.home() / ".ssh" / "id_rsa.pub")
    key_file = input(f"\n公钥文件路径 [{default_key}]: ").strip() or default_key
    
    if not Path(key_file).exists():
        print(f"{Colors.FAIL}❌ 公钥文件不存在: {key_file}{Colors.ENDC}")
        return False
    
    public_key = read_public_key(key_file)
    if not public_key:
        return False
    
    # 2. 获取服务器列表
    print(f"\n{Colors.OKBLUE}🌐 服务器列表（每行一个，格式：IP 或 IP:PORT）{Colors.ENDC}")
    print(f"{Colors.WARNING}输入空行结束{Colors.ENDC}")
    print_separator()
    
    hosts = []
    while True:
        line = input(f"服务器 #{len(hosts) + 1}: ").strip()
        if not line:
            break
        hosts.append(line)
    
    if not hosts:
        print(f"{Colors.FAIL}❌ 未输入任何服务器{Colors.ENDC}")
        return False
    
    # 3. 获取通用配置
    username = input(f"\nSSH 用户名（所有服务器） [root]: ").strip() or "root"
    password = getpass.getpass(f"SSH 密码（所有服务器）: ")
    
    if not password:
        print(f"{Colors.FAIL}❌ 密码不能为空{Colors.ENDC}")
        return False
    
    # 4. 批量部署
    print(f"\n{Colors.OKBLUE}🚀 开始批量部署...{Colors.ENDC}")
    print_separator()
    
    results = []
    for idx, host_str in enumerate(hosts, 1):
        # 解析 host:port
        if ':' in host_str and not '[' in host_str:  # 不是 IPv6
            host, port_str = host_str.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 22
        else:
            host = host_str
            port = 22
        
        print(f"\n{Colors.OKBLUE}[{idx}/{len(hosts)}] 部署到 {host}:{port}{Colors.ENDC}")
        
        # 先尝试 ssh-copy-id
        success = deploy_key_ssh_copy_id(host, username, password, key_file)
        
        # 失败则使用 Paramiko
        if not success:
            success = deploy_key_paramiko(host, port, username, password, public_key)
        
        results.append((host, port, success))
    
    # 5. 汇总结果
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}📊 部署结果汇总{Colors.ENDC}")
    print_separator()
    
    success_count = sum(1 for _, _, s in results if s)
    fail_count = len(results) - success_count
    
    for host, port, success in results:
        status = f"{Colors.OKGREEN}✓{Colors.ENDC}" if success else f"{Colors.FAIL}✗{Colors.ENDC}"
        print(f"{status} {host}:{port}")
    
    print_separator()
    print(f"成功: {Colors.OKGREEN}{success_count}{Colors.ENDC} | "
          f"失败: {Colors.FAIL}{fail_count}{Colors.ENDC}")
    
    return success_count > 0


def read_hosts_from_env():
    """从 .env 文件读取服务器列表"""
    env_file = Path('.env')
    
    if not env_file.exists():
        return []
    
    hosts = []
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # 查找 IP 变量
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                if '_V4' in key or '_V6' in key:
                    # 去除 CIDR 后缀
                    ip = value.split('/')[0]
                    if ip:
                        hosts.append(ip)
    
    return list(set(hosts))  # 去重


def interactive_mode():
    """交互式模式主菜单"""
    while True:
        print(f"\n{Colors.OKBLUE}{Colors.BOLD}📋 选择部署模式{Colors.ENDC}\n")
        print(f"  {Colors.OKGREEN}1.{Colors.ENDC} 单台服务器部署")
        print(f"  {Colors.OKGREEN}2.{Colors.ENDC} 批量部署")
        print(f"  {Colors.OKGREEN}3.{Colors.ENDC} 从 .env 文件批量部署")
        print(f"  {Colors.FAIL}0.{Colors.ENDC} 退出")
        
        choice = input(f"\n请选择 [1]: ").strip() or "1"
        
        if choice == "0":
            print(f"{Colors.OKCYAN}👋 再见！{Colors.ENDC}")
            return True
        elif choice == "1":
            deploy_to_single_host()
        elif choice == "2":
            deploy_to_multiple_hosts()
        elif choice == "3":
            hosts = read_hosts_from_env()
            if not hosts:
                print(f"{Colors.FAIL}❌ 未从 .env 文件中找到服务器 IP{Colors.ENDC}")
                continue

            print(f"\n{Colors.OKGREEN}✓ 从 .env 文件读取到 {len(hosts)} 个服务器{Colors.ENDC}")
            for ip in hosts:
                print(f"  • {ip}")

            confirm = input(f"\n继续部署到这些服务器？[Y/n]: ").strip().lower()
            if confirm in ['', 'y', 'yes']:
                # 获取公钥路径
                default_key = str(Path.home() / ".ssh" / "id_rsa.pub")
                key_file = input(f"\n公钥文件路径 [{default_key}]: ").strip() or default_key

                if not Path(key_file).exists():
                    print(f"{Colors.FAIL}❌ 公钥文件不存在: {key_file}{Colors.ENDC}")
                    continue

                public_key = read_public_key(key_file)
                if not public_key:
                    continue

                username = input(f"\nSSH 用户名（所有服务器） [root]: ").strip() or "root"
                password = getpass.getpass(f"SSH 密码（所有服务器）: ")

                if not password:
                    print(f"{Colors.FAIL}❌ 密码不能为空{Colors.ENDC}")
                    continue

                print(f"\n{Colors.OKBLUE}🚀 开始批量部署...{Colors.ENDC}")
                print_separator()

                results = []
                for idx, host in enumerate(hosts, 1):
                    port = 22
                    print(f"\n{Colors.OKBLUE}[{idx}/{len(hosts)}] 部署到 {host}:{port}{Colors.ENDC}")

                    success = deploy_key_ssh_copy_id(host, username, password, key_file)

                    if not success:
                        success = deploy_key_paramiko(host, port, username, password, public_key)

                    results.append((host, port, success))

                # 汇总结果
                print(f"\n{Colors.OKBLUE}{Colors.BOLD}📊 部署结果汇总{Colors.ENDC}")
                print_separator()

                success_count = sum(1 for _, _, s in results if s)
                fail_count = len(results) - success_count

                for host, port, success in results:
                    status = f"{Colors.OKGREEN}✓{Colors.ENDC}" if success else f"{Colors.FAIL}✗{Colors.ENDC}"
                    print(f"{status} {host}:{port}")

                print_separator()
                print(f"成功: {Colors.OKGREEN}{success_count}{Colors.ENDC} | "
                      f"失败: {Colors.FAIL}{fail_count}{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}❌ 无效的选择{Colors.ENDC}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AnixOps SSH Key Deployer - 交互式部署 SSH 公钥到远程服务器"
    )
    parser.add_argument('--key-file', help='SSH 公钥文件路径')
    parser.add_argument('--host', help='服务器地址')
    parser.add_argument('--user', default='root', help='SSH 用户名')
    parser.add_argument('--port', type=int, default=22, help='SSH 端口')
    
    args = parser.parse_args()
    
    print_banner()
    
    # 非交互模式
    if args.key_file and args.host:
        key_file = args.key_file
        
        if not Path(key_file).exists():
            print(f"{Colors.FAIL}❌ 公钥文件不存在: {key_file}{Colors.ENDC}")
            sys.exit(1)
        
        public_key = read_public_key(key_file)
        if not public_key:
            sys.exit(1)
        
        password = getpass.getpass(f"SSH 密码 ({args.user}@{args.host}): ")
        
        success = deploy_key_ssh_copy_id(args.host, args.user, password, key_file)
        
        if not success:
            success = deploy_key_paramiko(args.host, args.port, args.user, password, public_key)
        
        sys.exit(0 if success else 1)
    else:
        # 交互模式
        interactive_mode()


if __name__ == "__main__":
    main()
