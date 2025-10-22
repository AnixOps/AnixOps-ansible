# =============================================================================
# AnixOps Ansible Makefile
# =============================================================================
# 提供常用操作的快捷命令 | Provides shortcuts for common operations
# =============================================================================

.PHONY: help install lint syntax check deploy quick-setup health-check ping clean firewall-setup gen-inventory

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
	@echo "  make list-hosts     - 列出主机 | List configured hosts"
	@echo "  make clean          - 清理临时文件 | Clean temporary files"
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
