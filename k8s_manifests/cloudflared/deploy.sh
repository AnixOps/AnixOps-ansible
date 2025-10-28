#!/bin/bash
# =============================================================================
# Cloudflare Tunnel 快速部署脚本 | Quick Deploy Script for Cloudflare Tunnel
# =============================================================================
# 此脚本用于在 Kubernetes 集群中快速部署 Cloudflare Tunnel
# This script is used to quickly deploy Cloudflare Tunnel in a Kubernetes cluster
# =============================================================================

set -e  # 遇到错误立即退出 | Exit on error

# 颜色定义 | Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数 | Print functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  🚀 Cloudflare Tunnel for Kubernetes - Quick Deploy      ║${NC}"
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
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 检查必需工具 | Check required tools
check_requirements() {
    print_info "检查必需工具... | Checking required tools..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl 未安装！请先安装 kubectl。"
        print_error "kubectl not installed! Please install kubectl first."
        exit 1
    fi
    
    # 检查 kubectl 连接
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到 Kubernetes 集群！请检查 kubectl 配置。"
        print_error "Cannot connect to Kubernetes cluster! Please check kubectl configuration."
        exit 1
    fi
    
    print_success "所有必需工具已就绪 | All required tools are ready"
    echo ""
}

# 获取 Tunnel Token
get_tunnel_token() {
    print_info "请输入你的 Cloudflare Tunnel Token:"
    print_info "Please enter your Cloudflare Tunnel Token:"
    echo ""
    print_warning "从哪里获取 Token? | Where to get Token?"
    echo "  1. 访问 https://one.dash.cloudflare.com/"
    echo "  2. Access -> Tunnels -> Create a tunnel"
    echo "  3. 复制 Token (以 'eyJ' 开头) | Copy Token (starts with 'eyJ')"
    echo ""
    
    read -p "Token: " CF_TUNNEL_TOKEN
    
    if [ -z "$CF_TUNNEL_TOKEN" ]; then
        print_error "Token 不能为空！ | Token cannot be empty!"
        exit 1
    fi
    
    # 简单验证 Token 格式
    if [[ ! "$CF_TUNNEL_TOKEN" =~ ^eyJ ]]; then
        print_warning "Token 格式可能不正确（通常以 'eyJ' 开头）"
        print_warning "Token format may be incorrect (usually starts with 'eyJ')"
        read -p "是否继续? (y/N) | Continue? (y/N): " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            exit 1
        fi
    fi
    
    print_success "Token 已获取 | Token received"
    echo ""
}

# 步骤 1: 创建 Namespace
deploy_namespace() {
    print_info "步骤 1/6: 创建 Namespace... | Step 1/6: Creating Namespace..."
    
    if kubectl get namespace cloudflare-tunnel &> /dev/null; then
        print_warning "Namespace 'cloudflare-tunnel' 已存在，跳过创建"
        print_warning "Namespace 'cloudflare-tunnel' already exists, skipping"
    else
        kubectl apply -f 00-namespace.yaml
        print_success "Namespace 创建成功 | Namespace created successfully"
    fi
    echo ""
}

# 步骤 2: 创建 Secret
deploy_secret() {
    print_info "步骤 2/6: 创建 Secret... | Step 2/6: Creating Secret..."
    
    # 删除已存在的 Secret（如果有）
    kubectl delete secret cloudflared-token -n cloudflare-tunnel --ignore-not-found=true
    
    # 创建新的 Secret
    kubectl create secret generic cloudflared-token \
        --from-literal=token="$CF_TUNNEL_TOKEN" \
        --namespace=cloudflare-tunnel
    
    print_success "Secret 创建成功 | Secret created successfully"
    echo ""
}

# 步骤 3: 创建 ConfigMap
deploy_configmap() {
    print_info "步骤 3/6: 创建 ConfigMap... | Step 3/6: Creating ConfigMap..."
    
    kubectl apply -f 02-configmap.yaml
    print_success "ConfigMap 创建成功 | ConfigMap created successfully"
    echo ""
}

# 步骤 4: 部署 Deployment
deploy_deployment() {
    print_info "步骤 4/6: 部署 Deployment... | Step 4/6: Deploying Deployment..."
    
    kubectl apply -f 03-deployment.yaml
    print_success "Deployment 创建成功 | Deployment created successfully"
    echo ""
}

# 步骤 5: 部署 HPA（可选）
deploy_hpa() {
    print_info "步骤 5/6: 部署 HPA (可选)... | Step 5/6: Deploying HPA (optional)..."
    
    read -p "是否启用 HPA 自动扩缩容? (Y/n) | Enable HPA auto-scaling? (Y/n): " enable_hpa
    
    if [[ "$enable_hpa" != "n" && "$enable_hpa" != "N" ]]; then
        # 检查 Metrics Server
        if ! kubectl top nodes &> /dev/null; then
            print_warning "Metrics Server 未安装，HPA 将无法工作"
            print_warning "Metrics Server not installed, HPA will not work"
            read -p "是否仍然部署 HPA? (y/N) | Deploy HPA anyway? (y/N): " confirm
            if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
                print_info "跳过 HPA 部署 | Skipping HPA deployment"
                echo ""
                return
            fi
        fi
        
        kubectl apply -f 04-hpa.yaml
        print_success "HPA 创建成功 | HPA created successfully"
    else
        print_info "跳过 HPA 部署 | Skipping HPA deployment"
    fi
    echo ""
}

# 步骤 6: 部署 PDB
deploy_pdb() {
    print_info "步骤 6/6: 部署 PDB... | Step 6/6: Deploying PDB..."
    
    kubectl apply -f 05-pdb.yaml
    print_success "PDB 创建成功 | PDB created successfully"
    echo ""
}

# 等待 Pods 就绪
wait_for_pods() {
    print_info "等待 Pods 就绪... | Waiting for Pods to be ready..."
    echo ""
    
    kubectl wait --for=condition=available --timeout=120s \
        deployment/cloudflared -n cloudflare-tunnel || {
        print_warning "Pods 启动超时，请手动检查状态"
        print_warning "Pods startup timeout, please check status manually"
    }
    
    echo ""
}

# 验证部署
verify_deployment() {
    print_info "验证部署... | Verifying deployment..."
    echo ""
    
    # 显示 Pods 状态
    echo -e "${BLUE}═══ Pods 状态 | Pods Status ═══${NC}"
    kubectl get pods -n cloudflare-tunnel
    echo ""
    
    # 显示 Deployment 状态
    echo -e "${BLUE}═══ Deployment 状态 | Deployment Status ═══${NC}"
    kubectl get deployment cloudflared -n cloudflare-tunnel
    echo ""
    
    # 显示 HPA 状态（如果存在）
    if kubectl get hpa cloudflared-hpa -n cloudflare-tunnel &> /dev/null; then
        echo -e "${BLUE}═══ HPA 状态 | HPA Status ═══${NC}"
        kubectl get hpa cloudflared-hpa -n cloudflare-tunnel
        echo ""
    fi
    
    # 检查 Pod 日志
    echo -e "${BLUE}═══ Pod 日志 (最近 10 行) | Pod Logs (last 10 lines) ═══${NC}"
    kubectl logs -n cloudflare-tunnel -l app=cloudflared --tail=10 || {
        print_warning "无法获取日志，Pods 可能还未就绪"
        print_warning "Cannot get logs, Pods may not be ready yet"
    }
    echo ""
}

# 显示下一步操作
show_next_steps() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ 部署完成！ | Deployment Complete!                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    print_info "📝 下一步操作 | Next Steps:"
    echo ""
    echo "1️⃣  在 Cloudflare Dashboard 中配置域名路由:"
    echo "   https://one.dash.cloudflare.com/"
    echo "   Access -> Tunnels -> 你的 Tunnel -> Public Hostname"
    echo ""
    echo "2️⃣  添加 DNS 记录（通配符）:"
    echo "   Type: CNAME"
    echo "   Name: *"
    echo "   Target: <tunnel-id>.cfargotunnel.com"
    echo ""
    echo "3️⃣  创建 Ingress 资源（示例）:"
    echo "   kubectl apply -f - <<EOF"
    echo "   apiVersion: networking.k8s.io/v1"
    echo "   kind: Ingress"
    echo "   metadata:"
    echo "     name: my-app"
    echo "     namespace: default"
    echo "   spec:"
    echo "     ingressClassName: nginx"
    echo "     rules:"
    echo "       - host: app.anixops.com"
    echo "         http:"
    echo "           paths:"
    echo "             - path: /"
    echo "               pathType: Prefix"
    echo "               backend:"
    echo "                 service:"
    echo "                   name: my-app-service"
    echo "                   port:"
    echo "                     number: 80"
    echo "   EOF"
    echo ""
    
    print_info "📚 常用命令 | Useful Commands:"
    echo ""
    echo "  # 查看 Pods 状态 | Check Pods status"
    echo "  kubectl get pods -n cloudflare-tunnel"
    echo ""
    echo "  # 查看日志 | View logs"
    echo "  kubectl logs -n cloudflare-tunnel -l app=cloudflared -f"
    echo ""
    echo "  # 扩缩容 | Scale"
    echo "  kubectl scale deployment cloudflared --replicas=5 -n cloudflare-tunnel"
    echo ""
    echo "  # 删除部署 | Delete deployment"
    echo "  kubectl delete namespace cloudflare-tunnel"
    echo ""
}

# 主函数
main() {
    print_header
    
    # 检查运行目录
    if [ ! -f "00-namespace.yaml" ]; then
        print_error "请在 k8s_manifests/cloudflared 目录下运行此脚本！"
        print_error "Please run this script in the k8s_manifests/cloudflared directory!"
        exit 1
    fi
    
    check_requirements
    get_tunnel_token
    
    deploy_namespace
    deploy_secret
    deploy_configmap
    deploy_deployment
    deploy_hpa
    deploy_pdb
    
    wait_for_pods
    verify_deployment
    show_next_steps
}

# 运行主函数
main "$@"
