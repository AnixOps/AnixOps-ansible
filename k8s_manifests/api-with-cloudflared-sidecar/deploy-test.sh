#!/bin/bash

# =============================================================================
# Kind 集群 + Cloudflared Sidecar 测试部署脚本
# 自动创建 Kind 集群，部署测试 API，测试完成后可选择性销毁
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

# 图标
ICON_CHECK="✅"
ICON_CROSS="❌"
ICON_WARN="⚠️ "
ICON_INFO="ℹ️ "
ICON_ROCKET="🚀"
ICON_GEAR="⚙️ "

# 打印函数
print_banner() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║   Kind 集群 + Cloudflared Sidecar 测试环境              ║"
    echo "║   Automated Kind Cluster Test Deployment                 ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_info() {
    echo -e "${BLUE}${ICON_INFO} [INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}${ICON_CHECK} [SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}${ICON_WARN}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}${ICON_CROSS} [ERROR]${NC} $1"
}

print_step() {
    echo -e "${PURPLE}${ICON_GEAR} [STEP]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
${CYAN}使用方法:${NC} $0 [选项]

${CYAN}选项:${NC}
  --token TOKEN           Cloudflare Tunnel Token ${RED}(必需)${NC}
  --cluster-name NAME     Kind 集群名称 (默认: cloudflared-test)
  --keep-cluster          测试完成后保留集群
  --auto-destroy          测试完成后自动销毁集群 (默认: 询问)
  --help                  显示此帮助信息

${CYAN}示例:${NC}
  # 基本使用（测试后会询问是否销毁）
  $0 --token "your-cloudflare-tunnel-token"

  # 保留集群用于调试
  $0 --token "your-token" --keep-cluster

  # 自动销毁集群（用于 CI/CD）
  $0 --token "your-token" --auto-destroy

${CYAN}环境变量:${NC}
  CLOUDFLARE_TUNNEL_TOKEN  如果设置，可以省略 --token 参数

EOF
}

# 默认值
CLUSTER_NAME="cloudflared-test"
TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"
KEEP_CLUSTER=false
AUTO_DESTROY=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --token)
            TUNNEL_TOKEN="$2"
            shift 2
            ;;
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --keep-cluster)
            KEEP_CLUSTER=true
            shift
            ;;
        --auto-destroy)
            AUTO_DESTROY=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "未知参数: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# 清理函数
cleanup() {
    local exit_code=$?
    echo ""
    
    if [ $exit_code -ne 0 ]; then
        print_error "脚本执行失败，退出码: $exit_code"
    fi
    
    # 如果设置了自动销毁或者执行失败
    if [ "$AUTO_DESTROY" = true ] || ([ $exit_code -ne 0 ] && [ "$KEEP_CLUSTER" = false ]); then
        print_step "清理 Kind 集群..."
        kind delete cluster --name "$CLUSTER_NAME" 2>/dev/null || true
        print_success "集群已销毁"
    elif [ "$KEEP_CLUSTER" = false ] && [ $exit_code -eq 0 ]; then
        echo ""
        print_warning "Kind 集群仍在运行: $CLUSTER_NAME"
        echo -e "${CYAN}手动删除命令:${NC} kind delete cluster --name $CLUSTER_NAME"
    fi
}

# 注册清理函数
trap cleanup EXIT

# 检查必需工具
check_requirements() {
    print_step "检查系统要求..."
    
    local missing_tools=()
    
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if ! command -v kind &> /dev/null; then
        missing_tools+=("kind")
    fi
    
    if ! command -v kubectl &> /dev/null; then
        missing_tools+=("kubectl")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "缺少必需工具: ${missing_tools[*]}"
        echo ""
        echo -e "${CYAN}安装命令:${NC}"
        for tool in "${missing_tools[@]}"; do
            case $tool in
                docker)
                    echo "  Docker: https://docs.docker.com/get-docker/"
                    ;;
                kind)
                    echo "  Kind: curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64"
                    echo "        chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind"
                    ;;
                kubectl)
                    echo "  Kubectl: curl -LO https://dl.k8s.io/release/\$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                    echo "           chmod +x kubectl && sudo mv kubectl /usr/local/bin/"
                    ;;
            esac
        done
        exit 1
    fi
    
    print_success "所有必需工具已安装"
}

# 检查参数
check_parameters() {
    if [ -z "$TUNNEL_TOKEN" ]; then
        print_error "缺少必需参数: --token"
        echo ""
        echo -e "${CYAN}提示:${NC} 您也可以设置环境变量 CLOUDFLARE_TUNNEL_TOKEN"
        echo ""
        show_help
        exit 1
    fi
}

# 创建 Kind 集群
create_kind_cluster() {
    print_step "创建 Kind 集群: $CLUSTER_NAME"
    
    # 检查集群是否已存在
    if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        print_warning "集群 $CLUSTER_NAME 已存在"
        read -p "是否删除并重新创建? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kind delete cluster --name "$CLUSTER_NAME"
            print_success "旧集群已删除"
        else
            print_info "使用现有集群"
            return 0
        fi
    fi
    
    # 创建集群（简单配置，无端口映射）
    print_info "使用默认配置创建集群..."
    if kind create cluster --name "$CLUSTER_NAME"; then
        print_success "Kind 集群创建成功"
    else
        print_error "Kind 集群创建失败"
        exit 1
    fi
    
    # 等待集群就绪
    print_info "等待集群就绪..."
    sleep 5
    
    if kubectl cluster-info --context "kind-${CLUSTER_NAME}" &> /dev/null; then
        print_success "集群已就绪"
    else
        print_error "集群未就绪"
        exit 1
    fi
}

# 部署测试应用
deploy_test_app() {
    print_step "部署测试 API 和 Cloudflared Sidecar"
    
    # 切换 context
    kubectl config use-context "kind-${CLUSTER_NAME}" &> /dev/null
    
    # 创建 Secret
    print_info "创建 Cloudflare Tunnel Secret..."
    kubectl create secret generic cloudflared-secret \
        --from-literal=TUNNEL_TOKEN="$TUNNEL_TOKEN" \
        --dry-run=client -o yaml | kubectl apply -f - > /dev/null
    print_success "Secret 创建成功"
    
    # 创建部署文件
    print_info "创建 Deployment 和 Service..."
    local deploy_yaml=$(mktemp)
    cat > "$deploy_yaml" << 'YAML_EOF'
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-api-with-cloudflared
  labels:
    app: test-api-service
    environment: test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-api-service
  template:
    metadata:
      labels:
        app: test-api-service
        environment: test
    spec:
      containers:
      # httpbin 测试 API
      - name: test-api-service
        image: kennethreitz/httpbin:latest
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 80
          protocol: TCP
        resources:
          requests:
            cpu: "50m"
            memory: "64Mi"
          limits:
            cpu: "200m"
            memory: "256Mi"
        livenessProbe:
          httpGet:
            path: /status/200
            port: 80
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /status/200
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
      
      # Cloudflared Sidecar
      - name: cloudflared-sidecar
        image: cloudflare/cloudflared:latest
        imagePullPolicy: IfNotPresent
        args:
        - "tunnel"
        - "--no-autoupdate"
        - "run"
        - "--token"
        - "$(TUNNEL_TOKEN)"
        env:
        - name: TUNNEL_TOKEN
          valueFrom:
            secretKeyRef:
              name: cloudflared-secret
              key: TUNNEL_TOKEN
        resources:
          requests:
            cpu: "50m"
            memory: "64Mi"
          limits:
            cpu: "100m"
            memory: "128Mi"

---
apiVersion: v1
kind: Service
metadata:
  name: test-api-service
  labels:
    app: test-api-service
spec:
  type: ClusterIP
  selector:
    app: test-api-service
  ports:
  - name: http
    port: 80
    targetPort: 80
    protocol: TCP
YAML_EOF
    
    kubectl apply -f "$deploy_yaml" > /dev/null
    rm -f "$deploy_yaml"
    print_success "部署配置已应用"
    
    # 等待 Pod 就绪
    print_info "等待 Pod 启动（最多 2 分钟）..."
    if kubectl wait --for=condition=ready pod \
        -l app=test-api-service \
        --timeout=120s > /dev/null 2>&1; then
        print_success "Pod 已就绪"
    else
        print_warning "Pod 启动超时，继续检查状态..."
    fi
}

# 显示部署信息
show_deployment_info() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${ICON_ROCKET} 部署完成！${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Pod 状态
    print_info "Pod 状态:"
    kubectl get pods -l app=test-api-service
    echo ""
    
    # Service 状态
    print_info "Service 状态:"
    kubectl get svc test-api-service
    echo ""
    
    # 获取 Pod 名称
    local pod_name=$(kubectl get pods -l app=test-api-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -n "$pod_name" ]; then
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}📋 测试命令${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${GREEN}1. 查看 Cloudflared 日志:${NC}"
        echo "   kubectl logs $pod_name -c cloudflared-sidecar -f"
        echo ""
        echo -e "${GREEN}2. 查看 API 日志:${NC}"
        echo "   kubectl logs $pod_name -c test-api-service -f"
        echo ""
        echo -e "${GREEN}3. 测试 API (集群内部):${NC}"
        echo "   kubectl exec -it $pod_name -c test-api-service -- curl http://localhost/get"
        echo ""
        echo -e "${GREEN}4. 查看 Pod 详情:${NC}"
        echo "   kubectl describe pod $pod_name"
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}🌐 外部访问${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "请访问 Cloudflare Zero Trust Dashboard 查看隧道 URL:"
        echo "https://one.dash.cloudflare.com/"
        echo ""
        echo -e "${GREEN}测试端点示例:${NC}"
        echo "  curl https://your-tunnel-url/get"
        echo "  curl https://your-tunnel-url/status/200"
        echo "  curl https://your-tunnel-url/headers"
        echo ""
    fi
    
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🔧 集群管理${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${GREEN}Kind 集群信息:${NC}"
    echo "  名称: $CLUSTER_NAME"
    echo "  Context: kind-$CLUSTER_NAME"
    echo ""
    echo -e "${GREEN}访问集群:${NC}"
    echo "  kubectl config use-context kind-$CLUSTER_NAME"
    echo ""
    if [ "$KEEP_CLUSTER" = true ]; then
        echo -e "${GREEN}${ICON_INFO} 集群将被保留用于调试${NC}"
        echo -e "${RED}删除集群:${NC}"
        echo "  kind delete cluster --name $CLUSTER_NAME"
    fi
    echo ""
}

# 主函数
main() {
    print_banner
    
    # 检查要求
    check_requirements
    check_parameters
    
    echo ""
    print_info "配置信息:"
    echo "  集群名称: $CLUSTER_NAME"
    echo "  保留集群: $KEEP_CLUSTER"
    echo "  自动销毁: $AUTO_DESTROY"
    echo ""
    
    # 创建集群
    create_kind_cluster
    echo ""
    
    # 部署应用
    deploy_test_app
    
    # 显示信息
    show_deployment_info
    
    # 等待用户
    if [ "$KEEP_CLUSTER" = false ] && [ "$AUTO_DESTROY" = false ]; then
        echo -e "${YELLOW}${ICON_WARN}提示: 测试完成后，集群可以被删除${NC}"
        echo ""
        read -p "现在删除集群吗? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            AUTO_DESTROY=true
        else
            KEEP_CLUSTER=true
        fi
    fi
}

# 执行主函数
main
