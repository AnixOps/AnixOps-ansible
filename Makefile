# =============================================================================
# AnixOps Ansible - Makefile
# =============================================================================
# Thin wrappers around scripts/anixops.sh so that `make <target>` and the CLI
# always behave the same. Run `make help` for the target list.
#
# Variables (override on the command line):
#   INVENTORY     inventory passed to every ansible run (default: production)
#   ANSIBLE_ARGS  extra arguments appended to ansible-playbook, e.g.
#                 make deploy ANSIBLE_ARGS="--tags nginx --limit web_servers"
#   ANIXOPS_FLAGS extra flags for scripts/anixops.sh, e.g. ANIXOPS_FLAGS="--yes -vv"
#   ROLE          role for `make rollback` / `make status`; VERSION for rollback
#   PYTHON        Python interpreter (default: python3)
# =============================================================================

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

ANIXOPS       := scripts/anixops.sh
PYTHON        ?= python3
INVENTORY     ?= inventories/production/hosts.yml
ANSIBLE_ARGS  ?=
ANIXOPS_FLAGS ?=
ROLE          ?=
VERSION       ?=
PYTEST_ARGS   ?= -q

# Directories that are never scanned by repository-wide greps.
GREP_EXCLUDES := --exclude-dir=.git --exclude-dir=venv --exclude-dir=.venv --exclude-dir=.ansible \
                 --exclude-dir=collections --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
                 --exclude-dir=node_modules

.PHONY: help doctor install install-dev lint syntax test check ping deploy deploy-dry-run \
        quick-setup deploy-web health-check firewall-setup security-patch security-scan-only \
        rollback status gen-inventory check-inventory list-hosts clean encoding-check \
        backup-coverage pre-commit

##@ General

help: ## Show this help | 显示帮助
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target> [INVENTORY=path] [ANSIBLE_ARGS=\"...\"] [ANIXOPS_FLAGS=\"...\"] [ROLE=name]\n"} \
	  /^[a-zA-Z0-9_-]+:.*?##/ { printf "  %-20s %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n%s\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@printf "\nAll targets delegate to %s; run it with --help for every option.\n\n" "$(ANIXOPS)"

doctor: ## Check local tooling, .env, inventory parsing and drift
	$(ANIXOPS) doctor -i $(INVENTORY) $(ANIXOPS_FLAGS)

##@ Setup

install: ## Install runtime Python dependencies and Galaxy collections
	$(PYTHON) -m pip install -r requirements.txt
	ansible-galaxy collection install -r requirements.yml

install-dev: install ## Install development tools (pytest, shellcheck, pre-commit) and git hooks
	$(PYTHON) -m pip install -r requirements-dev.txt
	pre-commit install

##@ Validation

lint: ## Run yamllint + ansible-lint
	$(ANIXOPS) lint $(ANIXOPS_FLAGS)

syntax: ## ansible-playbook --syntax-check for every playbook
	$(ANIXOPS) syntax -i $(INVENTORY) $(ANIXOPS_FLAGS)

test: ## Run the Python unit tests
	$(PYTHON) -m pytest $(PYTEST_ARGS) tests

check-inventory: ## Verify hosts.yml matches servers-config.yml and parses
	$(PYTHON) tools/generate_inventory.py local --check
	ansible-inventory -i $(INVENTORY) --graph > /dev/null
	@echo "Inventory OK: $(INVENTORY)"

backup-coverage: ## Gate: template/copy tasks under /etc must set backup: true
	$(PYTHON) scripts/check-backup-coverage.py

encoding-check: ## Fail on UTF-8 BOMs or GBK mojibake anywhere in the repository
	@status=0; \
	bom=$$'^\xEF\xBB\xBF'; \
	pat=$$'\xe9\x88\xba|\xe9\x8f\x88|\xe9\x96\xae|\xe9\x90\xa8|\xe9\x94\x9b|\xe9\x8a\x86|\xe9\x8d\x8f|\xe9\x8e\xb4|\xe6\xb5\xa0|\xe7\x92\x81|\xe9\x8d\x99|\\?[^ -~]'; \
	if grep -rlI $(GREP_EXCLUDES) "$$bom" . ; then echo "ERROR: UTF-8 BOM found in the files above"; status=1; fi; \
	if grep -rnI $(GREP_EXCLUDES) -E "$$pat" . ; then echo "ERROR: GBK mojibake found in the lines above"; status=1; fi; \
	if [ "$$status" -eq 0 ]; then echo "Encoding check passed: no BOM, no mojibake"; fi; \
	exit $$status

check: lint syntax test check-inventory ## lint + syntax + test + check-inventory
	@echo "All checks passed"

pre-commit: ## Run every pre-commit hook against the whole repository
	pre-commit run --all-files

##@ Connectivity

ping: ## Ping all hosts (ANIXOPS_FLAGS="--limit group" to narrow)
	$(ANIXOPS) ping -i $(INVENTORY) $(ANIXOPS_FLAGS)

list-hosts: ## Show the inventory graph
	$(ANIXOPS) list-hosts -i $(INVENTORY) $(ANIXOPS_FLAGS)

##@ Deployment (production; prompts for confirmation unless ANIXOPS_FLAGS=--yes)

deploy: ## Full deployment (playbooks/provision/site.yml)
	$(ANIXOPS) deploy -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

deploy-dry-run: ## Full deployment in check mode with diff (no changes)
	$(ANIXOPS) deploy -i $(INVENTORY) --dry-run $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

quick-setup: ## common + monitoring agents + firewall (quick-setup.yml)
	$(ANIXOPS) quick-setup -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

deploy-web: ## Web servers: nginx + TLS (web-servers.yml)
	$(ANIXOPS) deploy-web -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

##@ Maintenance

health-check: ## Read-only health check of all hosts
	$(ANIXOPS) health-check -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

firewall-setup: ## Apply firewall rules and monitoring whitelist
	$(ANIXOPS) firewall -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

security-patch: ## Scan and apply security updates
	$(ANIXOPS) security-patch -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

security-scan-only: ## Vulnerability scan without applying updates
	$(ANIXOPS) security-patch --scan-only -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

rollback: ## Roll back a role: make rollback ROLE=nginx [VERSION=prev]
	@test -n "$(ROLE)" || { echo "usage: make rollback ROLE=<role> [VERSION=<version>]"; exit 2; }
	$(ANIXOPS) rollback $(ROLE) $(VERSION) -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

status: ## Lifecycle status of a role: make status ROLE=nginx
	@test -n "$(ROLE)" || { echo "usage: make status ROLE=<role>"; exit 2; }
	$(ANIXOPS) status $(ROLE) -i $(INVENTORY) $(ANIXOPS_FLAGS) -- $(ANSIBLE_ARGS)

##@ Inventory

gen-inventory: ## Regenerate inventories/production/hosts.yml (shows a diff, asks first)
	$(ANIXOPS) gen-inventory $(ANIXOPS_FLAGS)

##@ Housekeeping

clean: ## Remove caches, logs and generated fact cache
	find . -type f -name "*.pyc" -not -path "./venv/*" -delete
	find . -type d -name "__pycache__" -not -path "./venv/*" -prune -exec rm -rf {} +
	find . -type f -name "*.retry" -delete
	rm -rf .cache/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf .ansible/facts_cache .ansible/logs .ansible/tmp
	@echo "Cleaned"
