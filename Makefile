.PHONY: help install lint syntax check deploy quick-setup health-check ping clean

# 默认目标
help:
	@echo "AnixOps Ansible - 可用命令:"
	@echo ""
	@echo "  make install        - 安装所有依赖"
	@echo "  make lint          - 运行代码检查"
	@echo "  make syntax        - 检查 playbook 语法"
	@echo "  make ping          - 测试服务器连接"
	@echo "  make deploy        - 完整部署"
	@echo "  make quick-setup   - 快速初始化"
	@echo "  make health-check  - 健康检查"
	@echo "  make clean         - 清理临时文件"
	@echo ""

# 安装依赖
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "✓ Dependencies installed"

# 代码检查
lint:
	@echo "Running yamllint..."
	yamllint -c .yamllint.yml .
	@echo "Running ansible-lint..."
	ansible-lint --force-color playbooks/*.yml roles/*/tasks/*.yml
	@echo "✓ Lint completed"

# 语法检查
syntax:
	@echo "Checking playbook syntax..."
	ansible-playbook --syntax-check playbooks/site.yml
	ansible-playbook --syntax-check playbooks/quick-setup.yml
	ansible-playbook --syntax-check playbooks/health-check.yml
	@echo "✓ Syntax check passed"

# 测试连接
ping:
	@echo "Testing server connectivity..."
	ansible all -m ping
	@echo "✓ Connectivity test completed"

# 完整部署
deploy:
	@echo "Starting full deployment..."
	ansible-playbook -i inventory/hosts.yml playbooks/site.yml
	@echo "✓ Deployment completed"

# 快速初始化
quick-setup:
	@echo "Starting quick setup..."
	ansible-playbook -i inventory/hosts.yml playbooks/quick-setup.yml
	@echo "✓ Quick setup completed"

# 健康检查
health-check:
	@echo "Running health check..."
	ansible-playbook -i inventory/hosts.yml playbooks/health-check.yml
	@echo "✓ Health check completed"

# Web 服务器部署
deploy-web:
	@echo "Deploying web servers..."
	ansible-playbook -i inventory/hosts.yml playbooks/web-servers.yml
	@echo "✓ Web servers deployed"

# 清理临时文件
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.retry" -delete
	rm -rf .cache/
	@echo "✓ Cleanup completed"

# 查看服务器列表
list-hosts:
	@echo "Configured hosts:"
	@ansible all --list-hosts

# 显示变量
show-vars:
	@echo "Global variables:"
	@ansible all -m debug -a "var=hostvars[inventory_hostname]" | head -50

# SSH 密钥上传
upload-key:
	@echo "Starting SSH key upload wizard..."
	python tools/ssh_key_manager.py
