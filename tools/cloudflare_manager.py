#!/usr/bin/env python3
"""
Cloudflare DNS & Proxy Manager
用于管理 Cloudflare DNS 记录和代理设置（小黄云加速）

功能：
1. 自动创建/更新 DNS A/AAAA 记录
2. 启用/禁用 Cloudflare 代理（小黄云）
3. 批量管理多个域名记录
"""

import os
import sys
import json
import requests
import argparse
from typing import Dict, List, Optional

# ANSI 颜色代码
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_colored(message: str, color: str = Colors.RESET):
    """打印彩色消息"""
    print(f"{color}{message}{Colors.RESET}")

def print_header(message: str):
    """打印标题"""
    print_colored(f"\n{'='*60}", Colors.CYAN)
    print_colored(f"  {message}", Colors.BOLD + Colors.CYAN)
    print_colored(f"{'='*60}\n", Colors.CYAN)

class CloudflareManager:
    """Cloudflare API 管理器"""

    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: Optional[str] = None,
                 email: Optional[str] = None,
                 api_key: Optional[str] = None):
        """
        初始化 Cloudflare 管理器

        Args:
            api_token: API Token (推荐)
            email: 账户邮箱 (与 api_key 配合使用)
            api_key: Global API Key (与 email 配合使用)
        """
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

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """发送 API 请求"""
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if not result.get('success', False):
                errors = result.get('errors', [])
                error_msg = ', '.join([e.get('message', 'Unknown error') for e in errors])
                raise Exception(f"API Error: {error_msg}")

            return result
        except requests.exceptions.RequestException as e:
            raise Exception(f"请求失败: {str(e)}")

    def list_zones(self) -> List[Dict]:
        """列出所有可用区域"""
        result = self._request('GET', '/zones')
        return result.get('result', [])

    def get_zone_id(self, domain: str) -> Optional[str]:
        """根据域名获取 Zone ID"""
        zones = self.list_zones()
        for zone in zones:
            if zone['name'] == domain or domain.endswith(f".{zone['name']}"):
                return zone['id']
        return None

    def list_dns_records(self, zone_id: str, name: Optional[str] = None,
                        record_type: Optional[str] = None) -> List[Dict]:
        """列出 DNS 记录"""
        params = []
        if name:
            params.append(f"name={name}")
        if record_type:
            params.append(f"type={record_type}")

        query = f"?{'&'.join(params)}" if params else ""
        result = self._request('GET', f'/zones/{zone_id}/dns_records{query}')
        return result.get('result', [])

    def create_dns_record(self, zone_id: str, record_type: str, name: str,
                         content: str, proxied: bool = False, ttl: int = 1) -> Dict:
        """
        创建 DNS 记录

        Args:
            zone_id: Zone ID
            record_type: 记录类型 (A, AAAA, CNAME, etc.)
            name: 记录名称 (例如: www.example.com)
            content: 记录值 (例如: IP 地址)
            proxied: 是否启用 Cloudflare 代理（小黄云）
            ttl: TTL 值 (1 = 自动, proxied=True 时必须为 1)
        """
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "proxied": proxied,
            "ttl": 1 if proxied else ttl
        }

        result = self._request('POST', f'/zones/{zone_id}/dns_records', data)
        return result.get('result', {})

    def update_dns_record(self, zone_id: str, record_id: str, record_type: str,
                         name: str, content: str, proxied: bool = False,
                         ttl: int = 1) -> Dict:
        """更新 DNS 记录"""
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "proxied": proxied,
            "ttl": 1 if proxied else ttl
        }

        result = self._request('PUT', f'/zones/{zone_id}/dns_records/{record_id}', data)
        return result.get('result', {})

    def delete_dns_record(self, zone_id: str, record_id: str) -> bool:
        """删除 DNS 记录"""
        self._request('DELETE', f'/zones/{zone_id}/dns_records/{record_id}')
        return True

    def upsert_dns_record(self, zone_id: str, record_type: str, name: str,
                         content: str, proxied: bool = False, ttl: int = 1) -> Dict:
        """创建或更新 DNS 记录（如果存在则更新，不存在则创建）"""
        existing = self.list_dns_records(zone_id, name=name, record_type=record_type)

        if existing:
            record = existing[0]
            print_colored(f"  ⟳ 更新记录: {name} -> {content} (代理: {'✓' if proxied else '✗'})", Colors.YELLOW)
            return self.update_dns_record(
                zone_id, record['id'], record_type, name, content, proxied, ttl
            )
        else:
            print_colored(f"  ✚ 创建记录: {name} -> {content} (代理: {'✓' if proxied else '✗'})", Colors.GREEN)
            return self.create_dns_record(
                zone_id, record_type, name, content, proxied, ttl
            )

    def toggle_proxy(self, zone_id: str, name: str, proxied: bool) -> Dict:
        """切换 DNS 记录的代理状态"""
        records = self.list_dns_records(zone_id, name=name)

        if not records:
            raise Exception(f"未找到 DNS 记录: {name}")

        record = records[0]
        action = "启用" if proxied else "禁用"
        print_colored(f"  ⚡ {action}小黄云代理: {name}", Colors.CYAN)

        return self.update_dns_record(
            zone_id,
            record['id'],
            record['type'],
            record['name'],
            record['content'],
            proxied=proxied,
            ttl=1 if proxied else record.get('ttl', 1)
        )

def load_from_env(manager: CloudflareManager, zone_id: str):
    """从环境变量加载服务器配置并创建 DNS 记录"""
    print_header("从环境变量加载配置")

    # 域名配置
    base_domain = os.getenv('CLOUDFLARE_BASE_DOMAIN', 'example.com')

    # 服务域名
    services = {
        'GRAFANA_DOMAIN': os.getenv('GRAFANA_DOMAIN'),
        'PROMETHEUS_DOMAIN': os.getenv('PROMETHEUS_DOMAIN'),
        'LOKI_DOMAIN': os.getenv('LOKI_DOMAIN'),
    }

    # 服务器 IP 配置
    servers = {}
    for key, value in os.environ.items():
        if key.endswith('_V4') and not key.endswith('_SSH'):
            # 提取 IP 地址（去除 CIDR 后缀）
            ip = value.split('/')[0] if '/' in value else value
            servers[key] = ip

    if not servers:
        print_colored("  ⚠ 未找到服务器 IP 配置 (格式: *_V4=IP)", Colors.YELLOW)
        return

    print_colored(f"\n找到 {len(servers)} 台服务器:", Colors.BLUE)
    for key, ip in servers.items():
        print_colored(f"  • {key}: {ip}", Colors.BLUE)

    # 创建服务域名记录
    print_colored("\n配置服务域名:", Colors.BLUE)

    # 使用第一台服务器的 IP
    first_server_ip = list(servers.values())[0]

    for service_name, domain in services.items():
        if domain:
            service_type = service_name.replace('_DOMAIN', '').lower()
            try:
                manager.upsert_dns_record(
                    zone_id=zone_id,
                    record_type='A',
                    name=domain,
                    content=first_server_ip,
                    proxied=True  # 默认启用代理
                )
                print_colored(f"  ✓ {service_type}: {domain} -> {first_server_ip}", Colors.GREEN)
            except Exception as e:
                print_colored(f"  ✗ {service_type}: {domain} - {str(e)}", Colors.RED)
        else:
            service_type = service_name.replace('_DOMAIN', '').lower()
            print_colored(f"  ⊘ {service_type}: 未配置域名", Colors.YELLOW)

def interactive_mode():
    """交互式模式"""
    print_header("Cloudflare DNS 管理工具 - 交互式模式")

    # 加载 .env 文件
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        print_colored(f"正在加载环境变量: {env_path}", Colors.BLUE)
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print_colored("✓ 环境变量加载成功\n", Colors.GREEN)
    else:
        print_colored(f"⚠ 未找到 .env 文件: {env_path}\n", Colors.YELLOW)

    # 获取认证信息
    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    email = os.getenv('CLOUDFLARE_EMAIL')
    api_key = os.getenv('CLOUDFLARE_API_KEY')

    if not api_token and not (email and api_key):
        print_colored("错误: 未配置 Cloudflare 认证信息", Colors.RED)
        print_colored("请在 .env 文件中配置以下变量之一:", Colors.YELLOW)
        print_colored("  - CLOUDFLARE_API_TOKEN (推荐)", Colors.YELLOW)
        print_colored("  - CLOUDFLARE_EMAIL + CLOUDFLARE_API_KEY", Colors.YELLOW)
        sys.exit(1)

    try:
        manager = CloudflareManager(api_token=api_token, email=email, api_key=api_key)

        # 获取 Zone ID
        zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
        base_domain = os.getenv('CLOUDFLARE_BASE_DOMAIN', 'example.com')

        if not zone_id:
            print_colored("未配置 CLOUDFLARE_ZONE_ID，正在查询...", Colors.YELLOW)
            zones = manager.list_zones()

            if not zones:
                print_colored("错误: 未找到任何域名区域", Colors.RED)
                sys.exit(1)

            print_colored("\n可用的域名区域:", Colors.CYAN)
            for i, zone in enumerate(zones, 1):
                status = "✓ 活跃" if zone['status'] == 'active' else "✗ 未激活"
                print_colored(f"  {i}. {zone['name']} - {status}", Colors.GREEN)
                print_colored(f"     Zone ID: {zone['id']}", Colors.BLUE)

            choice = input(f"\n请选择区域 [1-{len(zones)}]: ").strip()
            try:
                zone_id = zones[int(choice) - 1]['id']
                base_domain = zones[int(choice) - 1]['name']
            except (ValueError, IndexError):
                print_colored("错误: 无效的选择", Colors.RED)
                sys.exit(1)

        print_colored(f"\n使用域名区域: {base_domain}", Colors.GREEN)
        print_colored(f"Zone ID: {zone_id}\n", Colors.BLUE)

        # 显示菜单
        while True:
            print_colored("\n" + "="*60, Colors.CYAN)
            print_colored("请选择操作:", Colors.BOLD + Colors.CYAN)
            print_colored("="*60, Colors.CYAN)
            print_colored("  1. 查看当前 DNS 记录", Colors.BLUE)
            print_colored("  2. 从 .env 自动配置可观测性服务 DNS", Colors.BLUE)
            print_colored("  3. 手动添加/更新 DNS 记录", Colors.BLUE)
            print_colored("  4. 删除 DNS 记录", Colors.BLUE)
            print_colored("  5. 启用/禁用 Cloudflare 代理（小黄云）", Colors.BLUE)
            print_colored("  0. 退出", Colors.BLUE)
            print_colored("="*60, Colors.CYAN)

            choice = input("\n请输入选项 [0-5]: ").strip()

            if choice == '0':
                print_colored("\n再见！", Colors.GREEN)
                break

            elif choice == '1':
                # 查看 DNS 记录
                print_header("当前 DNS 记录")
                records = manager.list_dns_records(zone_id)

                if not records:
                    print_colored("  未找到任何记录", Colors.YELLOW)
                else:
                    for record in records:
                        proxy_status = "🟡 代理" if record.get('proxied') else "⚪ 直连"
                        print_colored(
                            f"  {proxy_status} {record['name']} ({record['type']}) -> {record['content']}",
                            Colors.GREEN
                        )

            elif choice == '2':
                # 从 .env 自动配置
                load_from_env(manager, zone_id)
                print_colored("\n✓ 自动配置完成", Colors.GREEN)

            elif choice == '3':
                # 手动添加/更新
                print_colored("\n--- 添加/更新 DNS 记录 ---", Colors.CYAN)
                name = input("域名 (例如: grafana.anixops.com): ").strip()
                content = input("IP 地址: ").strip()
                record_type = input("记录类型 [A]: ").strip() or 'A'
                proxy_input = input("启用 Cloudflare 代理? (y/n) [y]: ").strip().lower()
                proxied = proxy_input != 'n'

                try:
                    manager.upsert_dns_record(
                        zone_id=zone_id,
                        record_type=record_type,
                        name=name,
                        content=content,
                        proxied=proxied
                    )
                    print_colored(f"\n✓ 操作成功: {name}", Colors.GREEN)
                except Exception as e:
                    print_colored(f"\n✗ 失败: {str(e)}", Colors.RED)

            elif choice == '4':
                # 删除记录
                print_colored("\n--- 删除 DNS 记录 ---", Colors.CYAN)
                name = input("要删除的域名: ").strip()

                try:
                    records = manager.list_dns_records(zone_id, name=name)

                    if not records:
                        print_colored(f"  ✗ 未找到记录: {name}", Colors.RED)
                    else:
                        confirm = input(f"确认删除 {len(records)} 条记录? (yes/no): ").strip().lower()
                        if confirm == 'yes':
                            for record in records:
                                manager.delete_dns_record(zone_id, record['id'])
                                print_colored(f"  ✓ 已删除: {record['name']} ({record['type']})", Colors.GREEN)
                        else:
                            print_colored("  取消操作", Colors.YELLOW)
                except Exception as e:
                    print_colored(f"\n✗ 失败: {str(e)}", Colors.RED)

            elif choice == '5':
                # 切换代理
                print_colored("\n--- 切换 Cloudflare 代理状态 ---", Colors.CYAN)
                name = input("域名: ").strip()
                action = input("启用(on)还是禁用(off)代理? [on]: ").strip().lower()
                proxied = action != 'off'

                try:
                    manager.toggle_proxy(zone_id, name, proxied)
                    status = "启用" if proxied else "禁用"
                    print_colored(f"\n✓ 已{status}代理: {name}", Colors.GREEN)
                except Exception as e:
                    print_colored(f"\n✗ 失败: {str(e)}", Colors.RED)

            else:
                print_colored("无效的选项，请重试", Colors.RED)

    except Exception as e:
        print_colored(f"\n✗ 错误: {str(e)}", Colors.RED)
        sys.exit(1)

def main():
    # 检查是否有命令行参数（除了脚本名称）
    if len(sys.argv) == 1:
        # 无参数，使用交互式模式
        interactive_mode()
        return

    # 有参数，使用命令行模式
    parser = argparse.ArgumentParser(
        description='Cloudflare DNS & 代理管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 创建 DNS 记录（不启用代理）
  %(prog)s add -z ZONE_ID -n www.example.com -c 1.2.3.4

  # 创建 DNS 记录并启用小黄云代理
  %(prog)s add -z ZONE_ID -n www.example.com -c 1.2.3.4 --proxy

  # 更新记录（如果存在）
  %(prog)s upsert -z ZONE_ID -n www.example.com -c 1.2.3.4 --proxy

  # 启用小黄云代理
  %(prog)s proxy-on -z ZONE_ID -n www.example.com

  # 禁用小黄云代理
  %(prog)s proxy-off -z ZONE_ID -n www.example.com

  # 从环境变量批量配置
  %(prog)s from-env -z ZONE_ID

  # 列出所有 DNS 记录
  %(prog)s list -z ZONE_ID

环境变量:
  CLOUDFLARE_API_TOKEN    - API Token (推荐)
  CLOUDFLARE_EMAIL        - 账户邮箱
  CLOUDFLARE_API_KEY      - Global API Key
  CLOUDFLARE_ZONE_ID      - Zone ID (可选，可通过 -z 参数指定)
        """
    )

    # 认证参数
    auth_group = parser.add_argument_group('认证')
    auth_group.add_argument('--token', help='Cloudflare API Token')
    auth_group.add_argument('--email', help='Cloudflare 账户邮箱')
    auth_group.add_argument('--api-key', help='Cloudflare Global API Key')

    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出 DNS 记录')
    list_parser.add_argument('-z', '--zone-id', required=True, help='Zone ID')
    list_parser.add_argument('-n', '--name', help='过滤记录名称')
    list_parser.add_argument('-t', '--type', help='过滤记录类型 (A, AAAA, CNAME, etc.)')

    # add 命令
    add_parser = subparsers.add_parser('add', help='创建 DNS 记录')
    add_parser.add_argument('-z', '--zone-id', required=True, help='Zone ID')
    add_parser.add_argument('-t', '--type', default='A', help='记录类型 (默认: A)')
    add_parser.add_argument('-n', '--name', required=True, help='记录名称')
    add_parser.add_argument('-c', '--content', required=True, help='记录值 (IP 地址)')
    add_parser.add_argument('--proxy', action='store_true', help='启用小黄云代理')
    add_parser.add_argument('--ttl', type=int, default=1, help='TTL 值 (默认: 1=自动)')

    # upsert 命令
    upsert_parser = subparsers.add_parser('upsert', help='创建或更新 DNS 记录')
    upsert_parser.add_argument('-z', '--zone-id', required=True, help='Zone ID')
    upsert_parser.add_argument('-t', '--type', default='A', help='记录类型 (默认: A)')
    upsert_parser.add_argument('-n', '--name', required=True, help='记录名称')
    upsert_parser.add_argument('-c', '--content', required=True, help='记录值 (IP 地址)')
    upsert_parser.add_argument('--proxy', action='store_true', help='启用小黄云代理')
    upsert_parser.add_argument('--ttl', type=int, default=1, help='TTL 值 (默认: 1=自动)')

    # delete 命令
    delete_parser = subparsers.add_parser('delete', help='删除 DNS 记录')
    delete_parser.add_argument('-z', '--zone-id', required=True, help='Zone ID')
    delete_parser.add_argument('-n', '--name', required=True, help='记录名称')
    delete_parser.add_argument('-t', '--type', help='记录类型')

    # proxy-on 命令
    proxy_on_parser = subparsers.add_parser('proxy-on', help='启用小黄云代理')
    proxy_on_parser.add_argument('-z', '--zone-id', required=True, help='Zone ID')
    proxy_on_parser.add_argument('-n', '--name', required=True, help='记录名称')

    # proxy-off 命令
    proxy_off_parser = subparsers.add_parser('proxy-off', help='禁用小黄云代理')
    proxy_off_parser.add_argument('-z', '--zone-id', required=True, help='Zone ID')
    proxy_off_parser.add_argument('-n', '--name', required=True, help='记录名称')

    # from-env 命令
    from_env_parser = subparsers.add_parser('from-env', help='从环境变量批量配置')
    from_env_parser.add_argument('-z', '--zone-id', required=True, help='Zone ID')

    # zones 命令
    subparsers.add_parser('zones', help='列出所有可用区域')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        # 从参数或环境变量获取认证信息
        api_token = args.token or os.getenv('CLOUDFLARE_API_TOKEN')
        email = args.email or os.getenv('CLOUDFLARE_EMAIL')
        api_key = args.api_key or os.getenv('CLOUDFLARE_API_KEY')

        manager = CloudflareManager(api_token=api_token, email=email, api_key=api_key)

        # 执行命令
        if args.command == 'zones':
            print_header("可用区域列表")
            zones = manager.list_zones()
            for zone in zones:
                status = "✓" if zone['status'] == 'active' else "✗"
                print_colored(f"  {status} {zone['name']}", Colors.GREEN)
                print_colored(f"    Zone ID: {zone['id']}", Colors.BLUE)

        elif args.command == 'list':
            print_header(f"DNS 记录列表 - Zone: {args.zone_id}")
            records = manager.list_dns_records(args.zone_id, args.name, args.type)

            if not records:
                print_colored("  未找到记录", Colors.YELLOW)
            else:
                for record in records:
                    proxy_status = "🟡" if record.get('proxied') else "⚪"
                    print_colored(
                        f"  {proxy_status} {record['name']} ({record['type']}) -> {record['content']}",
                        Colors.GREEN
                    )

        elif args.command == 'add':
            print_header("创建 DNS 记录")
            manager.create_dns_record(
                zone_id=args.zone_id,
                record_type=args.type,
                name=args.name,
                content=args.content,
                proxied=args.proxy,
                ttl=args.ttl
            )
            print_colored(f"\n✓ 成功创建记录: {args.name}", Colors.GREEN)

        elif args.command == 'upsert':
            print_header("创建或更新 DNS 记录")
            manager.upsert_dns_record(
                zone_id=args.zone_id,
                record_type=args.type,
                name=args.name,
                content=args.content,
                proxied=args.proxy,
                ttl=args.ttl
            )
            print_colored(f"\n✓ 操作成功: {args.name}", Colors.GREEN)

        elif args.command == 'delete':
            print_header("删除 DNS 记录")
            records = manager.list_dns_records(args.zone_id, args.name, args.type)

            if not records:
                print_colored(f"  ✗ 未找到记录: {args.name}", Colors.RED)
                return

            for record in records:
                manager.delete_dns_record(args.zone_id, record['id'])
                print_colored(f"  ✓ 已删除: {record['name']} ({record['type']})", Colors.GREEN)

        elif args.command == 'proxy-on':
            print_header("启用小黄云代理")
            manager.toggle_proxy(args.zone_id, args.name, True)
            print_colored(f"\n✓ 已启用代理: {args.name}", Colors.GREEN)

        elif args.command == 'proxy-off':
            print_header("禁用小黄云代理")
            manager.toggle_proxy(args.zone_id, args.name, False)
            print_colored(f"\n✓ 已禁用代理: {args.name}", Colors.GREEN)

        elif args.command == 'from-env':
            load_from_env(manager, args.zone_id)
            print_colored("\n✓ 批量配置完成", Colors.GREEN)

    except Exception as e:
        print_colored(f"\n✗ 错误: {str(e)}", Colors.RED)
        sys.exit(1)

if __name__ == '__main__':
    main()
