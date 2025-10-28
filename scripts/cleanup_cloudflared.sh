#!/bin/bash
# =============================================================================
# Cloudflare Tunnel 清理脚本 | Cleanup Script for Cloudflare Tunnel
# =============================================================================
# 此脚本用于删除现有的 Cloudflare Tunnel Kubernetes 部署
# This script removes existing Cloudflare Tunnel Kubernetes deployment
# =============================================================================

set -e  # 遇到错误立即退出 | Exit on error

# 颜色定义 | Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印函数 | Print functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  🗑️  Cloudflare Tunnel Cleanup Script                    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

# 确认函数 | Confirmation function
confirm() {
    read -p "$(echo -e ${YELLOW}"⚠️  $1 (yes/no): "${NC})" response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 主函数 | Main function
main() {
    print_header
    
    # -------------------------------------------------------------------------
    # 步骤 1: 检查工具 | Check Tools
    # -------------------------------------------------------------------------
    print_step "步骤 1/5: 检查必需工具... | Step 1/5: Checking required tools..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl 未安装！请先安装 kubectl。"
        print_error "kubectl not installed! Please install kubectl first."
        exit 1
    fi
    print_success "kubectl 已安装"
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到 Kubernetes 集群！"
        print_error "Cannot connect to Kubernetes cluster!"
        exit 1
    fi
    print_success "Kubernetes 集群连接正常"
    
    echo ""
    
    # -------------------------------------------------------------------------
    # 步骤 2: 检查现有资源 | Check Existing Resources
    # -------------------------------------------------------------------------
    print_step "步骤 2/5: 检查现有 Cloudflare Tunnel 资源... | Step 2/5: Checking existing resources..."
    
    NAMESPACE="cloudflare-tunnel"
    
    # 检查命名空间是否存在 | Check if namespace exists
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_info "发现命名空间: $NAMESPACE"
        
        # 列出所有资源 | List all resources
        print_info "命名空间中的资源:"
        kubectl get all -n "$NAMESPACE" 2>/dev/null || true
        
        echo ""
        print_info "Secrets:"
        kubectl get secrets -n "$NAMESPACE" 2>/dev/null || true
        
        echo ""
        print_info "ConfigMaps:"
        kubectl get configmaps -n "$NAMESPACE" 2>/dev/null || true
        
        echo ""
    else
        print_warning "命名空间 $NAMESPACE 不存在"
    fi
    
    # 检查 Helm releases
    if command -v helm &> /dev/null; then
        print_info "检查 Helm releases..."
        helm list -n "$NAMESPACE" 2>/dev/null || true
    fi
    
    echo ""
    
    # -------------------------------------------------------------------------
    # 步骤 3: 确认删除 | Confirm Deletion
    # -------------------------------------------------------------------------
    print_step "步骤 3/5: 确认删除操作 | Step 3/5: Confirm deletion"
    
    echo ""
    print_warning "此操作将删除以下资源:"
    print_warning "This operation will delete the following resources:"
    echo ""
    echo "  1. Namespace: $NAMESPACE"
    echo "  2. 所有 Deployments, Pods, Services"
    echo "  3. 所有 Secrets 和 ConfigMaps"
    echo "  4. HorizontalPodAutoscaler (HPA)"
    echo "  5. PodDisruptionBudget (PDB)"
    echo ""
    
    if ! confirm "确定要继续删除吗？Are you sure you want to continue?"; then
        print_info "操作已取消 | Operation cancelled"
        exit 0
    fi
    
    echo ""
    
    # -------------------------------------------------------------------------
    # 步骤 4: 删除资源 | Delete Resources
    # -------------------------------------------------------------------------
    print_step "步骤 4/5: 删除 Kubernetes 资源... | Step 4/5: Deleting Kubernetes resources..."
    
    # 如果存在 Helm release，先卸载 | Uninstall Helm release if exists
    if command -v helm &> /dev/null; then
        HELM_RELEASES=$(helm list -n "$NAMESPACE" -q 2>/dev/null || true)
        if [ -n "$HELM_RELEASES" ]; then
            print_info "卸载 Helm releases..."
            for release in $HELM_RELEASES; do
                print_info "卸载 release: $release"
                helm uninstall "$release" -n "$NAMESPACE" || true
                print_success "Helm release '$release' 已卸载"
            done
        fi
    fi
    
    # 删除各个资源（如果通过 kubectl apply 部署的话）| Delete individual resources
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_info "删除 PodDisruptionBudget..."
        kubectl delete pdb --all -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
        
        print_info "删除 HorizontalPodAutoscaler..."
        kubectl delete hpa --all -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
        
        print_info "删除 Deployments..."
        kubectl delete deployment --all -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
        
        print_info "删除 Services..."
        kubectl delete svc --all -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
        
        print_info "删除 ConfigMaps..."
        kubectl delete configmap --all -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
        
        print_info "删除 Secrets..."
        kubectl delete secret --all -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
        
        # 等待所有 Pod 终止 | Wait for all pods to terminate
        print_info "等待 Pod 终止..."
        kubectl wait --for=delete pod --all -n "$NAMESPACE" --timeout=60s 2>/dev/null || true
        
        # 删除命名空间 | Delete namespace
        print_info "删除命名空间 $NAMESPACE..."
        kubectl delete namespace "$NAMESPACE" --ignore-not-found=true
        
        print_success "所有资源已删除"
    else
        print_info "命名空间不存在，跳过删除"
    fi
    
    echo ""
    
    # -------------------------------------------------------------------------
    # 步骤 5: 停止 kind 集群（可选）| Stop kind cluster (optional)
    # -------------------------------------------------------------------------
    print_step "步骤 5/5: 停止 kind 集群（可选）| Step 5/5: Stop kind cluster (optional)"
    
    if command -v kind &> /dev/null; then
        KIND_CLUSTERS=$(kind get clusters 2>/dev/null || true)
        
        if [ -n "$KIND_CLUSTERS" ]; then
            echo ""
            print_info "检测到以下 kind 集群:"
            echo "$KIND_CLUSTERS"
            echo ""
            
            if confirm "是否要删除 kind 集群？Do you want to delete kind cluster?"; then
                echo ""
                print_info "可用的 kind 集群:"
                kind get clusters
                echo ""
                read -p "$(echo -e ${YELLOW}"请输入要删除的集群名称（留空跳过）| Enter cluster name to delete (empty to skip): "${NC})" cluster_name
                
                if [ -n "$cluster_name" ]; then
                    print_info "删除 kind 集群: $cluster_name"
                    kind delete cluster --name "$cluster_name" || print_error "删除失败"
                    print_success "kind 集群已删除"
                else
                    print_info "跳过 kind 集群删除"
                fi
            else
                print_info "保留 kind 集群"
            fi
        else
            print_info "未检测到 kind 集群"
        fi
    else
        print_info "kind 未安装，跳过此步骤"
    fi
    
    echo ""
    
    # -------------------------------------------------------------------------
    # 完成 | Complete
    # -------------------------------------------------------------------------
    print_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_success "✅ 清理完成！Cleanup completed!"
    print_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    print_info "验证删除结果 | Verify deletion:"
    echo "  kubectl get namespace $NAMESPACE"
    echo "  kubectl get all -n $NAMESPACE"
    echo ""
    print_info "使用新的 Helm 方式部署 | Deploy using new Helm method:"
    echo "  ansible-playbook playbooks/cloudflared_k8s_helm.yml \\"
    echo "    --extra-vars \"cloudflare_tunnel_token=YOUR_TOKEN\""
    echo ""
}

# 运行主函数 | Run main function
main "$@"
