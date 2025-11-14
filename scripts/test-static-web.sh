#!/bin/bash
# =============================================================================
# Static Web Deployment Test Script
# =============================================================================
# 测试静态网站部署的功能
# Test static website deployment functionality
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
BACKEND_PORT=8080
SITE_DOMAIN="${STATIC_SITE_DOMAIN:-test-web-ansible.anixops.com}"

echo "=========================================="
echo "Static Web Deployment Test"
echo "=========================================="
echo ""

# 函数：打印成功消息
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# 函数：打印错误消息
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# 函数：打印警告消息
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 函数：打印信息
print_info() {
    echo -e "ℹ $1"
}

# 测试 1: 检查 Nginx 是否运行
echo "Test 1: Checking Nginx service..."
if systemctl is-active --quiet nginx; then
    print_success "Nginx service is running"
else
    print_error "Nginx service is not running"
    exit 1
fi
echo ""

# 测试 2: 检查 Nginx 配置
echo "Test 2: Checking Nginx configuration..."
if nginx -t 2>&1 | grep -q "successful"; then
    print_success "Nginx configuration is valid"
else
    print_error "Nginx configuration has errors"
    nginx -t
    exit 1
fi
echo ""

# 测试 3: 检查后端配置文件
echo "Test 3: Checking backend configuration files..."
if [ -f "/etc/nginx/sites-available/test-web-ansible-backend" ]; then
    print_success "Backend configuration exists"
else
    print_error "Backend configuration not found"
    exit 1
fi

if [ -L "/etc/nginx/sites-enabled/test-web-ansible-backend" ]; then
    print_success "Backend configuration is enabled"
else
    print_warning "Backend configuration is not enabled"
fi
echo ""

# 测试 4: 检查反向代理配置文件
echo "Test 4: Checking reverse proxy configuration files..."
if [ -f "/etc/nginx/sites-available/test-web-ansible-proxy" ]; then
    print_success "Reverse proxy configuration exists"
else
    print_warning "Reverse proxy configuration not found"
fi

if [ -L "/etc/nginx/sites-enabled/test-web-ansible-proxy" ]; then
    print_success "Reverse proxy configuration is enabled"
else
    print_warning "Reverse proxy configuration is not enabled"
fi
echo ""

# 测试 5: 检查静态文件
echo "Test 5: Checking static files..."
if [ -d "/var/www/test-web-ansible" ]; then
    print_success "Web root directory exists"
else
    print_error "Web root directory not found"
    exit 1
fi

if [ -f "/var/www/test-web-ansible/index.html" ]; then
    print_success "index.html exists"
else
    print_error "index.html not found"
    exit 1
fi

if [ -f "/var/www/test-web-ansible/health" ]; then
    print_success "health check file exists"
else
    print_warning "health check file not found"
fi
echo ""

# 测试 6: 检查 SSL 证书（如果存在）
echo "Test 6: Checking SSL certificates..."
if [ -d "/etc/nginx/ssl" ]; then
    if [ -f "/etc/nginx/ssl/${SITE_DOMAIN}.crt" ]; then
        print_success "SSL certificate exists"
        
        # 检查证书有效期
        expiry=$(openssl x509 -in "/etc/nginx/ssl/${SITE_DOMAIN}.crt" -noout -enddate 2>/dev/null | cut -d= -f2)
        if [ -n "$expiry" ]; then
            print_info "Certificate expires: $expiry"
        fi
    else
        print_warning "SSL certificate not found"
    fi
    
    if [ -f "/etc/nginx/ssl/${SITE_DOMAIN}.key" ]; then
        print_success "SSL private key exists"
    else
        print_warning "SSL private key not found"
    fi
else
    print_warning "SSL directory not found - SSL may not be configured"
fi
echo ""

# 测试 7: 测试后端服务
echo "Test 7: Testing backend service..."
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}" | grep -q "200"; then
    print_success "Backend service is responding (HTTP 200)"
    
    # 获取内容预览
    content=$(curl -s "http://127.0.0.1:${BACKEND_PORT}" | head -1 | cut -c1-50)
    print_info "Content preview: $content..."
else
    print_error "Backend service is not responding"
    print_info "Trying to check if port is listening..."
    if ss -tlnp | grep -q ":${BACKEND_PORT}"; then
        print_info "Port ${BACKEND_PORT} is listening"
    else
        print_error "Port ${BACKEND_PORT} is not listening"
    fi
fi
echo ""

# 测试 8: 测试健康检查端点
echo "Test 8: Testing health check endpoint..."
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" | grep -q "200"; then
    print_success "Health check endpoint is working"
else
    print_warning "Health check endpoint is not responding"
fi
echo ""

# 测试 9: 检查日志文件
echo "Test 9: Checking log files..."
LOG_FILES=(
    "/var/log/nginx/test-web-ansible-backend-access.log"
    "/var/log/nginx/test-web-ansible-backend-error.log"
    "/var/log/nginx/test-web-ansible-access.log"
    "/var/log/nginx/test-web-ansible-error.log"
)

for log_file in "${LOG_FILES[@]}"; do
    if [ -f "$log_file" ]; then
        print_success "$(basename $log_file) exists"
    else
        print_warning "$(basename $log_file) not found"
    fi
done
echo ""

# 测试 10: 测试反向代理（如果配置了）
echo "Test 10: Testing reverse proxy..."
if [ -L "/etc/nginx/sites-enabled/test-web-ansible-proxy" ]; then
    # 测试本地访问（需要在 /etc/hosts 中配置）
    if grep -q "$SITE_DOMAIN" /etc/hosts 2>/dev/null; then
        print_info "Testing with domain: $SITE_DOMAIN"
        
        # 测试 HTTP
        if curl -s -o /dev/null -w "%{http_code}" "http://${SITE_DOMAIN}" | grep -q "301\|200"; then
            print_success "HTTP access working (redirect or direct access)"
        else
            print_warning "HTTP access not working"
        fi
        
        # 测试 HTTPS（如果有证书）
        if [ -f "/etc/nginx/ssl/${SITE_DOMAIN}.crt" ]; then
            if curl -k -s -o /dev/null -w "%{http_code}" "https://${SITE_DOMAIN}" | grep -q "200"; then
                print_success "HTTPS access working"
            else
                print_warning "HTTPS access not working"
            fi
        fi
    else
        print_info "Domain not in /etc/hosts, skipping domain tests"
        print_info "Add to /etc/hosts for testing: echo '127.0.0.1 $SITE_DOMAIN' | sudo tee -a /etc/hosts"
    fi
else
    print_info "Reverse proxy not configured, skipping"
fi
echo ""

# 总结
echo "=========================================="
echo "Test Summary"
echo "=========================================="
print_info "Backend URL: http://127.0.0.1:${BACKEND_PORT}"
print_info "Health Check: http://127.0.0.1:${BACKEND_PORT}/health"
if [ -f "/etc/nginx/ssl/${SITE_DOMAIN}.crt" ]; then
    print_info "Domain URL: https://${SITE_DOMAIN}"
else
    print_info "Domain URL: http://${SITE_DOMAIN}"
fi
echo ""

# 有用的命令
echo "Useful Commands:"
echo "  View logs:      sudo tail -f /var/log/nginx/test-web-ansible-*.log"
echo "  Test backend:   curl -I http://127.0.0.1:${BACKEND_PORT}"
echo "  Test health:    curl http://127.0.0.1:${BACKEND_PORT}/health"
echo "  Nginx status:   sudo systemctl status nginx"
echo "  Check config:   sudo nginx -t"
echo "  Reload Nginx:   sudo systemctl reload nginx"
echo ""
echo "=========================================="
