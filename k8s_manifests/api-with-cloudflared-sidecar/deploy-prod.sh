#!/bin/bash

# =============================================================================
# 生产环境 Cloudflared Sidecar 部署脚本
# Production Deployment Script with Cloudflared Sidecar
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
    echo "║   生产环境 Cloudflared Sidecar 部署工具                ║"
    echo "║   Production Deployment with Cloudflared                 ║"
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

${CYAN}必需参数:${NC}
  --token TOKEN           Cloudflare Tunnel Token ${RED}(必需)${NC}

${CYAN}可选参数:${NC}
  --image IMAGE           应用镜像 (默认: nginx:alpine)
  --namespace NS          Kubernetes Namespace (默认: default)
  --replicas NUM          副本数量 (默认: 2)
  --app-name NAME         应用名称 (默认: nginx-app)
  --app-port PORT         应用端口 (默认: 80)
  --health-path PATH      健康检查路径 (默认: /)
  --environment ENV       环境名称 (默认: production)
  --dry-run               模拟运行，只显示配置
  --help                  显示此帮助信息

${CYAN}示例:${NC}
  # 使用默认 Nginx 部署
  $0 --token "your-cloudflare-tunnel-token"

  # 部署自定义应用
  $0 --token "your-token" --image myapp:v1.0 --app-port 8080

  # 模拟运行查看配置
  $0 --token "your-token" --dry-run

${CYAN}环境变量:${NC}
  CLOUDFLARE_TUNNEL_TOKEN  如果设置，可以省略 --token 参数

EOF
}

# 默认值
NAMESPACE="default"
REPLICAS=2
APP_NAME="nginx-app"
APP_IMAGE="nginx:alpine"
APP_PORT=80
HEALTH_PATH="/"
ENVIRONMENT="production"
DRY_RUN=false
TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --token)
            TUNNEL_TOKEN="$2"
            shift 2
            ;;
        --image)
            APP_IMAGE="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --replicas)
            REPLICAS="$2"
            shift 2
            ;;
        --app-name)
            APP_NAME="$2"
            shift 2
            ;;
        --app-port)
            APP_PORT="$2"
            shift 2
            ;;
        --health-path)
            HEALTH_PATH="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
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

# 检查必需工具
check_requirements() {
    print_step "检查系统要求..."
    
    local missing_tools=()
    
    if ! command -v kubectl &> /dev/null; then
        missing_tools+=("kubectl")
    fi
    
    if ! command -v base64 &> /dev/null; then
        missing_tools+=("base64")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "缺少必需工具: ${missing_tools[*]}"
        exit 1
    fi
    
    # 检查 kubectl 连接
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到 Kubernetes 集群"
        print_info "请检查 kubectl 配置和集群连接"
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

# 确保 namespace 存在
ensure_namespace() {
    print_step "检查 Namespace: $NAMESPACE"
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_info "Namespace '$NAMESPACE' 已存在"
    else
        print_info "创建 Namespace '$NAMESPACE'..."
        if [ "$DRY_RUN" = false ]; then
            kubectl create namespace "$NAMESPACE"
            print_success "Namespace 创建成功"
        else
            print_info "[DRY RUN] 将创建 namespace: $NAMESPACE"
        fi
    fi
}

# 部署应用
deploy_application() {
    print_step "部署应用到 Kubernetes 集群"
    
    # 生成配置
    local deploy_yaml=$(mktemp)
    local encoded_token=$(echo -n "$TUNNEL_TOKEN" | base64 -w 0 2>/dev/null || echo -n "$TUNNEL_TOKEN" | base64)
    
    cat > "$deploy_yaml" << YAML_EOF
---
apiVersion: v1
kind: Secret
metadata:
  name: cloudflared-secret
  namespace: ${NAMESPACE}
  labels:
    app: ${APP_NAME}
type: Opaque
data:
  TUNNEL_TOKEN: ${encoded_token}

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}-with-tunnel
  namespace: ${NAMESPACE}
  labels:
    app: ${APP_NAME}
    environment: ${ENVIRONMENT}
spec:
  replicas: ${REPLICAS}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: ${APP_NAME}
  template:
    metadata:
      labels:
        app: ${APP_NAME}
        environment: ${ENVIRONMENT}
    spec:
      containers:
      # 应用容器
      - name: ${APP_NAME}
        image: ${APP_IMAGE}
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: ${APP_PORT}
          protocol: TCP
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: ${HEALTH_PATH}
            port: ${APP_PORT}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: ${HEALTH_PATH}
            port: ${APP_PORT}
          initialDelaySeconds: 10
          periodSeconds: 5
      
      # Cloudflared Sidecar
      - name: cloudflared-sidecar
        image: cloudflare/cloudflared:latest
        imagePullPolicy: IfNotPresent
        args:
        - tunnel
        - --no-autoupdate
        - run
        - --token
        - \$(TUNNEL_TOKEN)
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
  name: ${APP_NAME}-service
  namespace: ${NAMESPACE}
  labels:
    app: ${APP_NAME}
spec:
  type: ClusterIP
  selector:
    app: ${APP_NAME}
  ports:
  - name: http
    port: ${APP_PORT}
    targetPort: ${APP_PORT}
    protocol: TCP
YAML_EOF
    
    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] 生成的配置文件:"
        echo ""
        cat "$deploy_yaml"
        echo ""
        rm -f "$deploy_yaml"
        return 0
    fi
    
    # 应用配置
    print_info "应用 Kubernetes 配置..."
    if kubectl apply -f "$deploy_yaml"; then
        print_success "配置应用成功"
    else
        print_error "配置应用失败"
        rm -f "$deploy_yaml"
        exit 1
    fi
    
    rm -f "$deploy_yaml"
    
    # 等待 Pod 就绪
    print_info "等待 Pod 启动（最多 3 分钟）..."
    if kubectl wait --for=condition=ready pod \
        -l app=${APP_NAME} \
        -n ${NAMESPACE} \
        --timeout=180s > /dev/null 2>&1; then
        print_success "Pod 已就绪"
    else
        print_warning "Pod 启动超时或未就绪，请检查状态"
    fi
}

# 显示部署信息
show_deployment_info() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${ICON_ROCKET} 部署完成！${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    print_info "部署摘要:"
    echo "  • 环境: ${ENVIRONMENT}"
    echo "  • Namespace: ${NAMESPACE}"
    echo "  • 应用名称: ${APP_NAME}"
    echo "  • 镜像: ${APP_IMAGE}"
    echo "  • 副本数: ${REPLICAS}"
    echo ""
    
    # Pod 状态
    print_info "Pod 状态:"
    kubectl get pods -l app=${APP_NAME} -n ${NAMESPACE}
    echo ""
    
    # Service 状态
    print_info "Service 状态:"
    kubectl get svc ${APP_NAME}-service -n ${NAMESPACE}
    echo ""
    
    local pod_name=$(kubectl get pods -l app=${APP_NAME} -n ${NAMESPACE} -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -n "$pod_name" ]; then
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}📋 常用命令${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${GREEN}1. 查看应用日志:${NC}"
        echo "   kubectl logs -f $pod_name -c ${APP_NAME} -n ${NAMESPACE}"
        echo ""
        echo -e "${GREEN}2. 查看 Cloudflared 日志:${NC}"
        echo "   kubectl logs -f $pod_name -c cloudflared-sidecar -n ${NAMESPACE}"
        echo ""
        echo -e "${GREEN}3. 进入容器:${NC}"
        echo "   kubectl exec -it $pod_name -c ${APP_NAME} -n ${NAMESPACE} -- /bin/sh"
        echo ""
        echo -e "${GREEN}4. 扩缩容:${NC}"
        echo "   kubectl scale deployment/${APP_NAME}-with-tunnel --replicas=3 -n ${NAMESPACE}"
        echo ""
    fi
    
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🌐 外部访问${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "请访问 Cloudflare Zero Trust Dashboard 查看隧道 URL:"
    echo "https://one.dash.cloudflare.com/"
    echo ""
}

# 主函数
main() {
    print_banner
    
    # 检查要求
    check_requirements
    check_parameters
    
    # 显示配置
    echo ""
    print_info "部署配置:"
    echo "  • 环境: ${ENVIRONMENT}"
    echo "  • Namespace: ${NAMESPACE}"
    echo "  • 应用名称: ${APP_NAME}"
    echo "  • 应用镜像: ${APP_IMAGE}"
    echo "  • 应用端口: ${APP_PORT}"
    echo "  • 副本数: ${REPLICAS}"
    echo "  • 健康检查: ${HEALTH_PATH}"
    echo "  • 模拟运行: ${DRY_RUN}"
    echo ""
    
    if [ "$DRY_RUN" = false ]; then
        read -p "确认部署? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "部署已取消"
            exit 0
        fi
        echo ""
    fi
    
    # 准备环境
    ensure_namespace
    echo ""
    
    # 执行部署
    deploy_application
    
    # 显示信息
    if [ "$DRY_RUN" = false ]; then
        show_deployment_info
    fi
    
    print_success "脚本执行完成"
}

# 执行主函数
main "$@"
