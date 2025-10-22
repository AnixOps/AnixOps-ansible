#!/usr/bin/env bash
# AnixOps Linux startup script (venv bootstrap + command runner)
# This repository is Linux-only. This helper creates/uses a Python venv
# and provides convenient wrappers around common Ansible tasks.

set -euo pipefail

# Colors
C_RED='\033[0;31m'
C_GREEN='\033[0;32m'
C_YELLOW='\033[1;33m'
C_BLUE='\033[0;34m'
C_RESET='\033[0m'

# Logging functions
log() { echo -e "${C_BLUE}[*]${C_RESET} $*"; }
ok() { echo -e "${C_GREEN}[✓]${C_RESET} $*"; }
warn() { echo -e "${C_YELLOW}[!]${C_RESET} $*"; }
err() { echo -e "${C_RED}[x]${C_RESET} $*" 1>&2; }

# Resolve repository root (this script lives in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR%/scripts}"
cd "$REPO_ROOT"

VENV_DIR="venv"
REQ_FILE="requirements.txt"
INVENTORY="inventory/hosts.yml"
ENV_FILE=".env"

# Load .env file if it exists
if [[ -f "$ENV_FILE" ]]; then
  log "Loading environment variables from $ENV_FILE"
  set -a  # auto export all variables
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
elif [[ -z "${GITHUB_ACTIONS:-}" ]]; then
  # Only warn if not in GitHub Actions
  warn "No $ENV_FILE file found; using system environment or defaults"
  warn "Copy .env.example to .env and configure your server IPs"
else
  log "Running in GitHub Actions - using repository secrets"
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "Missing required command: $1"; exit 1; }
}

ensure_python() {
  if command -v python3 >/dev/null 2>&1; then
    PY=python3
  elif command -v python >/dev/null 2>&1; then
    PY=python
  else
    err "Python 3 is required. Please install Python 3.8+"
    exit 1
  fi
}

create_venv() {
  ensure_python
  if [[ -d "$VENV_DIR" ]]; then
    warn "Virtual environment already exists: $VENV_DIR"
    return 0
  fi
  log "Creating virtual environment in $VENV_DIR ..."
  "$PY" -m venv "$VENV_DIR"
  ok "Venv created"
}

activate_venv() {
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

install_requirements() {
  if [[ ! -f "$REQ_FILE" ]]; then
    warn "No $REQ_FILE found; skipping python deps installation"
    return 0
  fi
  log "Installing Python dependencies from $REQ_FILE ..."
  pip install --upgrade pip >/dev/null
  pip install -r "$REQ_FILE"
  ok "Dependencies installed"
}

ensure_venv_ready() {
  if [[ ! -d "$VENV_DIR" ]]; then
    create_venv
  fi
  activate_venv
  install_requirements
}

usage() {
  cat <<'EOF'
AnixOps helper (Linux-only)

Usage: scripts/anixops.sh <command>

Commands:
  help            Show this help
  setup-venv      Create venv and install dependencies
  install         Install/upgrade dependencies in existing venv
  ping            ansible all -m ping
  deploy          ansible-playbook -i inventory/hosts.yml playbooks/site.yml
  quick-setup     ansible-playbook -i inventory/hosts.yml playbooks/quick-setup.yml (含监控和防火墙)
  firewall-setup  ansible-playbook -i inventory/hosts.yml playbooks/firewall-setup.yml
  health-check    ansible-playbook -i inventory/hosts.yml playbooks/health-check.yml
  web-servers     ansible-playbook -i inventory/hosts.yml playbooks/web-servers.yml
  observability   ansible-playbook -i inventory/hosts.yml playbooks/observability.yml
  cf-setup        Setup Cloudflare DNS records from .env
  cf-proxy-on     Enable Cloudflare proxy (小黄云) for domain
  cf-proxy-off    Disable Cloudflare proxy for domain
  clean-venv      Remove the venv directory

Tips:
- Configure your inventory in inventory/hosts.yml
- Ensure your SSH key path is set in inventory vars if needed
EOF
}

cmd=${1:-help}
shift || true

case "$cmd" in
  help|-h|--help)
    usage
    ;;
  setup-venv)
    create_venv
    activate_venv
    install_requirements
    ;;
  install)
    if [[ ! -d "$VENV_DIR" ]]; then
      warn "Venv missing; creating one first"
      create_venv
    fi
    activate_venv
    install_requirements
    ;;
  clean-venv)
    if [[ -d "$VENV_DIR" ]]; then
      rm -rf "$VENV_DIR"
      ok "Removed $VENV_DIR"
    else
      warn "No venv to remove"
    fi
    ;;
  ping)
    ensure_venv_ready
    need_cmd ansible
    ansible all -i "$INVENTORY" -m ping "$@"
    ;;
  deploy)
    ensure_venv_ready
    need_cmd ansible-playbook
    ansible-playbook -i "$INVENTORY" playbooks/site.yml "$@"
    ;;
  quick-setup)
    ensure_venv_ready
    need_cmd ansible-playbook
    ansible-playbook -i "$INVENTORY" playbooks/quick-setup.yml "$@"
    ;;
  firewall-setup)
    ensure_venv_ready
    need_cmd ansible-playbook
    ansible-playbook -i "$INVENTORY" playbooks/firewall-setup.yml "$@"
    ;;
  health-check)
    ensure_venv_ready
    need_cmd ansible-playbook
    ansible-playbook -i "$INVENTORY" playbooks/health-check.yml "$@"
    ;;
  web-servers)
    ensure_venv_ready
    need_cmd ansible-playbook
    ansible-playbook -i "$INVENTORY" playbooks/web-servers.yml "$@"
    ;;
  observability)
    ensure_venv_ready
    need_cmd ansible-playbook
    ansible-playbook -i "$INVENTORY" playbooks/observability.yml "$@"
    ;;
  cf-setup)
    ensure_venv_ready
    need_cmd python3
    if [[ -z "$CLOUDFLARE_ZONE_ID" ]]; then
      err "CLOUDFLARE_ZONE_ID not set in .env"
      exit 1
    fi
    python3 tools/cloudflare_manager.py from-env -z "$CLOUDFLARE_ZONE_ID"
    ;;
  cf-proxy-on)
    ensure_venv_ready
    need_cmd python3
    if [[ -z "$CLOUDFLARE_ZONE_ID" ]]; then
      err "CLOUDFLARE_ZONE_ID not set in .env"
      exit 1
    fi
    if [[ -z "$1" ]]; then
      err "Usage: $0 cf-proxy-on <domain>"
      exit 1
    fi
    python3 tools/cloudflare_manager.py proxy-on -z "$CLOUDFLARE_ZONE_ID" -n "$1"
    ;;
  cf-proxy-off)
    ensure_venv_ready
    need_cmd python3
    if [[ -z "$CLOUDFLARE_ZONE_ID" ]]; then
      err "CLOUDFLARE_ZONE_ID not set in .env"
      exit 1
    fi
    if [[ -z "$1" ]]; then
      err "Usage: $0 cf-proxy-off <domain>"
      exit 1
    fi
    python3 tools/cloudflare_manager.py proxy-off -z "$CLOUDFLARE_ZONE_ID" -n "$1"
    ;;
  *)
    err "Unknown command: $cmd"
    usage
    exit 1
    ;;
 esac
