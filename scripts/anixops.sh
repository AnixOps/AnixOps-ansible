#!/bin/bash
# =============================================================================
# AnixOps Deployment Tool
# =============================================================================
# 统一的部署管理脚本
# Unified deployment management script
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 打印函数
print_header() {
    echo ""
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC}  $1"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

# 显示使用说明
show_usage() {
    cat << EOF
$(print_header "AnixOps Deployment Tool")

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  deploy-local              部署到本地 Kind 集群
  deploy-production         部署到生产环境 K3s 集群
  cleanup-local             清理本地 Kind 集群
  cleanup-production        清理生产环境（谨慎使用）
  status-local              查看本地集群状态
  status-production         查看生产集群状态
  test                      运行测试
  help                      显示此帮助信息

Options:
  -t, --token TOKEN         Cloudflare Tunnel Token
  -i, --inventory FILE      指定 inventory 文件
  --vault-password FILE     Vault 密码文件
  --ask-vault-pass          交互式输入 Vault 密码
  --tags TAGS               只运行指定的 tags
  --skip-tags TAGS          跳过指定的 tags
  -v, --verbose             详细输出
  --dry-run                 测试运行（不执行实际操作）

Examples:
  # 部署到本地（直接传入 token）
  $0 deploy-local -t "your-cloudflare-token"

  # 部署到本地（使用环境变量）
  export CLOUDFLARE_TUNNEL_TOKEN="your-token"
  $0 deploy-local

  # 部署到生产（使用 Vault）
  $0 deploy-production --vault-password ~/.vault_pass

  # 清理本地环境
  $0 cleanup-local

  # 查看本地集群状态
  $0 status-local

  # 只部署 K8s，不部署 cloudflared
  $0 deploy-local --tags k8s

  # 详细输出
  $0 deploy-local -v

EOF
}

# 检查必要工具
check_requirements() {
    print_step "Checking requirements..."
    
    local missing_tools=()
    
    if ! command -v ansible-playbook &> /dev/null; then
        missing_tools+=("ansible")
    fi
    
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        echo ""
        echo "Please install:"
        for tool in "${missing_tools[@]}"; do
            echo "  - $tool"
        done
        exit 1
    fi
    
    print_success "All requirements met"
}

# 检查 Token
check_token() {
    if [ -z "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
        print_warning "CLOUDFLARE_TUNNEL_TOKEN not set"
        echo ""
        echo "Please provide your Cloudflare Tunnel Token:"
        read -r -p "Token: " token
        export CLOUDFLARE_TUNNEL_TOKEN="$token"
    else
        print_success "Using CLOUDFLARE_TUNNEL_TOKEN from environment"
    fi
    
    if [ -z "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
        print_error "No token provided. Cannot proceed."
        exit 1
    fi
}

# 部署到本地
deploy_local() {
    print_header "Deploy to Local (Kind)"
    
    check_requirements
    check_token
    
    local ansible_args=()
    ansible_args+=("-i" "$PROJECT_ROOT/inventories/local/hosts.ini")
    
    if [ "$VERBOSE" = true ]; then
        ansible_args+=("-v")
    fi
    
    if [ -n "$TAGS" ]; then
        ansible_args+=("--tags" "$TAGS")
    fi
    
    if [ -n "$SKIP_TAGS" ]; then
        ansible_args+=("--skip-tags" "$SKIP_TAGS")
    fi
    
    if [ "$DRY_RUN" = true ]; then
        ansible_args+=("--check")
        print_warning "Running in DRY-RUN mode"
    fi
    
    ansible_args+=("--extra-vars" "cloudflare_tunnel_token=${CLOUDFLARE_TUNNEL_TOKEN}")
    
    print_step "Running Ansible playbook..."
    echo ""
    
    cd "$PROJECT_ROOT"
    ansible-playbook playbooks/deployment/local.yml "${ansible_args[@]}"
    
    if [ $? -eq 0 ]; then
        echo ""
        print_success "Local deployment completed!"
        echo ""
        echo "Next steps:"
        echo "  kubectl get pods -n cloudflared"
        echo "  kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared"
        echo ""
    else
        print_error "Deployment failed"
        exit 1
    fi
}

# 部署到生产
deploy_production() {
    print_header "Deploy to Production (K3s)"
    
    check_requirements
    
    local ansible_args=()
    ansible_args+=("-i" "$PROJECT_ROOT/inventories/production/hosts.ini")
    
    if [ -n "$VAULT_PASSWORD_FILE" ]; then
        ansible_args+=("--vault-password-file" "$VAULT_PASSWORD_FILE")
    elif [ "$ASK_VAULT_PASS" = true ]; then
        ansible_args+=("--ask-vault-pass")
    fi
    
    if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
        ansible_args+=("--extra-vars" "cloudflare_tunnel_token=${CLOUDFLARE_TUNNEL_TOKEN}")
    elif [ -f "$PROJECT_ROOT/vars/secrets.yml" ]; then
        ansible_args+=("--extra-vars" "@$PROJECT_ROOT/vars/secrets.yml")
    else
        print_error "No credentials provided!"
        echo ""
        echo "Please use one of:"
        echo "  1. -t TOKEN or set CLOUDFLARE_TUNNEL_TOKEN"
        echo "  2. Create vars/secrets.yml with ansible-vault"
        exit 1
    fi
    
    if [ "$VERBOSE" = true ]; then
        ansible_args+=("-v")
    fi
    
    if [ -n "$TAGS" ]; then
        ansible_args+=("--tags" "$TAGS")
    fi
    
    if [ -n "$SKIP_TAGS" ]; then
        ansible_args+=("--skip-tags" "$SKIP_TAGS")
    fi
    
    if [ "$DRY_RUN" = true ]; then
        ansible_args+=("--check")
        print_warning "Running in DRY-RUN mode"
    fi
    
    print_warning "You are about to deploy to PRODUCTION!"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_warning "Deployment cancelled"
        exit 0
    fi
    
    print_step "Running Ansible playbook..."
    echo ""
    
    cd "$PROJECT_ROOT"
    ansible-playbook playbooks/deployment/production.yml "${ansible_args[@]}"
    
    if [ $? -eq 0 ]; then
        echo ""
        print_success "Production deployment completed!"
    else
        print_error "Deployment failed"
        exit 1
    fi
}

# 清理本地环境
cleanup_local() {
    print_header "Cleanup Local Environment"
    
    local cluster_name="${1:-cloudflared-dev}"
    
    if ! command -v kind &> /dev/null; then
        print_error "Kind is not installed"
        exit 1
    fi
    
    if kind get clusters 2>/dev/null | grep -q "^${cluster_name}$"; then
        print_warning "Found Kind cluster: ${cluster_name}"
        read -p "Delete this cluster? (yes/no): " confirm
        
        if [ "$confirm" == "yes" ]; then
            print_step "Deleting Kind cluster..."
            kind delete cluster --name "${cluster_name}"
            print_success "Cluster deleted"
        else
            print_warning "Cancelled"
            exit 0
        fi
    else
        print_warning "Cluster '${cluster_name}' not found"
    fi
    
    # 清理临时文件
    if [ -f "/tmp/kind-config.yaml" ]; then
        rm -f /tmp/kind-config.yaml
        print_success "Cleaned up temporary files"
    fi
    
    print_success "Cleanup completed"
}

# 清理生产环境
cleanup_production() {
    print_header "Cleanup Production Environment"
    
    print_error "This is a DESTRUCTIVE operation!"
    print_warning "This will remove K3s and all deployed applications from production servers"
    echo ""
    read -p "Type 'DELETE PRODUCTION' to confirm: " confirm
    
    if [ "$confirm" != "DELETE PRODUCTION" ]; then
        print_warning "Cancelled"
        exit 0
    fi
    
    print_step "Running cleanup playbook..."
    
    cd "$PROJECT_ROOT"
    
    if [ -f "playbooks/maintenance/cleanup-production.yml" ]; then
        ansible-playbook playbooks/maintenance/cleanup-production.yml \
            -i inventories/production/hosts.ini
    else
        print_warning "Cleanup playbook not found"
        echo ""
        echo "To manually cleanup production:"
        echo "  1. SSH to server"
        echo "  2. Run: /usr/local/bin/k3s-uninstall.sh"
    fi
}

# 查看本地状态
status_local() {
    print_header "Local Environment Status"
    
    if ! command -v kind &> /dev/null; then
        print_error "Kind is not installed"
        exit 1
    fi
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    print_step "Kind clusters:"
    kind get clusters 2>/dev/null || echo "  No clusters found"
    
    echo ""
    print_step "Kubernetes context:"
    kubectl config current-context 2>/dev/null || echo "  No context set"
    
    echo ""
    print_step "Cluster info:"
    kubectl cluster-info 2>/dev/null || echo "  Cluster not accessible"
    
    echo ""
    print_step "Cloudflared pods:"
    kubectl get pods -n cloudflared 2>/dev/null || echo "  Namespace not found"
    
    echo ""
    print_step "All namespaces:"
    kubectl get namespaces 2>/dev/null || echo "  Cannot list namespaces"
}

# 查看生产状态
status_production() {
    print_header "Production Environment Status"
    
    cd "$PROJECT_ROOT"
    
    if [ ! -f "playbooks/maintenance/health-check.yml" ]; then
        print_warning "Health check playbook not found"
        echo ""
        echo "To manually check production:"
        echo "  1. SSH to server"
        echo "  2. Run: kubectl get pods --all-namespaces"
        exit 1
    fi
    
    ansible-playbook playbooks/maintenance/health-check.yml \
        -i inventories/production/hosts.ini
}

# 运行测试
run_tests() {
    print_header "Running Tests"
    
    print_step "Syntax check..."
    ansible-playbook playbooks/deployment/local.yml \
        -i inventories/local/hosts.ini \
        --syntax-check
    
    print_step "Local inventory test..."
    ansible-inventory -i inventories/local/hosts.ini --list
    
    print_success "Tests passed"
}

# 主函数
main() {
    # 默认值
    VERBOSE=false
    DRY_RUN=false
    ASK_VAULT_PASS=false
    VAULT_PASSWORD_FILE=""
    TAGS=""
    SKIP_TAGS=""
    
    # 解析参数
    COMMAND=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            deploy-local|deploy-production|cleanup-local|cleanup-production|status-local|status-production|test|help)
                COMMAND="$1"
                shift
                ;;
            -t|--token)
                export CLOUDFLARE_TUNNEL_TOKEN="$2"
                shift 2
                ;;
            -i|--inventory)
                INVENTORY_FILE="$2"
                shift 2
                ;;
            --vault-password)
                VAULT_PASSWORD_FILE="$2"
                shift 2
                ;;
            --ask-vault-pass)
                ASK_VAULT_PASS=true
                shift
                ;;
            --tags)
                TAGS="$2"
                shift 2
                ;;
            --skip-tags)
                SKIP_TAGS="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                echo ""
                show_usage
                exit 1
                ;;
        esac
    done
    
    # 执行命令
    case $COMMAND in
        deploy-local)
            deploy_local
            ;;
        deploy-production)
            deploy_production
            ;;
        cleanup-local)
            cleanup_local
            ;;
        cleanup-production)
            cleanup_production
            ;;
        status-local)
            status_local
            ;;
        status-production)
            status_production
            ;;
        test)
            run_tests
            ;;
        help|"")
            show_usage
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
