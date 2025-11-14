# =============================================================================
# AnixOps Ansible Makefile
# =============================================================================
# 提供常用操作的快捷命令 | Provides shortcuts for common operations
# =============================================================================

.PHONY: help install lint syntax check deploy quick-setup health-check ping clean firewall-setup gen-inventory deploy-static-web

# -----------------------------------------------------------------------------
# 默认目标：显示帮助信息 | Default target: Show help information
# -----------------------------------------------------------------------------
help:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "AnixOps Ansible - 可用命令 | Available Commands"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "  make install        - 安装所有依赖 | Install all dependencies"
	@echo "  make gen-inventory  - 生成 inventory | Generate inventory from servers-config.yml"
	@echo "  make lint           - 运行代码检查 | Run code linting"
	@echo "  make syntax         - 检查语法 | Check playbook syntax"
	@echo "  make ping           - 测试连接 | Test server connectivity"
	@echo "  make deploy         - 完整部署 | Full deployment"
	@echo "  make quick-setup    - 快速初始化 | Quick initialization (monitoring + firewall)"
	@echo "  make firewall-setup - 配置防火墙 | Configure firewall and monitoring whitelist"
	@echo "  make health-check   - 健康检查 | Health check"
	@echo "  make deploy-web     - 部署 Web 服务器 | Deploy web servers"
	@echo "  make deploy-static-web - 部署静态网站+反向代理 | Deploy static web + reverse proxy"
	@echo "  make ssh-test       - 测试 SSH 配置 | Test SSH configuration"
	@echo "  make ssh-fix        - 强制修复 SSH 配置 | Force fix SSH configuration"
	@echo "  make list-hosts     - 列出主机 | List configured hosts"
	@echo "  make clean          - 清理临时文件 | Clean temporary files"
	@echo ""
	@echo "🚀 Cloudflare Tunnel (Kubernetes with Helm):"
	@echo "  make cf-k8s-deploy  - 部署 CF Tunnel 到 K8s (Helm) | Deploy CF Tunnel to K8s"
	@echo "  make cf-k8s-cleanup - 清理 CF Tunnel K8s 部署 | Cleanup CF Tunnel K8s deployment"
	@echo "  make cf-k8s-verify  - 验证 CF Tunnel 部署 | Verify CF Tunnel deployment"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"

# -----------------------------------------------------------------------------
# 安装依赖 | Install Dependencies
# -----------------------------------------------------------------------------
install:
	@echo "Installing Python dependencies... | 正在安装 Python 依赖..."
	pip install -r requirements.txt
	@echo "✓ Dependencies installed | 依赖安装完成"

# -----------------------------------------------------------------------------
# 生成 Inventory | Generate Inventory
# -----------------------------------------------------------------------------
gen-inventory:
	@echo "Generating inventory from servers-config.yml... | 从 servers-config.yml 生成 inventory..."
	@python3 tools/generate_inventory.py local > inventory/hosts.yml
	@echo "✓ Inventory generated: inventory/hosts.yml | Inventory 已生成"
	@echo ""
	@echo "Preview (first 30 lines) | 预览（前 30 行）:"
	@head -n 30 inventory/hosts.yml

# -----------------------------------------------------------------------------
# 代码检查 | Code Linting
# -----------------------------------------------------------------------------
lint:
	@echo "Running yamllint... | 运行 yamllint..."
	yamllint -c .yamllint.yml .
	@echo "Running ansible-lint... | 运行 ansible-lint..."
	ansible-lint --force-color playbooks/*.yml roles/*/tasks/*.yml
	@echo "✓ Lint completed | 代码检查完成"

# -----------------------------------------------------------------------------
# 语法检查 | Syntax Check
# -----------------------------------------------------------------------------
syntax:
	@echo "Checking playbook syntax... | 检查 playbook 语法..."
	ansible-playbook --syntax-check playbooks/site.yml
	ansible-playbook --syntax-check playbooks/quick-setup.yml
	ansible-playbook --syntax-check playbooks/health-check.yml
	ansible-playbook --syntax-check playbooks/firewall-setup.yml
	@echo "✓ Syntax check passed | 语法检查通过"

# -----------------------------------------------------------------------------
# 测试连接 | Test Connectivity
# -----------------------------------------------------------------------------
ping:
	@echo "Testing server connectivity... | 测试服务器连接..."
	ansible all -m ping
	@echo "✓ Connectivity test completed | 连接测试完成"

# -----------------------------------------------------------------------------
# 完整部署 | Full Deployment
# -----------------------------------------------------------------------------
deploy:
	@echo "Starting full deployment... | 开始完整部署..."
	ansible-playbook -i inventory/hosts.yml playbooks/site.yml
	@echo "✓ Deployment completed | 部署完成"

# -----------------------------------------------------------------------------
# 快速初始化 | Quick Setup
# -----------------------------------------------------------------------------
quick-setup:
	@echo "Starting quick setup (common + monitoring + firewall)... | 开始快速设置..."
	ansible-playbook -i inventory/hosts.yml playbooks/quick-setup.yml
	@echo "✓ Quick setup completed | 快速设置完成"

# -----------------------------------------------------------------------------
# 防火墙配置 | Firewall Setup
# -----------------------------------------------------------------------------
firewall-setup:
	@echo "Configuring firewall and monitoring whitelist... | 配置防火墙和监控白名单..."
	ansible-playbook -i inventory/hosts.yml playbooks/firewall-setup.yml
	@echo "✓ Firewall setup completed | 防火墙设置完成"

# -----------------------------------------------------------------------------
# 健康检查 | Health Check
# -----------------------------------------------------------------------------
health-check:
	@echo "Running health check... | 运行健康检查..."
	ansible-playbook -i inventory/hosts.yml playbooks/health-check.yml
	@echo "✓ Health check completed | 健康检查完成"

# -----------------------------------------------------------------------------
# Web 服务器部署 | Web Servers Deployment
# -----------------------------------------------------------------------------
deploy-web:
	@echo "Deploying web servers... | 部署 Web 服务器..."
	ansible-playbook -i inventory/hosts.yml playbooks/web-servers.yml
	@echo "✓ Web servers deployed | Web 服务器部署完成"

# -----------------------------------------------------------------------------
# 部署静态网站和反向代理 | Deploy Static Website with Reverse Proxy
# -----------------------------------------------------------------------------
deploy-static-web:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🌐 部署静态网站和反向代理 | Deploy Static Web + Reverse Proxy"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@if [ -z "$$CF_SSL_CERT" ] || [ -z "$$CF_SSL_KEY" ]; then \
		echo "⚠️  Warning: CF_SSL_CERT or CF_SSL_KEY not set!"; \
		echo "SSL certificates will not be deployed."; \
		echo ""; \
		echo "To enable SSL, set environment variables:"; \
		echo "  export CF_SSL_CERT=\"\$$(cat cert.pem | base64 -w 0)\""; \
		echo "  export CF_SSL_KEY=\"\$$(cat key.pem | base64 -w 0)\""; \
		echo ""; \
		read -p "Continue without SSL? (y/N): " confirm; \
		if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
			echo "Deployment cancelled."; \
			exit 1; \
		fi; \
	else \
		echo "✓ SSL certificates configured"; \
	fi
	@echo ""
	@echo "📝 Starting deployment to dev_servers..."
	@echo ""
	ansible-playbook -i inventory/hosts.yml playbooks/deployment/deploy-static-web.yml
	@echo ""
	@echo "✅ Deployment completed!"
	@echo ""
	@echo "🔍 Test commands:"
	@echo "  curl -I http://127.0.0.1:8080"
	@echo "  curl -I https://test-web-ansible.anixops.com"

# -----------------------------------------------------------------------------
# SSH 配置测试 | SSH Configuration Test
# -----------------------------------------------------------------------------
ssh-test:
	@echo "Testing SSH configuration... | 测试 SSH 配置..."
	ansible-playbook -i inventory/hosts.yml playbooks/ssh-config-test.yml
	@echo "✓ SSH configuration test completed | SSH 配置测试完成"

# -----------------------------------------------------------------------------
# SSH 配置强制修复 | SSH Configuration Force Fix
# -----------------------------------------------------------------------------
ssh-fix:
	@echo "⚠️  WARNING: This will restart SSH service! | 警告：这将重启 SSH 服务！"
	@echo "Press Ctrl+C within 5 seconds to cancel... | 5 秒内按 Ctrl+C 取消..."
	@sleep 5
	@echo "Forcing SSH configuration apply... | 强制应用 SSH 配置..."
	ansible-playbook -i inventory/hosts.yml playbooks/ssh-config-force-apply.yml
	@echo "✓ SSH configuration force applied | SSH 配置已强制应用"

# -----------------------------------------------------------------------------
# 清理临时文件 | Clean Temporary Files
# -----------------------------------------------------------------------------
clean:
	@echo "Cleaning up... | 清理中..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.retry" -delete
	rm -rf .cache/
	@echo "✓ Cleanup completed | 清理完成"

# -----------------------------------------------------------------------------
# 查看服务器列表 | List Hosts
# -----------------------------------------------------------------------------
list-hosts:
	@echo "Configured hosts | 已配置主机:"
	@ansible all --list-hosts

# 显示变量
show-vars:
	@echo "Global variables:"
	@ansible all -m debug -a "var=hostvars[inventory_hostname]" | head -50

# SSH 密钥上传
upload-key:
	@echo "Starting SSH key upload wizard..."
	python tools/ssh_key_manager.py

# -----------------------------------------------------------------------------
# Cloudflare Tunnel Kubernetes 部署 (Helm) | CF Tunnel K8s Deployment (Helm)
# -----------------------------------------------------------------------------
cf-k8s-deploy:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🚀 Deploying Cloudflare Tunnel to Kubernetes (Helm)"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@if [ -z "$$CLOUDFLARE_TUNNEL_TOKEN" ]; then \
		echo "❌ Error: CLOUDFLARE_TUNNEL_TOKEN is not set!"; \
		echo ""; \
		echo "Please set it first:"; \
		echo "  export CLOUDFLARE_TUNNEL_TOKEN=\"your-token-here\""; \
		echo ""; \
		echo "Or use:"; \
		echo "  make cf-k8s-deploy CLOUDFLARE_TUNNEL_TOKEN=your-token"; \
		exit 1; \
	fi
	@echo "📦 Token: ✅ (first 10 chars: $${CLOUDFLARE_TUNNEL_TOKEN:0:10}...)"
	@echo "📝 Starting deployment..."
	@echo ""
	ansible-playbook playbooks/cloudflared_k8s_helm.yml
	@echo ""
	@echo "✅ Deployment completed!"
	@echo ""
	@echo "🔍 Verify:"
	@echo "  kubectl get pods -n cloudflare-tunnel"
	@echo "  make cf-k8s-verify"

cf-k8s-cleanup:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🗑️  Cleaning up Cloudflare Tunnel Kubernetes deployment"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@./scripts/cleanup_cloudflared.sh

cf-k8s-verify:
	@echo "═══════════════════════════════════════════════════════════"
	@echo "🔍 Verifying Cloudflare Tunnel Kubernetes deployment"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "📦 Checking namespace..."
	@kubectl get namespace cloudflare-tunnel 2>/dev/null || echo "❌ Namespace not found"
	@echo ""
	@echo "📦 Checking Helm release..."
	@helm list -n cloudflare-tunnel
	@echo ""
	@echo "📦 Checking pods..."
	@kubectl get pods -n cloudflare-tunnel -o wide
	@echo ""
	@echo "📊 Checking pod status..."
	@kubectl get pods -n cloudflare-tunnel -o json | jq -r '.items[] | "\(.metadata.name): \(.status.phase)"'
	@echo ""
	@echo "📝 Recent logs (last 10 lines)..."
	@kubectl logs -n cloudflare-tunnel -l app.kubernetes.io/name=cloudflared --tail=10

