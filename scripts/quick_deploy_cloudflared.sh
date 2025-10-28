#!/bin/bash
# =============================================================================
# Cloudflare Tunnel 快速安装脚本 | Quick Install Script
# =============================================================================
# 此脚本会自动安装依赖并部署 Cloudflare Tunnel 到 Kubernetes
#
# 使用方法 | Usage:
#   ./scripts/quick_deploy_cloudflared.sh
#   或从任何目录: bash /path/to/scripts/quick_deploy_cloudflared.sh
#
# 环境变量 | Environment Variables:
#   CLOUDFLARE_TUNNEL_TOKEN - Cloudflare Tunnel Token (可选，脚本会提示输入)
# =============================================================================

set -e

# 获取脚本所在目录和项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 切换到项目根目录
cd "$PROJECT_ROOT" || {
    echo "❌ 错误: 无法切换到项目根目录"
    exit 1
}

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  🚀 Cloudflare Tunnel K8s Deployment (Helm)              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

check_dependencies() {
    print_info "检查依赖... | Checking dependencies..."
    
    local missing_deps=()
    
    # 检查 Ansible
    if ! command -v ansible &> /dev/null; then
        missing_deps+=("ansible")
    fi
    
    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        missing_deps+=("kubectl")
    fi
    
    # 检查 Helm，如果没有则自动安装
    if ! command -v helm &> /dev/null; then
        print_warning "Helm 未安装，正在自动安装..."
        if curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash; then
            print_success "Helm 已安装"
        else
            print_error "Helm 安装失败"
            missing_deps+=("helm")
        fi
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "缺少依赖: ${missing_deps[*]}"
        echo ""
        print_info "请先安装缺少的依赖："
        echo ""
        for dep in "${missing_deps[@]}"; do
            case $dep in
                ansible)
                    echo "  Ansible: pip install ansible"
                    ;;
                kubectl)
                    echo "  kubectl: curl -LO https://dl.k8s.io/release/\$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                    echo "           sudo install kubectl /usr/local/bin/"
                    ;;
                helm)
                    echo "  Helm: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
                    ;;
            esac
        done
        exit 1
    fi
    
    print_success "所有依赖已安装"
}

install_collections() {
    print_info "检查 Python 依赖和 Ansible Collections..."
    
    # 检查是否在虚拟环境中
    if [ -n "$VIRTUAL_ENV" ]; then
        print_info "检测到虚拟环境: $VIRTUAL_ENV"
        PIP_CMD="$VIRTUAL_ENV/bin/pip"
    else
        print_info "使用系统 Python"
        PIP_CMD="pip3"
    fi
    
    # 安装 Python 依赖
    print_info "安装 Python 依赖..."
    $PIP_CMD install -q kubernetes openshift PyYAML 2>/dev/null || {
        print_warning "Python 依赖可能已安装或安装失败"
    }
    
    # 安装 Ansible Collection
    print_info "安装 Ansible Collections..."
    ansible-galaxy collection install kubernetes.core --force > /dev/null 2>&1
    
    print_success "所有依赖已检查"
}

get_token() {
    if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
        print_success "从环境变量读取 Token"
        return 0
    fi
    
    echo ""
    print_warning "请输入 Cloudflare Tunnel Token:"
    print_info "（获取方式: Cloudflare Dashboard → Zero Trust → Access → Tunnels）"
    echo ""
    read -p "Token: " token
    
    if [ -z "$token" ]; then
        print_error "Token 不能为空"
        exit 1
    fi
    
    export CLOUDFLARE_TUNNEL_TOKEN="$token"
    print_success "Token 已设置"
}

deploy() {
    print_info "开始部署..."
    echo ""
    
    # 确保在项目根目录
    if [ ! -f "playbooks/cloudflared_k8s_helm.yml" ]; then
        print_error "找不到 playbook: playbooks/cloudflared_k8s_helm.yml"
        print_error "当前目录: $(pwd)"
        exit 1
    fi
    
    ansible-playbook playbooks/cloudflared_k8s_helm.yml
    
    echo ""
    print_success "部署完成！"
}

verify() {
    echo ""
    print_info "验证部署..."
    echo ""
    
    print_info "Checking pods..."
    kubectl get pods -n cloudflare-tunnel
    
    echo ""
    print_info "Checking Helm release..."
    helm list -n cloudflare-tunnel
    
    echo ""
    print_success "验证完成！"
    echo ""
    print_info "检查日志: kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared -f"
}

main() {
    print_header
    
    check_dependencies
    echo ""
    
    install_collections
    echo ""
    
    get_token
    echo ""
    
    deploy
    
    verify
}

main "$@"
