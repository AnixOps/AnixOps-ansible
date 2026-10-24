#!/bin/bash
# =============================================================================
# AnixOps Deployment Tool
# =============================================================================
# 缁熶竴鐨勯儴缃茬鐞嗚剼鏈?
# Unified deployment management script
# =============================================================================

set -e

# 棰滆壊瀹氫箟
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# 鑴氭湰鐩綍
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 婵€娲昏櫄鎷熺幆澧?
VENV_PATH="${PROJECT_ROOT}/venv"
if [ -d "$VENV_PATH" ]; then
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        echo -e "${GREEN}鉁?宸叉縺娲昏櫄鎷熺幆澧? $VENV_PATH${NC}"
    else
        echo -e "${YELLOW}鈿狅笍  铏氭嫙鐜瀛樺湪浣?activate 鏂囦欢鏈壘鍒? $VENV_PATH${NC}"
    fi
else
    echo -e "${YELLOW}鈿狅笍  铏氭嫙鐜涓嶅瓨鍦? $VENV_PATH${NC}"
    echo -e "${YELLOW}   鎻愮ず: 鍙互杩愯 'python3 -m venv $VENV_PATH' 鍒涘缓铏氭嫙鐜${NC}"
fi

# 鎵撳嵃鍑芥暟
print_header() {
    echo ""
    echo -e "${MAGENTA}鈺斺晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晽${NC}"
    echo -e "${MAGENTA}鈺?{NC}  $1"
    echo -e "${MAGENTA}鈺氣晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暆${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}鈩癸笍  $1${NC}"
}

print_success() {
    echo -e "${GREEN}鉁?$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}鈿狅笍  $1${NC}"
}

print_error() {
    echo -e "${RED}鉂?$1${NC}"
}

print_step() {
    echo -e "${CYAN}鈻?$1${NC}"
}

# 鍔犺浇鐜鍙橀噺锛堝畨鍏ㄦ柟寮忥紝蹇界暐娉ㄩ噴鍜岀┖琛岋級
load_env() {
    local env_file="${1:-.env}"
    if [ ! -f "$env_file" ]; then
        print_error "Environment file not found: $env_file"
        return 1
    fi
    
    print_step "Loading environment variables from $env_file"
    
    # 浣跨敤 set -a 鑷姩 export 鎵€鏈夊彉閲?
    set -a
    # 鍙姞杞介潪娉ㄩ噴銆侀潪绌鸿涓斿寘鍚瓑鍙风殑琛?
    while IFS= read -r line || [ -n "$line" ]; do
        # 璺宠繃娉ㄩ噴鍜岀┖琛?
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$line" ]] && continue
        # 鍙鐞嗗寘鍚瓑鍙风殑琛?
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            eval "export $line"
        fi
    done < "$env_file"
    set +a
    
    print_success "Environment variables loaded"
    return 0
}

# 鏄剧ず浣跨敤璇存槑
show_usage() {
    cat << EOF
$(print_header "AnixOps Deployment Tool")

Usage: $0 [COMMAND] [OPTIONS]

Commands:
  quick-setup               蹇€熷垵濮嬪寲鏈嶅姟鍣紙涓绘満鍚?+ 鐩戞帶 + 闃茬伀澧欙級
  deploy-local              鍒涘缓鏈湴 Kind 闆嗙兢锛堜笉閮ㄧ讲搴旂敤锛?
  deploy-remote-test        鍒涘缓杩滅▼ K3s 娴嬭瘯闆嗙兢锛堟尝鍏版湇鍔″櫒锛?
  deploy-production         閮ㄧ讲鍒扮敓浜х幆澧?K3s 闆嗙兢
  deploy-k8s-control-panel  閮ㄧ讲 K8s 鎺у埗闈㈡澘锛圖ashboard + 鍙嶅悜浠ｇ悊 + SSL锛?
  cleanup-local             娓呯悊鏈湴 Kind 闆嗙兢
  cleanup-remote-test       娓呯悊杩滅▼娴嬭瘯闆嗙兢
  cleanup-production        娓呯悊鐢熶骇鐜锛堣皑鎱庝娇鐢級
  status-local              鏌ョ湅鏈湴闆嗙兢鐘舵€?
  status-remote-test        鏌ョ湅杩滅▼娴嬭瘯闆嗙兢鐘舵€?
  status-production         鏌ョ湅鐢熶骇闆嗙兢鐘舵€?

Lifecycle Commands:
  status <role>             鏌ョ湅鏈嶅姟閮ㄧ讲鐘舵€佸拰鍘嗗彶
  rollback <role> [version] 鍥炴粴鏈嶅姟鍒版寚瀹氱増鏈紙prev 鎴栧叿浣撶増鏈彿锛?
  cleanup-role <role>       娓呯悊鏈嶅姟锛堝仠姝€佸垹闄ら厤缃€佷繚鐣欐渶杩戝浠斤級

Options:
  --target <host|group>     闄愬畾鎿嶄綔鐩爣涓绘満鎴栦富鏈虹粍
  --force                   璺宠繃纭鎻愮ず锛岀洿鎺ユ墽琛?
  --dry-run                 娴嬭瘯杩愯锛堜笉鎵ц瀹為檯鎿嶄綔锛?
  --keep-backups <n>        娓呯悊鏃朵繚鐣欐渶杩?N 涓浠斤紙榛樿 5锛?

Examples:
  # 蹇€熷垵濮嬪寲鎵€鏈夋湇鍔″櫒锛堣缃富鏈哄悕銆佺洃鎺с€侀槻鐏锛?
  $0 quick-setup

  # 鏌ョ湅 nginx 鏈嶅姟閮ㄧ讲鐘舵€?
  $0 status nginx

  # 鏌ョ湅鎸囧畾涓绘満鐨?prometheus 鐘舵€?
  $0 status prometheus --target jp-1

  # 鍥炴粴 nginx 鍒颁笂涓€鐗堟湰
  $0 rollback nginx

  # 鍥炴粴 prometheus 鍒版寚瀹氱増鏈?
  $0 rollback nginx v20260426_120000

  # 鍥炴粴鍒版寚瀹氫富鏈?
  $0 rollback nginx --target jp-1

  # 娓呯悊 loki 鏈嶅姟锛堜繚鐣欐渶杩?10 涓浠斤級
  $0 cleanup-role loki --keep-backups 10

  # 寮哄埗娓呯悊锛堣烦杩囩‘璁わ級
  $0 cleanup-role nginx --force

EOF
}

# 妫€鏌ュ繀瑕佸伐鍏?
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

# 妫€鏌?Token (宸插純鐢?- Cloudflare Mesh 浣跨敤 _TOKEN)
# check_token 鍑芥暟宸茬Щ闄わ紝Mesh token 鍦? role 涓獙璇?

# 閮ㄧ讲鍒版湰鍦?
deploy_local() {
    print_header "Create Local Kind Cluster"
    
    check_requirements
    # 绉婚櫎 check_token - 涓嶅啀闇€瑕?Cloudflare Token
    
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

# 閮ㄧ讲鍒拌繙绋嬫祴璇曟湇鍔″櫒
deploy_remote_test() {
    print_header "Create Remote K3s Test Cluster"
    
    check_requirements
    
    # 鍔犺浇鐜鍙橀噺
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
    
    # 瀵煎嚭鎵€鏈夌幆澧冨彉閲忕粰 Ansible
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

# 閮ㄧ讲 WARP Connector锛堝涓绘満鏂瑰紡锛?

# 閮ㄧ讲 WARP Connector锛堝涓绘満鏂瑰紡锛?
# 蹇€熻缃湇鍔″櫒
quick_setup() {
    print_header "Quick Server Setup (Hostname + Monitoring + Firewall)"
    
    check_requirements
    
    # 鍔犺浇鐜鍙橀噺
    load_env "$PROJECT_ROOT/.env" || exit 1
    
    print_step "This will configure:"
    echo "  鉁?Server hostname (from inventory)"
    echo "  鉁?Common system configuration"
    echo "  鉁?Node Exporter (monitoring)"
    echo "  鉁?Promtail (log collection)"
    echo "  鉁?Firewall rules"
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

# 閮ㄧ讲 K8s 鎺у埗闈㈡澘 (Dashboard + 鍙嶅悜浠ｇ悊 + SSL)

# 閮ㄧ讲 K8s 鎺у埗闈㈡澘 (Dashboard + 鍙嶅悜浠ｇ悊 + SSL)
deploy_k8s_control_panel() {
    print_header "Deploy K8s Control Panel (Dashboard + Reverse Proxy + SSL)"
    
    check_requirements
    
    # 鍔犺浇鐜鍙橀噺
    load_env "$PROJECT_ROOT/.env" || exit 1
    
    # 妫€鏌ュ繀瑕佺殑鐜鍙橀噺
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
    
    # 璁剧疆鐜鍙橀噺渚?Ansible 浣跨敤
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
        echo "鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
        echo "馃搳 Access Dashboard:"
        echo "   URL: https://${K8S_DASHBOARD_DOMAIN:-k8s-dashboard.anixops.com}"
        echo ""
        echo "馃攽 Get Access Token:"
        echo "   ssh root@\$(grep pl-1 inventories/production/hosts.yml | grep ansible_host | awk '{print \$2}' | cut -d= -f2) 'cat /root/k8s-dashboard-token.txt'"
        echo ""
        echo "馃搵 Or view token directly on server:"
        echo "   /root/k8s-dashboard-token.txt"
        echo ""
        echo "鉁?Services:"
        echo "   - Dashboard: https://${K8S_DASHBOARD_DOMAIN:-k8s-dashboard.anixops.com}"
        echo "   - API: https://${K8S_API_DOMAIN:-k8s-api.anixops.com}"
        echo "   - Metrics: https://${K8S_METRICS_DOMAIN:-k8s-metrics.anixops.com}"
        echo "鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
        echo ""
    else
        print_error "Deployment failed"
        exit 1
    fi
}

# 閮ㄧ讲鍒扮敓浜?
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

# 娓呯悊鏈湴鐜
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
    
    # 娓呯悊涓存椂鏂囦欢
    if [ -f "/tmp/kind-config.yaml" ]; then
        rm -f /tmp/kind-config.yaml
        print_success "Cleaned up temporary files"
    fi
    
    print_success "Cleanup completed"
}

# 娓呯悊鐢熶骇鐜
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

# 鏌ョ湅鏈湴鐘舵€?
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

# 鏌ョ湅鐢熶骇鐘舵€?
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

# 杩愯娴嬭瘯
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

# =============================================================================
# Lifecycle 鍛戒护鍑芥暟
# =============================================================================

# 鏌ョ湅鏈嶅姟鐘舵€?
lifecycle_status() {
    if [ -z "$LIFECYCLE_ROLE" ]; then
        print_error "蹇呴』鎸囧畾 role 鍚嶇О"
        echo ""
        echo "鐢ㄦ硶: $0 status <role> [--target <host|group>]"
        echo ""
        echo "鏀寔鐨?roles: nginx, prometheus, grafana, loki, promtail, node_exporter, common, "
        exit 1
    fi

    print_header "Service Status: ${LIFECYCLE_ROLE}"

    cd "$PROJECT_ROOT"

    local ansible_args=()
    ansible_args+=("-e" "lifecycle_target_role=${LIFECYCLE_ROLE}")
    ansible_args+=("--tags" "status")

    if [ -n "$LIFECYCLE_TARGET" ]; then
        ansible_args+=("--limit" "${LIFECYCLE_TARGET}")
    fi

    ansible_args+=("-i" "${INVENTORY_FILE:-inventories/production/hosts.yml}")

    if [ "$DRY_RUN" = true ]; then
        print_warning "Dry-run mode - only showing what would be executed"
        echo "ansible-playbook playbooks/maintenance/lifecycle.yml ${ansible_args[*]}"
    else
        ansible-playbook playbooks/maintenance/lifecycle.yml "${ansible_args[@]}"
    fi
}

# 鍥炴粴鏈嶅姟
lifecycle_rollback() {
    if [ -z "$LIFECYCLE_ROLE" ]; then
        print_error "蹇呴』鎸囧畾 role 鍚嶇О"
        echo ""
        echo "鐢ㄦ硶: $0 rollback <role> [version] [--target <host|group>] [--force]"
        echo ""
        echo "鏀寔鐨?roles: nginx, prometheus, grafana, loki, promtail, node_exporter, common"
        echo "version: prev (涓婁竴鐗堟湰) 鎴?vYYYYMMDD_HHMMSS (鍏蜂綋鐗堟湰)"
        exit 1
    fi

    print_header "Rollback Service: ${LIFECYCLE_ROLE}"

    # 鐢ㄦ埛纭
    if [ "$LIFECYCLE_FORCE" != true ]; then
        print_warning "鍗冲皢鍥炴粴 ${LIFECYCLE_ROLE} 鍒?${LIFECYCLE_VERSION:-prev}"
        echo ""
        read -p "纭鎵ц鍥炴粴? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            print_warning "宸插彇娑?
            exit 0
        fi
    fi

    cd "$PROJECT_ROOT"

    local ansible_args=()
    ansible_args+=("-e" "lifecycle_target_role=${LIFECYCLE_ROLE}")
    ansible_args+=("-e" "lifecycle_hook_type=post_rollback")
    ansible_args+=("--tags" "rollback")

    if [ -n "$LIFECYCLE_VERSION" ]; then
        ansible_args+=("-e" "lifecycle_version=${LIFECYCLE_VERSION}")
    fi

    if [ -n "$LIFECYCLE_TARGET" ]; then
        ansible_args+=("--limit" "${LIFECYCLE_TARGET}")
    fi

    ansible_args+=("-i" "${INVENTORY_FILE:-inventories/production/hosts.yml}")

    if [ "$DRY_RUN" = true ]; then
        print_warning "Dry-run mode - only showing what would be executed"
        echo "ansible-playbook playbooks/maintenance/lifecycle.yml ${ansible_args[*]}"
    else
        ansible-playbook playbooks/maintenance/lifecycle.yml "${ansible_args[@]}"
    fi
}

# 娓呯悊鏈嶅姟
lifecycle_cleanup_role() {
    if [ -z "$LIFECYCLE_ROLE" ]; then
        print_error "蹇呴』鎸囧畾 role 鍚嶇О"
        echo ""
        echo "鐢ㄦ硶: $0 cleanup-role <role> [--target <host|group>] [--force] [--keep-backups <n>]"
        echo ""
        echo "鏀寔鐨?roles: nginx, prometheus, grafana, loki, promtail, node_exporter, common, "
        exit 1
    fi

    print_header "Cleanup Service: ${LIFECYCLE_ROLE}"

    print_warning "鈿狅笍 杩欏皢:"
    echo "  - 鍋滄骞剁鐢ㄦ湇鍔?
    echo "  - 鍒犻櫎閰嶇疆鏂囦欢锛堟暟鎹皢褰掓。锛?
    echo "  - 鍒犻櫎鏃у浠斤紙淇濈暀鏈€杩?${LIFECYCLE_KEEP_BACKUPS} 涓級"
    echo ""

    # 鐢ㄦ埛纭
    if [ "$LIFECYCLE_FORCE" != true ]; then
        print_error "杩欐槸涓€涓牬鍧忔€ф搷浣?"
        read -p "杈撳叆 'yes' 纭娓呯悊 ${LIFECYCLE_ROLE}: " confirm
        if [ "$confirm" != "yes" ]; then
            print_warning "宸插彇娑?
            exit 0
        fi
    fi

    cd "$PROJECT_ROOT"

    local ansible_args=()
    ansible_args+=("-e" "lifecycle_target_role=${LIFECYCLE_ROLE}")
    ansible_args+=("-e" "cleanup_confirm=yes")
    ansible_args+=("-e" "cleanup_keep_backups=${LIFECYCLE_KEEP_BACKUPS}")
    ansible_args+=("--tags" "cleanup")

    if [ -n "$LIFECYCLE_TARGET" ]; then
        ansible_args+=("--limit" "${LIFECYCLE_TARGET}")
    fi

    ansible_args+=("-i" "${INVENTORY_FILE:-inventories/production/hosts.yml}")

    if [ "$DRY_RUN" = true ]; then
        print_warning "Dry-run mode - only showing what would be executed"
        echo "ansible-playbook playbooks/maintenance/lifecycle.yml ${ansible_args[*]}"
    else
        ansible-playbook playbooks/maintenance/lifecycle.yml "${ansible_args[@]}"
    fi
}

# 涓诲嚱鏁?
main() {
    # 榛樿鍊?
    VERBOSE=false
    DRY_RUN=false
    ASK_VAULT_PASS=false
    VAULT_PASSWORD_FILE=""
    TAGS=""
    SKIP_TAGS=""
    TARGET_GROUP=""
    MANIFEST_DIR=""
    _TOKEN=""
    INVENTORY_FILE=""

    # Lifecycle 鍛戒护鍙傛暟
    LIFECYCLE_ROLE=""
    LIFECYCLE_VERSION=""
    LIFECYCLE_TARGET=""
    LIFECYCLE_FORCE=false
    LIFECYCLE_KEEP_BACKUPS=5

    # 瑙ｆ瀽鍙傛暟
    COMMAND=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            quick-setup|deploy-local|deploy-remote-test|deploy-production|deploy-k8s-control-panel|cleanup-local|cleanup-remote-test|cleanup-production|status-local|status-remote-test|status-production|test|help|status|rollback|cleanup-role)
                COMMAND="$1"
                shift
                ;;
            # Lifecycle role 鍙傛暟锛堜綅缃弬鏁帮級
            nginx|prometheus|grafana|loki|promtail|node_exporter|common|acme_ssl|firewall)
                if [ "$COMMAND" == "status" ] || [ "$COMMAND" == "rollback" ] || [ "$COMMAND" == "cleanup-role" ]; then
                    LIFECYCLE_ROLE="$1"
                    shift
                else
                    print_error "Unknown option: $1"
                    show_usage
                    exit 1
                fi
                ;;
            # Lifecycle version 鍙傛暟
            prev|v[0-9]*)
                if [ "$COMMAND" == "rollback" ]; then
                    LIFECYCLE_VERSION="$1"
                    shift
                else
                    print_error "Unknown option: $1"
                    show_usage
                    exit 1
                fi
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
            --target)
                LIFECYCLE_TARGET="$2"
                shift 2
                ;;
            --force)
                LIFECYCLE_FORCE=true
                shift
                ;;
            --keep-backups)
                LIFECYCLE_KEEP_BACKUPS="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                echo ""
                show_usage
                exit 1
                ;;
        esac
    done
    
    # 鎵ц鍛戒护
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
        status)
            lifecycle_status
            ;;
        rollback)
            lifecycle_rollback
            ;;
        cleanup-role)
            lifecycle_cleanup_role
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

# 杩愯涓诲嚱鏁?
main "$@"
