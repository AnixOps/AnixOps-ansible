#!/bin/bash
# =============================================================================
# Netmaker 客户端部署脚本 | Netmaker Client Deployment Script
# =============================================================================
# 此脚本简化了 Netmaker 客户端的部署流程
# This script simplifies the Netmaker client deployment process
#
# 用法 | Usage:
#   ./scripts/deploy_netmaker_clients.sh [options]
#
# 选项 | Options:
#   -e, --env         环境 (dev/test/prod) | Environment
#   -l, --limit       限制到特定主机 | Limit to specific hosts
#   -c, --check       检查模式 (dry-run) | Check mode
#   -v, --verbose     详细输出 | Verbose output
#   -h, --help        显示帮助 | Show help
# =============================================================================

set -e

# 获取脚本所在目录和项目根目录 | Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 切换到项目根目录 | Change to project root directory
cd "$PROJECT_ROOT"

# 自动加载 .env 文件 | Automatically load .env file
if [ -f .env ]; then
    # 使用 export 加载环境变量
    set -a
    source .env
    set +a
fi

# 颜色定义 | Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置 | Default configuration
PLAYBOOK="playbooks/netmaker/deploy_netclient.yml"
CHECK_MODE=""
LIMIT=""
VERBOSE=""
ENV=""

# =============================================================================
# 函数定义 | Function Definitions
# =============================================================================

print_banner() {
    echo -e "${BLUE}"
    cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║         Netmaker 客户端部署工具                               ║
║         Netmaker Client Deployment Tool                       ║
║                                                               ║
║         AnixOps Infrastructure Automation                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_help() {
    cat << EOF

用法 | Usage:
  $0 [options]

选项 | Options:
  -e, --env ENV         环境 (dev/test/prod)
                        Environment
                        
  -l, --limit HOSTS     限制到特定主机
                        Limit to specific hosts
                        示例 | Examples: de-1, "de-1,jp-1", dev_servers
                        
  -c, --check           检查模式 (dry-run，不实际执行)
                        Check mode (dry-run, no actual execution)
                        
  -v, --verbose         详细输出 (可多次使用 -vvv)
                        Verbose output (use multiple times -vvv)
                        
  -h, --help            显示此帮助信息
                        Show this help message

示例 | Examples:
  # 部署到所有客户端
  $0
  
  # 部署到开发环境
  $0 --env dev
  
  # 仅部署到特定主机
  $0 --limit de-1
  
  # 部署到多个主机
  $0 --limit "de-1,jp-1"
  
  # 检查模式（不实际执行）
  $0 --check
  
  # 详细输出
  $0 --verbose

环境变量 | Environment Variables:
  NETMAKER_ACCESS_KEY       Netmaker 访问密钥 (必需 | Required)
  NETMAKER_NETWORK_NAME     网络名称 (可选，默认: anixops-mesh)
  PL_1_V4_SSH               Netmaker 服务器地址 (必需 | Required)
  ANSIBLE_USER              SSH 用户名
  SSH_KEY_PATH              SSH 密钥路径

EOF
}

check_prerequisites() {
    print_info "检查前置条件 | Checking prerequisites..."
    
    # 显示当前目录
    print_info "项目根目录 | Project root: $PROJECT_ROOT"
    
    # 检查 Ansible
    if ! command -v ansible-playbook &> /dev/null; then
        print_error "未找到 ansible-playbook 命令"
        print_error "ansible-playbook command not found"
        print_info "请安装 Ansible: pip install ansible"
        exit 1
    fi
    
    # 检查 playbook 文件
    if [ ! -f "$PLAYBOOK" ]; then
        print_error "未找到 Playbook 文件: $PLAYBOOK"
        print_error "Playbook file not found: $PLAYBOOK"
        print_info "完整路径 | Full path: $PROJECT_ROOT/$PLAYBOOK"
        exit 1
    fi
    
    # 检查变量文件
    VAR_FILE="inventory/group_vars/netmaker_clients.yml"
    if [ ! -f "$VAR_FILE" ]; then
        print_warning "未找到变量文件: $VAR_FILE"
        print_warning "Variable file not found: $VAR_FILE"
        print_info "请确保文件存在"
        print_info "Please ensure the file exists"
        exit 1
    fi
    
    # 检查必需的环境变量
    check_environment_variables
    
    print_success "前置条件检查通过 | Prerequisites check passed"
}

check_environment_variables() {
    print_info "检查环境变量 | Checking environment variables..."
    
    local missing_vars=()
    
    # 检查 Netmaker Access Key
    if [ -z "${NETMAKER_ACCESS_KEY}" ]; then
        missing_vars+=("NETMAKER_ACCESS_KEY")
    else
        print_success "✓ NETMAKER_ACCESS_KEY 已设置"
    fi
    
    # 检查 PL-1 服务器地址
    if [ -z "${PL_1_V4_SSH}" ]; then
        missing_vars+=("PL_1_V4_SSH")
    else
        print_success "✓ PL_1_V4_SSH 已设置: ${PL_1_V4_SSH}"
    fi
    
    # 显示网络名称（有默认值，不是必需的）
    if [ -n "${NETMAKER_NETWORK_NAME}" ]; then
        print_success "✓ NETMAKER_NETWORK_NAME 已设置: ${NETMAKER_NETWORK_NAME}"
    else
        print_info "ℹ NETMAKER_NETWORK_NAME 未设置，将使用默认值: anixops-mesh"
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo
        print_error "缺少必需的环境变量 | Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            print_error "  ✗ $var"
        done
        echo
        print_info "请在 .env 文件中设置这些变量 | Please set these variables in .env file:"
        print_info "  NETMAKER_ACCESS_KEY=\"your-access-key-here\""
        print_info "  PL_1_V4_SSH=\"your-server-ip\""
        echo
        print_info "或手动导出 | Or manually export:"
        print_info "  export NETMAKER_ACCESS_KEY='your-access-key-here'"
        print_info "  export PL_1_V4_SSH='your-server-ip'"
        exit 1
    fi
    
    echo
    print_success "环境变量检查通过 | Environment variables check passed"
}

build_ansible_command() {
    local CMD="ansible-playbook $PLAYBOOK"
    
    # 添加 check 模式
    if [ -n "$CHECK_MODE" ]; then
        CMD="$CMD --check"
    fi
    
    # 添加 limit
    if [ -n "$LIMIT" ]; then
        CMD="$CMD --limit $LIMIT"
    fi
    
    # 添加 verbose
    if [ -n "$VERBOSE" ]; then
        CMD="$CMD $VERBOSE"
    fi
    
    # 添加环境变量
    if [ -n "$ENV" ]; then
        local NETWORK_NAME="${ENV}-mesh"
        CMD="$CMD -e netmaker_network_name=$NETWORK_NAME"
    fi
    
    echo "$CMD"
}

run_deployment() {
    print_info "准备运行部署 | Preparing to run deployment..."
    echo
    
    # 构建命令
    CMD=$(build_ansible_command)
    
    # 显示配置摘要
    print_info "配置摘要 | Configuration Summary:"
    echo "  Playbook: $PLAYBOOK"
    [ -n "$ENV" ] && echo "  环境 | Environment: $ENV"
    [ -n "$LIMIT" ] && echo "  目标主机 | Target hosts: $LIMIT"
    [ -n "$CHECK_MODE" ] && echo "  模式 | Mode: Check (dry-run)"
    echo
    
    # 确认执行
    if [ -z "$CHECK_MODE" ]; then
        read -p "确认执行部署? Confirm deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "已取消 | Cancelled"
            exit 0
        fi
    fi
    
    # 执行命令
    print_info "执行命令 | Executing command:"
    echo "  $CMD"
    echo
    
    eval "$CMD"
    
    if [ $? -eq 0 ]; then
        print_success "部署完成 | Deployment completed successfully!"
    else
        print_error "部署失败 | Deployment failed!"
        exit 1
    fi
}

# =============================================================================
# 主程序 | Main Program
# =============================================================================

main() {
    print_banner
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--env)
                ENV="$2"
                shift 2
                ;;
            -l|--limit)
                LIMIT="$2"
                shift 2
                ;;
            -c|--check)
                CHECK_MODE="--check"
                shift
                ;;
            -v|--verbose)
                if [ -z "$VERBOSE" ]; then
                    VERBOSE="-v"
                else
                    VERBOSE="${VERBOSE}v"
                fi
                shift
                ;;
            -h|--help)
                print_help
                exit 0
                ;;
            *)
                print_error "未知选项 | Unknown option: $1"
                print_help
                exit 1
                ;;
        esac
    done
    
    # 检查前置条件
    check_prerequisites
    
    # 运行部署
    run_deployment
    
    echo
    print_success "所有操作完成 | All operations completed"
    print_info "验证部署 | Verify deployment:"
    print_info "  ansible netmaker_clients -m shell -a 'netclient list'"
}

# 运行主程序
main "$@"
