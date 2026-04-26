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

# 激活虚拟环境
VENV_PATH="${PROJECT_ROOT}/venv"
if [ -d "$VENV_PATH" ]; then
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        echo -e "${GREEN}✅ 已激活虚拟环境: $VENV_PATH${NC}"
    else
        echo -e "${YELLOW}⚠️  虚拟环境存在但 activate 文件未找到: $VENV_PATH${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  虚拟环境不存在: $VENV_PATH${NC}"
    echo -e "${YELLOW}   提示: 可以运行 'python3 -m venv $VENV_PATH' 创建虚拟环境${NC}"
fi

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

# 加载环境变量（安全方式，忽略注释和空行）
load_env() {
    local env_file="${1:-.env}"
    if [ ! -f "$env_file" ]; then
        print_error "Environment file not found: $env_file"
        return 1
    fi
    
    print_step "Loading environment variables from $env_file"
    
    # 使用 set -a 自动 export 所有变量
    set -a
    # 只加载非注释、非空行且包含等号的行
    while IFS= read -r line || [ -n "$line" ]; do
        # 跳过注释和空行
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$line" ]] && continue
        # 只处理包含等号的行
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            eval "export $line"
        fi
    done < "$env_file"
    set +a
    
    print_success "Environment variables loaded"
    return 0
}

# 显示使用说明
show_usage() {
    cat << EOF
$(print_header "AnixOps Deployment Tool")

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  quick-setup               快速初始化服务器（主机名 + 监控 + 防火墙）
  deploy-local              创建本地 Kind 集群（不部署应用）
  deploy-remote-test        创建远程 K3s 测试集群（波兰服务器）
  deploy-production         部署到生产环境 K3s 集群
  deploy-k8s-control-panel  部署 K8s 控制面板（Dashboard + 反向代理 + SSL）
  cleanup-local             清理本地 Kind 集群
  cleanup-remote-test       清理远程测试集群
  cleanup-production        清理生产环境（谨慎使用）
  status-local              查看本地集群状态
  status-remote-test        查看远程测试集群状态
  status-production         查看生产集群状态
  test                      运行测试
  help                      显示此帮助信息

Options:
  -t, --token TOKEN         Cloudflare Tunnel Token (仅生产环境需要)
  -i, --inventory FILE      指定 inventory 文件 (默认: inventories/production/hosts.yml)
  --vault-password FILE     Vault 密码文件
  --ask-vault-pass          交互式输入 Vault 密码
  --tags TAGS               只运行指定的 tags
  --skip-tags TAGS          跳过指定的 tags
  -v, --verbose             详细输出
  --dry-run                 测试运行（不执行实际操作）

Examples:
  # 快速初始化所有服务器（设置主机名、监控、防火墙）
  $0 quick-setup

  # 快速初始化指定服务器
  $0 quick-setup -i inventories/production/hosts.yml --limit jp-2,uk-1

  # 创建本地 Kind 集群（不需要 token）
  $0 deploy-local

  # 创建远程 K3s 测试集群
  $0 deploy-remote-test

  # 部署 K8s 控制面板（Dashboard + 反向代理 + SSL）
  $0 deploy-k8s-control-panel

  # 只部署 Dashboard，跳过 SSL
  $0 deploy-k8s-control-panel --tags dashboard

  # 只更新 nginx 配置
  $0 deploy-k8s-control-panel --tags config

  # 部署到生产（使用 Vault）
  $0 deploy-production --vault-password ~/.vault_pass

  # 清理本地环境
  $0 cleanup-local

  # 查看远程测试集群状态
  $0 status-remote-test

  # 只创建 K8s 集群，不做其他操作
  $0 deploy-remote-test --tags k8s

  # 详细输出
  $0 deploy-remote-test -v

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

# 检查 Token (已弃用 - Cloudflare Mesh 使用 CLOUDFLARE_MESH_TOKEN)
# check_token 函数已移除，Mesh token 在 cloudflare_mesh role 中验证

# 部署到本地
deploy_local() {
    print_header "Create Local Kind Cluster"
    
    check_requirements
    # 移除 check_token - 不再需要 Cloudflare Token
    
    local ansible_args=()
    ansible_args+=("-i" "$PROJECT_ROOT/inventories/development/hosts.yml")
    
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
    
    print_step "Running Ansible playbook..."
    echo ""
    
    cd "$PROJECT_ROOT"
    ansible-playbook playbooks/platform/kind.yml "${ansible_args[@]}"
    
    if [ $? -eq 0 ]; then
        echo ""
        print_success "Kind cluster created successfully!"
        echo ""
        echo "Next steps:"
        echo "  kubectl get nodes"
        echo "  kubectl get pods --all-namespaces"
        echo ""
        echo "Deploy applications:"
        echo "  kubectl apply -f your-manifest.yaml"
        echo ""
    else
        print_error "Deployment failed"
        exit 1
    fi
}

# 部署到远程测试服务器
deploy_remote_test() {
    print_header "Create Remote K3s Test Cluster"
    
    check_requirements
    
    # 加载环境变量
    load_env "$PROJECT_ROOT/.env" || exit 1
    
    local ansible_args=()
    ansible_args+=("-i" "$PROJECT_ROOT/inventories/production/hosts.yml")
    
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
    
    print_step "Running Ansible playbook..."
    echo ""
    
    cd "$PROJECT_ROOT"
    
    # 导出所有环境变量给 Ansible
    export DE_1_V4_SSH
    export ANSIBLE_USER="${ANSIBLE_USER:-root}"
    export ANSIBLE_PORT="${ANSIBLE_PORT:-22}"
    
    ansible-playbook playbooks/platform/k3s-test.yml "${ansible_args[@]}"
    
    if [ $? -eq 0 ]; then
        echo ""
        print_success "Remote K3s cluster created successfully!"
        echo ""
        echo "Next steps:"
        echo "  export KUBECONFIG=/tmp/k3s-de-1-kubeconfig.yaml"
        echo "  kubectl get nodes"
        echo "  kubectl get pods --all-namespaces"
        echo ""
        echo "Deploy applications:"
        echo "  kubectl apply -f your-manifest.yaml"
        echo ""
    else
        print_error "Deployment failed"
        exit 1
    fi
}

# 部署 WARP Connector（宿主机方式）

# 部署 WARP Connector（宿主机方式）
# 快速设置服务器
quick_setup() {
    print_header "Quick Server Setup (Hostname + Monitoring + Firewall)"
    
    check_requirements
    
    # 加载环境变量
    load_env "$PROJECT_ROOT/.env" || exit 1
    
    print_step "This will configure:"
    echo "  ✓ Server hostname (from inventory)"
    echo "  ✓ Common system configuration"
    echo "  ✓ Node Exporter (monitoring)"
    echo "  ✓ Promtail (log collection)"
    echo "  ✓ Firewall rules"
    echo ""
    
    local ansible_args=()
    
    if [ -n "$INVENTORY_FILE" ]; then
        ansible_args+=("-i" "$INVENTORY_FILE")
    else
        ansible_args+=("-i" "$PROJECT_ROOT/inventories/production/hosts.yml")
    fi
    
    if [ "$VERBOSE" = true ]; then
        ansible_args+=("-vv")
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
    
    print_step "Running Ansible playbook..."
    echo ""
    
    cd "$PROJECT_ROOT"
    ansible-playbook playbooks/provision/quick-setup.yml "${ansible_args[@]}"
    
    if [ $? -eq 0 ]; then
        echo ""
        print_success "Quick setup completed successfully!"
        echo ""
        print_info "Server hostnames have been set to match inventory names"
        print_info "Monitoring agents are now running"
        print_info "Firewall rules are active"
        echo ""
    else
        print_error "Quick setup failed"
        exit 1
    fi
}

# 部署 K8s 控制面板 (Dashboard + 反向代理 + SSL)

# 部署 K8s 控制面板 (Dashboard + 反向代理 + SSL)
deploy_k8s_control_panel() {
    print_header "Deploy K8s Control Panel (Dashboard + Reverse Proxy + SSL)"
    
    check_requirements
    
    # 加载环境变量
    load_env "$PROJECT_ROOT/.env" || exit 1
    
    # 检查必要的环境变量
    if [ "$K8S_CONTROL_SSL_ENABLED" = "true" ]; then
        if [ "$K8S_CONTROL_SSL_METHOD" = "custom" ]; then
            if [ -z "$SSL_CERTIFICATE_PEM" ] || [ -z "$SSL_CERTIFICATE_KEY_PEM" ]; then
                print_error "SSL certificates not configured!"
                echo ""
                echo "Please set in .env file:"
                echo "  SSL_CERTIFICATE_PEM=<base64_encoded_cert>"
                echo "  SSL_CERTIFICATE_KEY_PEM=<base64_encoded_key>"
                echo ""
                exit 1
            fi
            print_success "Using custom SSL certificates"
        elif [ "$K8S_CONTROL_SSL_METHOD" = "acme" ]; then
            if [ -z "$CLOUDFLARE_API_TOKEN" ] && [ -z "$CLOUDFLARE_API_KEY" ]; then
                print_error "Cloudflare credentials not configured!"
                echo ""
                echo "Please set in .env file:"
                echo "  CLOUDFLARE_API_TOKEN=<your_token>"
                echo "  CLOUDFLARE_ZONE_ID=<your_zone_id>"
                echo ""
                exit 1
            fi
            print_success "Using Let's Encrypt (ACME) SSL certificates"
        fi
    else
        print_warning "SSL is disabled. Dashboard will use HTTP only (Cloudflare provides SSL termination)"
    fi
    
    print_step "K8s Control Panel Configuration"
    echo "  SSL Enabled: ${K8S_CONTROL_SSL_ENABLED:-false}"
    echo "  SSL Method: ${K8S_CONTROL_SSL_METHOD:-acme}"
    echo "  Dashboard Domain: ${K8S_DASHBOARD_DOMAIN:-k8s-dashboard.anixops.com}"
    echo "  API Domain: ${K8S_API_DOMAIN:-k8s-api.anixops.com}"
    echo "  Metrics Domain: ${K8S_METRICS_DOMAIN:-k8s-metrics.anixops.com}"
    echo ""
    
    local ansible_args=()
    ansible_args+=("-i" "$PROJECT_ROOT/inventories/production/hosts.yml")
    
    if [ "$VERBOSE" = true ]; then
        ansible_args+=("-vv")
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
    
    print_step "Running Ansible playbook..."
    echo ""
    
    cd "$PROJECT_ROOT"
    
    # 设置环境变量供 Ansible 使用
    export K8S_CONTROL_SSL_ENABLED
    export K8S_CONTROL_SSL_METHOD
    export K8S_DASHBOARD_DOMAIN
    export K8S_API_DOMAIN
    export K8S_METRICS_DOMAIN
    export SSL_CERTIFICATE_PEM
    export SSL_CERTIFICATE_KEY_PEM
    export CLOUDFLARE_API_TOKEN
    export CLOUDFLARE_ZONE_ID
    export ACME_EMAIL
    
    ansible-playbook playbooks/maintenance/k8s_control_plane.yml "${ansible_args[@]}"
    
    if [ $? -eq 0 ]; then
        echo ""
        print_success "K8s Control Panel deployed successfully!"
        echo ""
        echo "═══════════════════════════════════════════════════════════"
        echo "📊 Access Dashboard:"
        echo "   URL: https://${K8S_DASHBOARD_DOMAIN:-k8s-dashboard.anixops.com}"
        echo ""
        echo "🔑 Get Access Token:"
        echo "   ssh root@\$(grep pl-1 inventories/production/hosts.yml | grep ansible_host | awk '{print \$2}' | cut -d= -f2) 'cat /root/k8s-dashboard-token.txt'"
        echo ""
        echo "📋 Or view token directly on server:"
        echo "   /root/k8s-dashboard-token.txt"
        echo ""
        echo "✅ Services:"
        echo "   - Dashboard: https://${K8S_DASHBOARD_DOMAIN:-k8s-dashboard.anixops.com}"
        echo "   - API: https://${K8S_API_DOMAIN:-k8s-api.anixops.com}"
        echo "   - Metrics: https://${K8S_METRICS_DOMAIN:-k8s-metrics.anixops.com}"
        echo "═══════════════════════════════════════════════════════════"
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
    ansible_args+=("-i" "$PROJECT_ROOT/inventories/production/hosts.yml")

    if [ -n "$VAULT_PASSWORD_FILE" ]; then
        ansible_args+=("--vault-password-file" "$VAULT_PASSWORD_FILE")
    elif [ "$ASK_VAULT_PASS" = true ]; then
        ansible_args+=("--ask-vault-pass")
    fi
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
    ansible-playbook playbooks/platform/k3s.yml "${ansible_args[@]}"
    
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
    
    local cluster_name="${1:-anixops-dev}"
    
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
            -i inventories/production/hosts.yml
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
    print_step "All pods:"
    kubectl get pods --all-namespaces 2>/dev/null || echo "  Cannot list pods"
    
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
        -i inventories/production/hosts.yml
}

# 运行测试
run_tests() {
    print_header "Running Tests"
    
    print_step "Syntax check..."
    ansible-playbook playbooks/platform/kind.yml \
        -i inventories/development/hosts.yml \
        --syntax-check
    
    print_step "Local inventory test..."
    ansible-inventory -i inventories/development/hosts.yml --list
    
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
    TARGET_GROUP=""
    MANIFEST_DIR=""
    CLOUDFLARE_MESH_TOKEN=""
    INVENTORY_FILE=""
    
    # 解析参数
    COMMAND=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            quick-setup|deploy-local|deploy-remote-test|deploy-production|deploy-k8s-control-panel|cleanup-local|cleanup-remote-test|cleanup-production|status-local|status-remote-test|status-production|test|help)
                COMMAND="$1"
                shift
                ;;
            -i|--inventory)
                INVENTORY_FILE="$2"
                shift 2
                ;;
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
        quick-setup)
            quick_setup
            ;;
        deploy-local)
            deploy_local
            ;;
        deploy-remote-test)
            deploy_remote_test
            ;;
        deploy-k8s-control-panel)
            deploy_k8s_control_panel
            ;;
        deploy-production)
            deploy_production
            ;;
        cleanup-local)
            cleanup_local
            ;;
        cleanup-remote-test)
            print_warning "Cleanup remote test cluster (K3s on DE-1)"
            echo "SSH to server and run: /usr/local/bin/k3s-uninstall.sh"
            ;;
        cleanup-production)
            cleanup_production
            ;;
        status-local)
            status_local
            ;;
        status-remote-test)
            print_header "Remote Test Cluster Status"
            echo "Export kubeconfig:"
            echo "  export KUBECONFIG=/tmp/k3s-de-1-kubeconfig.yaml"
            echo ""
            if [ -f "/tmp/k3s-de-1-kubeconfig.yaml" ]; then
                export KUBECONFIG=/tmp/k3s-de-1-kubeconfig.yaml
                kubectl get nodes 2>/dev/null || echo "Cannot connect to cluster"
                kubectl get pods --all-namespaces 2>/dev/null || true
            else
                print_error "Kubeconfig not found. Run deploy-remote-test first."
            fi
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
