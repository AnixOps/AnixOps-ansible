#!/usr/bin/env bash
# =============================================================================
# AnixOps CLI | AnixOps 命令行工具
# =============================================================================
# Single entry point for the day-to-day operation of this repository:
# provisioning, maintenance, lifecycle management, local Kubernetes labs and
# static validation (lint / syntax / tests).
#
#   Usage: scripts/anixops.sh <command> [arguments] [options] [-- ansible-args]
#   Help:  scripts/anixops.sh --help
#
# Design rules | 设计原则:
#   * Every ansible-playbook invocation is printed verbatim before it starts and
#     tee'd to a timestamped log file under --log-dir (default .ansible/logs).
#   * Commands that change production hosts ask for confirmation unless --yes.
#   * .env is parsed line by line (KEY=value) and exported; nothing is eval'd.
#   * Exit codes are stable (EX_* below) so CI and wrappers can rely on them.
# =============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

# --- Exit codes --------------------------------------------------------------
readonly EX_OK=0          # success
readonly EX_FAIL=1        # the requested command failed (ansible / lint / tests)
readonly EX_USAGE=2       # bad arguments
readonly EX_DEPENDENCY=3  # a required tool is missing
readonly EX_CANCELLED=4   # the operator declined a confirmation prompt
readonly EX_CONFIG=5      # a required file is missing (inventory, playbook, ...)

# --- Locations ---------------------------------------------------------------
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SCRIPT_NAME SCRIPT_DIR PROJECT_ROOT

ANIXOPS_VERSION="$(cat "${PROJECT_ROOT}/VERSION" 2>/dev/null || echo "unknown")"
ANIXOPS_VERSION="${ANIXOPS_VERSION//[[:space:]]/}"
ANIXOPS_VERSION="${ANIXOPS_VERSION#v}"
readonly ANIXOPS_VERSION

readonly DEFAULT_INVENTORY="inventories/production/hosts.yml"
readonly DEV_INVENTORY="inventories/development/hosts.yml"
readonly DEFAULT_LOG_DIR=".ansible/logs"

# Roles accepted by the lifecycle commands (status / rollback / cleanup-role).
readonly -a VALID_ROLES=(
  common nginx node_exporter promtail prometheus loki grafana
  firewall acme_ssl postgresql v2board v2bx speedtest
)

# --- Options (filled by parse_args) -------------------------------------------
INVENTORY=""
INVENTORY_EXPLICIT=0
LIMIT=""
TAGS=""
SKIP_TAGS=""
DRY_RUN=0
VERBOSE=0
ASSUME_YES=0
VAULT_PASSWORD_FILE=""
ASK_VAULT_PASS=0
LOG_DIR=""
ENV_FILE=""
NO_ENV=0
WITH_DEV=0
SCAN_ONLY=0
ROLLBACK_TIMESTAMP=""
KEEP_BACKUPS=""
declare -a EXTRA_VARS=()
declare -a PASSTHROUGH=()
declare -a POSITIONAL=()
declare -a ANSIBLE_OPTS=()
COMMAND=""
declare -a ARGS=()
PLAN_MODE_OVERRIDE=""

# --- Colours & logging -------------------------------------------------------
C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_CYAN="" C_BOLD="" C_RESET=""

setup_colours() {
  if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-dumb}" != "dumb" ]]; then
    C_RED=$'\033[0;31m'
    C_GREEN=$'\033[0;32m'
    C_YELLOW=$'\033[0;33m'
    C_BLUE=$'\033[0;34m'
    C_CYAN=$'\033[0;36m'
    C_BOLD=$'\033[1m'
    C_RESET=$'\033[0m'
    export ANSIBLE_FORCE_COLOR=1
  else
    export ANSIBLE_NOCOLOR=1
  fi
}

log_info()  { printf '%s[INFO]%s  %s\n' "$C_BLUE" "$C_RESET" "$*" >&2; }
log_ok()    { printf '%s[ OK ]%s  %s\n' "$C_GREEN" "$C_RESET" "$*" >&2; }
log_warn()  { printf '%s[WARN]%s  %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
log_error() { printf '%s[FAIL]%s  %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
log_step()  { printf '\n%s==> %s%s\n' "$C_BOLD" "$*" "$C_RESET" >&2; }
log_debug() { if (( VERBOSE > 0 )); then printf '%s[DBUG]%s  %s\n' "$C_CYAN" "$C_RESET" "$*" >&2; fi; }

die() {
  log_error "$1"
  exit "${2:-$EX_FAIL}"
}

on_error() {
  local exit_code=$1 line=$2 command=$3
  log_error "Unexpected failure (exit ${exit_code}) at ${SCRIPT_NAME}:${line}: ${command}"
  exit "$exit_code"
}
trap 'on_error "$?" "$LINENO" "$BASH_COMMAND"' ERR
trap 'printf "\n"; log_warn "Interrupted."; exit 130' INT

# --- Small helpers -----------------------------------------------------------
rel_path() {
  # Print a path relative to the project root when it lives inside it.
  local p=$1
  printf '%s\n' "${p#"${PROJECT_ROOT}/"}"
}

abs_path() {
  # Make a user supplied path absolute (relative to the caller's cwd).
  local p=$1
  if [[ "$p" == /* ]]; then
    printf '%s\n' "$p"
  else
    printf '%s/%s\n' "$PWD" "${p#./}"
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

join_words() {
  # Join arguments with single spaces (IFS is newline/tab in this script).
  local IFS=' '
  printf '%s' "$*"
}

require_cmd() {
  local c
  for c in "$@"; do
    if ! have_cmd "$c"; then
      die "Required command not found: ${c} (install it or run '${SCRIPT_NAME} setup')" "$EX_DEPENDENCY"
    fi
  done
}

require_file() {
  local f=$1 what=${2:-File}
  if [[ ! -f "$f" ]]; then
    die "${what} not found: $(rel_path "$f")" "$EX_CONFIG"
  fi
}

is_valid_role() {
  local role=$1 r
  for r in "${VALID_ROLES[@]}"; do
    if [[ "$r" == "$role" ]]; then
      return 0
    fi
  done
  return 1
}

require_role_arg() {
  local role=${1:-}
  if [[ -z "$role" ]]; then
    die "Missing <role> argument. Valid roles: $(join_words "${VALID_ROLES[@]}")" "$EX_USAGE"
  fi
  if ! is_valid_role "$role"; then
    die "Unknown role '${role}'. Valid roles: $(join_words "${VALID_ROLES[@]}")" "$EX_USAGE"
  fi
}

print_cmd() {
  # Print a command exactly as it will be executed (shell-quoted).
  local out
  out="$(printf '%q ' "$@")"
  printf '%s$ %s%s\n' "$C_CYAN" "${out% }" "$C_RESET" >&2
}

# --- Confirmations -----------------------------------------------------------
confirm() {
  # confirm "<question>": continue on y/yes, exit EX_CANCELLED otherwise.
  local question=$1 answer=""
  if (( ASSUME_YES )); then
    log_info "--yes given, skipping confirmation: ${question}"
    return 0
  fi
  if [[ ! -t 0 ]]; then
    die "Confirmation required but stdin is not a terminal. Re-run with --yes to proceed." "$EX_USAGE"
  fi
  printf '%s%s%s [y/N] ' "$C_YELLOW" "$question" "$C_RESET" >&2
  IFS= read -r answer || answer=""
  answer="${answer//[[:space:]]/}"
  case "${answer,,}" in
    y|yes) return 0 ;;
    *) log_warn "Cancelled by operator."; exit "$EX_CANCELLED" ;;
  esac
}

confirm_typed() {
  # confirm_typed "<warning>": the operator must type the literal word "yes".
  local warning=$1 answer=""
  if (( ASSUME_YES )); then
    log_info "--yes given, skipping typed confirmation."
    return 0
  fi
  if [[ ! -t 0 ]]; then
    die "Typed confirmation required but stdin is not a terminal. Re-run with --yes to proceed." "$EX_USAGE"
  fi
  printf '%s%s%s\n' "$C_RED" "$warning" "$C_RESET" >&2
  printf "Type 'yes' to continue: " >&2
  IFS= read -r answer || answer=""
  answer="${answer//[[:space:]]/}"
  if [[ "$answer" != "yes" ]]; then
    log_warn "Cancelled by operator."
    exit "$EX_CANCELLED"
  fi
}

# --- Environment: venv + .env ------------------------------------------------
activate_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    log_debug "Virtualenv already active: ${VIRTUAL_ENV}"
    return 0
  fi
  local candidate
  for candidate in "${PROJECT_ROOT}/venv" "${PROJECT_ROOT}/.venv"; do
    if [[ -f "${candidate}/bin/activate" ]]; then
      set +u
      # shellcheck disable=SC1091
      source "${candidate}/bin/activate"
      set -u
      log_debug "Activated virtualenv $(rel_path "$candidate")"
      return 0
    fi
  done
  log_debug "No virtualenv found (looked for ./venv and ./.venv); using system Python."
}

load_env_file() {
  # Parse KEY=value lines and export them. Existing environment variables win.
  # Supports: blank lines, # comments, optional 'export ' prefix, single or
  # double quoted values, and trailing ' # comment' on unquoted values.
  local file=$1
  local line key value lineno=0 loaded=0 skipped=0

  while IFS= read -r line || [[ -n "$line" ]]; do
    lineno=$((lineno + 1))
    line="${line%$'\r'}"
    line="${line#"${line%%[![:space:]]*}"}"              # ltrim
    if [[ -z "$line" || "$line" == \#* ]]; then
      continue
    fi
    if [[ "$line" == export[[:space:]]* ]]; then
      line="${line#export}"
      line="${line#"${line%%[![:space:]]*}"}"
    fi
    if [[ "$line" != *=* ]]; then
      log_warn "$(rel_path "$file"):${lineno}: ignoring line without '='"
      skipped=$((skipped + 1))
      continue
    fi
    key="${line%%=*}"
    value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"                 # rtrim
    if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      log_warn "$(rel_path "$file"):${lineno}: ignoring invalid variable name '${key}'"
      skipped=$((skipped + 1))
      continue
    fi
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if (( ${#value} >= 2 )) && [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" =~ ^(.*[^[:space:]])[[:space:]]+#.*$ ]]; then
      value="${BASH_REMATCH[1]}"
    fi
    if [[ -n "${!key+x}" ]]; then
      log_debug "${key} already set in the environment; keeping the existing value"
      continue
    fi
    export "${key?}=${value}"
    loaded=$((loaded + 1))
  done < "$file"

  log_debug "Loaded ${loaded} variable(s) from $(rel_path "$file") (${skipped} skipped)"
}

load_env() {
  if (( NO_ENV )); then
    log_debug "--no-env given; skipping .env"
    return 0
  fi
  if [[ -n "$ENV_FILE" ]]; then
    require_file "$ENV_FILE" "Environment file"
    load_env_file "$ENV_FILE"
  elif [[ -f "${PROJECT_ROOT}/.env" ]]; then
    load_env_file "${PROJECT_ROOT}/.env"
  else
    log_debug "No .env file found (copy .env.example to .env if you need one)."
  fi
}

# --- Ansible invocation ------------------------------------------------------
verbose_flag() {
  local n=$VERBOSE flag="-"
  if (( n <= 0 )); then
    return 0
  fi
  if (( n > 4 )); then n=4; fi
  while (( n-- > 0 )); do flag+="v"; done
  printf '%s\n' "$flag"
}

build_common_opts() {
  # Options shared by ansible and ansible-playbook.
  ANSIBLE_OPTS=(-i "$INVENTORY")
  local vflag
  vflag="$(verbose_flag)"
  if [[ -n "$vflag" ]]; then
    ANSIBLE_OPTS+=("$vflag")
  fi
  if [[ -n "$VAULT_PASSWORD_FILE" ]]; then
    ANSIBLE_OPTS+=(--vault-password-file "$VAULT_PASSWORD_FILE")
  fi
  if (( ASK_VAULT_PASS )); then
    ANSIBLE_OPTS+=(--ask-vault-pass)
  fi
  local v
  for v in ${EXTRA_VARS[@]+"${EXTRA_VARS[@]}"}; do
    ANSIBLE_OPTS+=(-e "$v")
  done
}

build_playbook_opts() {
  # build_playbook_opts [no-check]: playbook-only options on top of the common ones.
  local mode=${1:-check}
  build_common_opts
  if [[ -n "$LIMIT" ]]; then
    ANSIBLE_OPTS+=(--limit "$LIMIT")
  fi
  if [[ -n "$TAGS" ]]; then
    ANSIBLE_OPTS+=(--tags "$TAGS")
  fi
  if [[ -n "$SKIP_TAGS" ]]; then
    ANSIBLE_OPTS+=(--skip-tags "$SKIP_TAGS")
  fi
  if (( DRY_RUN )) && [[ "$mode" != "no-check" ]]; then
    ANSIBLE_OPTS+=(--check --diff)
  fi
  ANSIBLE_OPTS+=(${PASSTHROUGH[@]+"${PASSTHROUGH[@]}"})
}

show_plan() {
  # show_plan <playbook> [extra args...]
  local playbook=$1
  shift
  local mode="apply changes"
  if (( DRY_RUN )); then mode="${PLAN_MODE_OVERRIDE:-check mode + diff (no changes)}"; fi
  {
    printf '\n%sPlan | 执行计划%s\n' "$C_BOLD" "$C_RESET"
    printf '  %-12s %s\n' "Command:"   "$COMMAND"
    printf '  %-12s %s\n' "Playbook:"  "playbooks/${playbook}"
    printf '  %-12s %s\n' "Inventory:" "$(rel_path "$INVENTORY")"
    printf '  %-12s %s\n' "Limit:"     "${LIMIT:-<all hosts in play>}"
    printf '  %-12s %s\n' "Tags:"      "${TAGS:-<all>}"
    printf '  %-12s %s\n' "Skip tags:" "${SKIP_TAGS:-<none>}"
    printf '  %-12s %s\n' "Mode:"      "$mode"
    if (( ${#EXTRA_VARS[@]} > 0 )) || (( $# > 0 )); then
      printf '  %-12s %s\n' "Extra:"   "$(join_words ${EXTRA_VARS[@]+"${EXTRA_VARS[@]}"} "$@")"
    fi
    printf '  %-12s %s\n' "Log dir:"   "$(rel_path "$LOG_DIR")"
    printf '\n'
  } >&2
}

strip_ansi() {
  # strip_ansi <file>: remove colour escape sequences from a log file (portable sed).
  local file=$1 esc tmp
  esc="$(printf '\033')"
  tmp="${file}.tmp"
  if sed "s/${esc}\[[0-9;]*[A-Za-z]//g" "$file" > "$tmp" 2>/dev/null; then
    mv "$tmp" "$file"
  else
    rm -f "$tmp"
  fi
}

run_playbook() {
  # run_playbook <label> <playbook relative to playbooks/> [check|no-check] [extra args...]
  local label=$1 playbook=$2 mode=${3:-check}
  shift 3
  local path="${PROJECT_ROOT}/playbooks/${playbook}"
  require_file "$path" "Playbook"
  require_file "$INVENTORY" "Inventory"
  require_cmd ansible-playbook

  build_playbook_opts "$mode"
  local -a cmd=(ansible-playbook "playbooks/${playbook}" "${ANSIBLE_OPTS[@]}" "$@")

  mkdir -p "$LOG_DIR"
  local stamp log_file rc=0
  stamp="$(date +%Y%m%d-%H%M%S)"
  log_file="${LOG_DIR}/${stamp}-${label}.log"

  log_step "Running ansible-playbook (${label})"
  print_cmd "${cmd[@]}"
  log_info "Log file: $(rel_path "$log_file")"

  cd "$PROJECT_ROOT"
  "${cmd[@]}" 2>&1 | tee "$log_file" || rc=$?
  strip_ansi "$log_file"

  if (( rc != 0 )); then
    die "ansible-playbook exited with status ${rc}. Full output: $(rel_path "$log_file")" "$rc"
  fi
  log_ok "${label} finished. Log: $(rel_path "$log_file")"
}

run_adhoc() {
  # run_adhoc <host-pattern> <ansible args...>
  local pattern=$1
  shift
  require_file "$INVENTORY" "Inventory"
  require_cmd ansible
  build_common_opts
  local -a cmd=(ansible "$pattern" "${ANSIBLE_OPTS[@]}" "$@" ${PASSTHROUGH[@]+"${PASSTHROUGH[@]}"})
  print_cmd "${cmd[@]}"
  cd "$PROJECT_ROOT"
  local rc=0
  "${cmd[@]}" || rc=$?
  if (( rc != 0 )); then
    die "ansible exited with status ${rc}" "$rc"
  fi
}

warn_tags_overridden() {
  if [[ -n "$TAGS" ]]; then
    log_warn "--tags is ignored by lifecycle commands (the action selects the tag)."
  fi
}

# --- Commands: environment ---------------------------------------------------
cmd_setup() {
  require_cmd python3
  local venv="${PROJECT_ROOT}/venv"
  cd "$PROJECT_ROOT"

  log_step "Python virtual environment"
  if [[ -f "${venv}/bin/activate" ]]; then
    log_info "Reusing existing virtualenv ./venv"
  else
    print_cmd python3 -m venv "$venv"
    python3 -m venv "$venv"
    log_ok "Created ./venv"
  fi
  set +u
  # shellcheck disable=SC1091
  source "${venv}/bin/activate"
  set -u

  log_step "Python dependencies"
  print_cmd python -m pip install --upgrade pip
  python -m pip install --upgrade pip
  print_cmd python -m pip install -r requirements.txt
  python -m pip install -r requirements.txt
  if (( WITH_DEV )) && [[ -f requirements-dev.txt ]]; then
    print_cmd python -m pip install -r requirements-dev.txt
    python -m pip install -r requirements-dev.txt
  fi

  log_step "Ansible collections"
  require_file "${PROJECT_ROOT}/requirements.yml" "Collection requirements"
  print_cmd ansible-galaxy collection install -r requirements.yml
  ansible-galaxy collection install -r requirements.yml

  if [[ ! -f .env && -f .env.example ]]; then
    log_warn "No .env found. Create one with: cp .env.example .env"
  fi
  log_ok "Setup complete. Activate the environment with: source venv/bin/activate"
}

DOCTOR_PASS=0
DOCTOR_WARN=0
DOCTOR_FAIL=0
doc_pass() { DOCTOR_PASS=$((DOCTOR_PASS + 1)); printf '  %s[PASS]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
doc_warn() { DOCTOR_WARN=$((DOCTOR_WARN + 1)); printf '  %s[WARN]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
doc_fail() { DOCTOR_FAIL=$((DOCTOR_FAIL + 1)); printf '  %s[FAIL]%s %s\n' "$C_RED" "$C_RESET" "$*"; }

doctor_tool() {
  # doctor_tool <command> <required|optional> <purpose>
  local tool=$1 level=$2 purpose=$3 version=""
  if have_cmd "$tool"; then
    case "$tool" in
      python3)         version="$(python3 --version 2>&1 | head -n1)" ;;
      ansible-playbook) version="$(ansible-playbook --version 2>/dev/null | head -n1)" ;;
      ansible-lint)    version="$(ansible-lint --version 2>/dev/null | head -n1 | cut -d' ' -f1-2)" ;;
      yamllint)        version="$(yamllint --version 2>/dev/null | head -n1)" ;;
      shellcheck)      version="$(shellcheck --version 2>/dev/null | sed -n 's/^version: //p')" ;;
      kubectl)         version="$(kubectl version --client 2>/dev/null | head -n1)" ;;
      *)               version="$("$tool" --version 2>/dev/null | head -n1)" ;;
    esac
    doc_pass "${tool}: ${version:-found} ${purpose}"
  elif [[ "$level" == "required" ]]; then
    doc_fail "${tool}: not found ${purpose}"
  else
    doc_warn "${tool}: not found ${purpose}"
  fi
}

cmd_doctor() {
  cd "$PROJECT_ROOT"
  printf '%sAnixOps doctor | 环境自检%s  (v%s)\n' "$C_BOLD" "$C_RESET" "$ANIXOPS_VERSION"

  printf '\n%sTools%s\n' "$C_BOLD" "$C_RESET"
  if (( BASH_VERSINFO[0] >= 4 )); then
    doc_pass "bash ${BASH_VERSION}"
  else
    doc_fail "bash ${BASH_VERSION} (bash >= 4 required)"
  fi
  doctor_tool python3 required "(required)"
  doctor_tool ansible-playbook required "(required)"
  doctor_tool ansible-lint optional "(needed by: lint)"
  doctor_tool yamllint optional "(needed by: lint)"
  doctor_tool shellcheck optional "(needed by: pre-commit)"
  doctor_tool docker optional "(needed by: deploy-local)"
  doctor_tool kind optional "(needed by: deploy-local, cleanup-local, status-local)"
  doctor_tool kubectl optional "(needed by: deploy-local, status-local)"

  printf '\n%sEnvironment%s\n' "$C_BOLD" "$C_RESET"
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    doc_pass "virtualenv active: ${VIRTUAL_ENV}"
  else
    doc_warn "no virtualenv active (run '${SCRIPT_NAME} setup' to create ./venv)"
  fi
  if [[ -f .env ]]; then
    doc_pass ".env present"
  else
    doc_warn ".env missing (optional; copy .env.example to .env to provide host addresses and secrets)"
  fi
  if [[ -f ansible.cfg ]]; then
    doc_pass "ansible.cfg present"
  else
    doc_fail "ansible.cfg missing"
  fi
  if mkdir -p "$LOG_DIR" 2>/dev/null && [[ -w "$LOG_DIR" ]]; then
    doc_pass "log directory writable: $(rel_path "$LOG_DIR")"
  else
    doc_fail "log directory not writable: $(rel_path "$LOG_DIR")"
  fi

  printf '\n%sInventory%s\n' "$C_BOLD" "$C_RESET"
  if [[ ! -f "$INVENTORY" ]]; then
    doc_fail "inventory not found: $(rel_path "$INVENTORY")"
  elif ! have_cmd ansible-inventory; then
    doc_warn "ansible-inventory not available; cannot parse $(rel_path "$INVENTORY")"
  else
    local graph_out hosts
    if graph_out="$(ansible-inventory -i "$INVENTORY" --graph 2>&1)"; then
      hosts="$(ansible all -i "$INVENTORY" --list-hosts 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')"
      doc_pass "inventory parses: $(rel_path "$INVENTORY") (${hosts:-?} hosts)"
    else
      doc_fail "inventory does not parse: $(rel_path "$INVENTORY")"
      printf '%s\n' "$graph_out" | sed 's/^/        /'
    fi
  fi
  if [[ -f tools/generate_inventory.py ]]; then
    local drift_rc=0
    python3 tools/generate_inventory.py local --check >/dev/null 2>&1 || drift_rc=$?
    case "$drift_rc" in
      0) doc_pass "inventory matches servers-config.yml (no drift)" ;;
      1) doc_warn "inventory drift detected; run '${SCRIPT_NAME} gen-inventory' to regenerate" ;;
      *) doc_warn "drift check unavailable (generate_inventory.py --check exited ${drift_rc})" ;;
    esac
  fi

  printf '\n%sCollections%s\n' "$C_BOLD" "$C_RESET"
  if have_cmd ansible-galaxy; then
    local installed coll
    installed="$(ansible-galaxy collection list 2>/dev/null || true)"
    for coll in ansible.posix community.general community.docker kubernetes.core; do
      if grep -q "^${coll} " <<< "$installed"; then
        doc_pass "collection ${coll}"
      else
        doc_warn "collection ${coll} not installed (ansible-galaxy collection install -r requirements.yml)"
      fi
    done
  else
    doc_warn "ansible-galaxy not available; cannot verify collections"
  fi

  printf '\n%sSummary:%s %d passed, %d warnings, %d failed\n' \
    "$C_BOLD" "$C_RESET" "$DOCTOR_PASS" "$DOCTOR_WARN" "$DOCTOR_FAIL"
  if (( DOCTOR_FAIL > 0 )); then
    exit "$EX_FAIL"
  fi
}

# --- Commands: connectivity --------------------------------------------------
cmd_ping() {
  log_step "Ping ${LIMIT:-all} | 测试连接"
  run_adhoc "${LIMIT:-all}" -m ansible.builtin.ping
}

cmd_facts() {
  local host=${ARGS[0]:-}
  if [[ -z "$host" ]]; then
    die "Usage: ${SCRIPT_NAME} facts <host|group>" "$EX_USAGE"
  fi
  log_step "Gather facts for ${host}"
  run_adhoc "$host" -m ansible.builtin.setup
}

cmd_list_hosts() {
  require_file "$INVENTORY" "Inventory"
  require_cmd ansible-inventory
  cd "$PROJECT_ROOT"
  if [[ -n "$LIMIT" ]]; then
    print_cmd ansible "$LIMIT" -i "$INVENTORY" --list-hosts
    ansible "$LIMIT" -i "$INVENTORY" --list-hosts
  else
    print_cmd ansible-inventory -i "$INVENTORY" --graph
    ansible-inventory -i "$INVENTORY" --graph
  fi
}

# --- Commands: provisioning --------------------------------------------------
cmd_deploy() {
  show_plan provision/site.yml
  if (( ! DRY_RUN )); then
    confirm "Deploy playbooks/provision/site.yml to PRODUCTION hosts?"
  fi
  run_playbook deploy provision/site.yml check
}

cmd_quick_setup() {
  show_plan provision/quick-setup.yml
  if (( ! DRY_RUN )); then
    confirm "Run quick-setup (common + monitoring agents + firewall) on production hosts?"
  fi
  run_playbook quick-setup provision/quick-setup.yml check
}

cmd_deploy_web() {
  show_plan provision/web-servers.yml
  if (( ! DRY_RUN )); then
    confirm "Deploy web servers (nginx + TLS) to production hosts?"
  fi
  run_playbook deploy-web provision/web-servers.yml check
}

cmd_deploy_node_platform() {
  show_plan provision/node-platform.yml
  if (( ! DRY_RUN )); then
    confirm "Deploy the AnixOps node platform to production hosts?"
  fi
  run_playbook deploy-node-platform provision/node-platform.yml check
}

# --- Commands: maintenance ---------------------------------------------------
cmd_health() {
  show_plan maintenance/health-check.yml
  run_playbook health-check maintenance/health-check.yml check
}

cmd_firewall() {
  show_plan maintenance/firewall-setup.yml
  if (( ! DRY_RUN )); then
    log_warn "Firewall changes can lock you out. The SSH port is always allowed before UFW is enabled."
    confirm "Apply firewall configuration to production hosts?"
  fi
  run_playbook firewall maintenance/firewall-setup.yml check
}

cmd_fix_docker() {
  show_plan maintenance/fix-docker.yml
  if (( ! DRY_RUN )); then
    confirm "Repair the Docker APT repository / installation on production hosts?"
  fi
  run_playbook fix-docker maintenance/fix-docker.yml check
}

cmd_security_patch() {
  local -a extra=()
  if (( SCAN_ONLY )); then
    extra=(-e security_patch_apply_updates=false)
    log_info "Scan-only mode: vulnerabilities are reported, no packages are updated."
  fi
  show_plan maintenance/security-patch.yml ${extra[@]+"${extra[@]}"}
  if (( ! DRY_RUN && ! SCAN_ONLY )); then
    confirm "Apply security updates on production hosts (may schedule reboots)?"
  fi
  run_playbook security-patch maintenance/security-patch.yml check ${extra[@]+"${extra[@]}"}
}

cmd_ssh_force_apply() {
  show_plan maintenance/ssh-config-force-apply.yml
  if (( ! DRY_RUN )); then
    log_warn "This rewrites /etc/ssh/sshd_config and RESTARTS sshd on every targeted host."
    confirm "Continue with the SSH configuration force-apply?"
    confirm_typed "Second confirmation: a broken sshd_config can lock you out of the hosts."
  fi
  run_playbook ssh-force-apply maintenance/ssh-config-force-apply.yml check
}

# --- Commands: lifecycle -----------------------------------------------------
cmd_status() {
  local role=${ARGS[0]:-}
  require_role_arg "$role"
  warn_tags_overridden
  TAGS="status"
  show_plan maintenance/lifecycle.yml "lifecycle_target_role=${role}"
  run_playbook "status-${role}" maintenance/lifecycle.yml check -e "lifecycle_target_role=${role}"
}

cmd_rollback() {
  local role=${ARGS[0]:-} version=${ARGS[1]:-}
  require_role_arg "$role"
  warn_tags_overridden
  TAGS="rollback"
  # The playbook refuses multi-host rollbacks without lifecycle_confirm_all; the prompt below
  # (or --yes) is that confirmation.
  local -a extra=(-e "lifecycle_target_role=${role}" -e "lifecycle_confirm_all=true")
  if [[ -n "$version" ]]; then
    extra+=(-e "lifecycle_version=${version}")
  fi
  show_plan maintenance/lifecycle.yml "${extra[@]}"
  if (( ! DRY_RUN )); then
    confirm "Roll back role '${role}' to version '${version:-prev}' on ${LIMIT:-all hosts}?"
  fi
  run_playbook "rollback-${role}" maintenance/lifecycle.yml check "${extra[@]}"
}

cmd_rollback_files() {
  local role=${ARGS[0]:-}
  require_role_arg "$role"
  # The playbook refuses multi-host rollbacks without rollback_confirm_all; the prompt below
  # (or --yes) is that confirmation.
  local -a extra=(-e "rollback_role=${role}" -e "rollback_confirm_all=true")
  if [[ -n "$ROLLBACK_TIMESTAMP" ]]; then
    extra+=(-e "rollback_timestamp=${ROLLBACK_TIMESTAMP}")
  fi
  if (( DRY_RUN )); then
    # The playbook has its own dry-run switch; --check would hide the backup listing.
    extra+=(-e "rollback_dry_run=true")
    PLAN_MODE_OVERRIDE="playbook dry run (rollback_dry_run=true, lists backups only)"
    log_info "Dry run: the playbook lists the backup files it would restore."
  fi
  show_plan maintenance/rollback.yml "${extra[@]}"
  if (( ! DRY_RUN )); then
    confirm "Restore the newest${ROLLBACK_TIMESTAMP:+ (timestamp ${ROLLBACK_TIMESTAMP})} config backups of '${role}'?"
  fi
  run_playbook "rollback-files-${role}" maintenance/rollback.yml no-check "${extra[@]}"
}

cmd_cleanup_role() {
  local role=${ARGS[0]:-} keep=${KEEP_BACKUPS:-5}
  require_role_arg "$role"
  warn_tags_overridden
  TAGS="cleanup"
  local -a extra=(
    -e "lifecycle_target_role=${role}" -e "cleanup_confirm=yes" -e "cleanup_keep_backups=${keep}"
    -e "lifecycle_confirm_all=true"
  )
  show_plan maintenance/lifecycle.yml "${extra[@]}"
  if (( ! DRY_RUN )); then
    confirm_typed "cleanup-role removes the '${role}' service, its configuration and all but ${keep} backups on ${LIMIT:-all hosts}."
  fi
  run_playbook "cleanup-${role}" maintenance/lifecycle.yml check "${extra[@]}"
}

# --- Commands: Kubernetes platforms ------------------------------------------
cmd_deploy_local() {
  require_cmd docker kind kubectl
  if (( ! INVENTORY_EXPLICIT )); then
    INVENTORY="${PROJECT_ROOT}/${DEV_INVENTORY}"
  fi
  show_plan platform/kind.yml
  run_playbook deploy-local platform/kind.yml check
  log_info "Next steps: kubectl get nodes; kubectl get pods --all-namespaces"
}

cmd_deploy_remote_test() {
  show_plan platform/k3s-test.yml
  if (( ! DRY_RUN )); then
    confirm "Deploy the K3s TEST cluster (playbooks/platform/k3s-test.yml)?"
  fi
  run_playbook deploy-remote-test platform/k3s-test.yml check
}

cmd_deploy_production_k3s() {
  show_plan platform/k3s.yml
  if (( ! DRY_RUN )); then
    confirm_typed "This provisions the PRODUCTION K3s cluster (playbooks/platform/k3s.yml) on k8s_servers."
  fi
  run_playbook deploy-production-k3s platform/k3s.yml check
}

kind_cluster_name() {
  local name="${KIND_CLUSTER_NAME:-}"
  if [[ -z "$name" && -f "${PROJECT_ROOT}/roles/k8s_provision/defaults/main.yml" ]]; then
    name="$(sed -n 's/^kind_cluster_name:[[:space:]]*"\{0,1\}\([^"#]*\)"\{0,1\}.*/\1/p' \
      "${PROJECT_ROOT}/roles/k8s_provision/defaults/main.yml" | head -n1 | tr -d '[:space:]')"
  fi
  printf '%s\n' "${name:-anixops-dev}"
}

cmd_cleanup_local() {
  require_cmd kind
  local name
  name="$(kind_cluster_name)"
  if ! kind get clusters 2>/dev/null | grep -qx "$name"; then
    log_info "No kind cluster named '${name}' exists; nothing to do."
    return 0
  fi
  confirm "Delete the local kind cluster '${name}'?"
  print_cmd kind delete cluster --name "$name"
  kind delete cluster --name "$name"
  log_ok "Deleted kind cluster '${name}'"
}

cmd_status_local() {
  require_cmd kind kubectl
  printf '%skind clusters%s\n' "$C_BOLD" "$C_RESET"
  kind get clusters 2>/dev/null || printf '  (none)\n'
  printf '\n%skubectl context%s\n' "$C_BOLD" "$C_RESET"
  kubectl config current-context 2>/dev/null || printf '  (no context set)\n'
  printf '\n%scluster-info%s\n' "$C_BOLD" "$C_RESET"
  kubectl cluster-info 2>/dev/null || printf '  (cluster not reachable)\n'
  printf '\n%snodes%s\n' "$C_BOLD" "$C_RESET"
  kubectl get nodes 2>/dev/null || printf '  (cannot list nodes)\n'
  printf '\n%spods (all namespaces)%s\n' "$C_BOLD" "$C_RESET"
  kubectl get pods --all-namespaces 2>/dev/null || printf '  (cannot list pods)\n'
}

# --- Commands: validation ----------------------------------------------------
cmd_lint() {
  require_cmd yamllint ansible-lint
  cd "$PROJECT_ROOT"
  local failures=0
  local -a paths=(${ARGS[@]+"${ARGS[@]}"})

  log_step "yamllint"
  if (( ${#paths[@]} > 0 )); then
    print_cmd yamllint -c .yamllint.yml "${paths[@]}"
    yamllint -c .yamllint.yml "${paths[@]}" || failures=$((failures + 1))
  else
    print_cmd yamllint -c .yamllint.yml .
    yamllint -c .yamllint.yml . || failures=$((failures + 1))
  fi

  log_step "ansible-lint"
  print_cmd ansible-lint --offline ${paths[@]+"${paths[@]}"}
  ansible-lint --offline ${paths[@]+"${paths[@]}"} || failures=$((failures + 1))

  if (( failures > 0 )); then
    die "lint: ${failures} linter(s) reported problems" "$EX_FAIL"
  fi
  log_ok "lint: clean"
}

cmd_syntax() {
  require_cmd ansible-playbook
  cd "$PROJECT_ROOT"
  local pb inv out rc failed=0 total=0
  local -a failed_list=()

  log_step "ansible-playbook --syntax-check (all playbooks)"
  while IFS= read -r pb; do
    total=$((total + 1))
    inv="$INVENTORY"
    if [[ "$pb" == playbooks/platform/kind.yml && ! $INVENTORY_EXPLICIT -eq 1 ]]; then
      inv="${PROJECT_ROOT}/${DEV_INVENTORY}"
    fi
    rc=0
    out="$(ansible-playbook --syntax-check -i "$inv" "$pb" 2>&1)" || rc=$?
    if (( rc == 0 )); then
      printf '  %s[PASS]%s %s\n' "$C_GREEN" "$C_RESET" "$pb"
    else
      failed=$((failed + 1))
      failed_list+=("$pb")
      printf '  %s[FAIL]%s %s\n' "$C_RED" "$C_RESET" "$pb"
      printf '%s\n' "$out" | grep -v '^\[WARNING\]' | sed 's/^/        /'
    fi
  done < <(find playbooks -mindepth 2 -maxdepth 2 -name '*.yml' -type f | sort)

  printf '\n%d playbook(s) checked, %d failed\n' "$total" "$failed"
  if (( failed > 0 )); then
    die "syntax: failed playbooks: $(join_words "${failed_list[@]}")" "$EX_FAIL"
  fi
  log_ok "syntax: all playbooks pass"
}

cmd_test() {
  require_cmd python3
  cd "$PROJECT_ROOT"
  if ! python3 -c 'import pytest' 2>/dev/null; then
    die "pytest is not installed (pip install -r requirements-dev.txt)" "$EX_DEPENDENCY"
  fi
  print_cmd python3 -m pytest -q tests ${ARGS[@]+"${ARGS[@]}"}
  python3 -m pytest -q tests ${ARGS[@]+"${ARGS[@]}"} || die "tests failed" "$EX_FAIL"
  log_ok "tests passed"
}

cmd_gen_inventory() {
  require_cmd python3
  cd "$PROJECT_ROOT"
  require_file "${PROJECT_ROOT}/tools/generate_inventory.py" "Inventory generator"
  local target="${PROJECT_ROOT}/${DEFAULT_INVENTORY}" tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/anixops-inventory.XXXXXX")"
  # shellcheck disable=SC2064  # expand tmp now; it never changes afterwards
  trap "rm -f '${tmp}'" EXIT

  log_step "Rendering inventory from servers-config.yml"
  print_cmd python3 tools/generate_inventory.py local --output "$tmp"
  python3 tools/generate_inventory.py local --output "$tmp"

  if [[ -f "$target" ]] && cmp -s "$tmp" "$target"; then
    log_ok "$(rel_path "$target") is already up to date."
    return 0
  fi
  if [[ -f "$target" ]]; then
    log_info "Changes against the current $(rel_path "$target"):"
    diff -u "$target" "$tmp" | head -n 80 || true
    if (( DRY_RUN )); then
      log_info "Dry run: inventory not written."
      return 0
    fi
    confirm "Overwrite $(rel_path "$target") with the rendered inventory?"
  fi
  cp "$tmp" "$target"
  log_ok "Wrote $(rel_path "$target")"
  if have_cmd ansible-inventory; then
    ansible-inventory -i "$target" --graph >/dev/null || die "Generated inventory does not parse" "$EX_FAIL"
    log_ok "Generated inventory parses with ansible-inventory"
  fi
}

cmd_version() {
  printf 'anixops %s\n' "$ANIXOPS_VERSION"
}

# --- Help --------------------------------------------------------------------
usage() {
  cat <<EOF
${C_BOLD}AnixOps CLI${C_RESET} v${ANIXOPS_VERSION} | AnixOps 命令行工具

${C_BOLD}Usage:${C_RESET}
  ${SCRIPT_NAME} <command> [arguments] [options] [-- extra ansible-playbook args]

${C_BOLD}Environment${C_RESET}
  setup [--dev]            Create ./venv, pip install requirements, install Galaxy collections
  doctor                   Check tools, .env, inventory parsing, inventory drift, collections
  version                  Print the AnixOps version

${C_BOLD}Connectivity${C_RESET}
  ping                     ansible.builtin.ping all hosts (or --limit) | 测试连接
  facts <host>             Gather and print facts for one host or group
  list-hosts               Show the inventory graph (or --limit hosts)

${C_BOLD}Provisioning (production, confirmation unless --yes)${C_RESET}
  deploy                   provision/site.yml, full deployment | 完整部署
  quick-setup              provision/quick-setup.yml (common + agents + firewall)
  deploy-web               provision/web-servers.yml (nginx + TLS)
  deploy-node-platform     provision/node-platform.yml

${C_BOLD}Maintenance${C_RESET}
  health, health-check     maintenance/health-check.yml (read-only) | 健康检查
  firewall                 maintenance/firewall-setup.yml
  fix-docker               maintenance/fix-docker.yml
  security-patch           maintenance/security-patch.yml; --scan-only reports without updating
  ssh-force-apply          maintenance/ssh-config-force-apply.yml (double confirmation)

${C_BOLD}Lifecycle (roles: $(join_words "${VALID_ROLES[@]}"))${C_RESET}
  status <role>            lifecycle.yml --tags status
  rollback <role> [ver]    lifecycle.yml --tags rollback (prev | initial | vYYYYMMDDTHHMMSS)
  rollback-files <role>    maintenance/rollback.yml: restore config backups
                             [--timestamp YYYY-MM-DD@HH] [--dry-run]
  cleanup-role <role>      lifecycle.yml --tags cleanup [--keep-backups N] (typed confirmation)

${C_BOLD}Kubernetes platforms${C_RESET}
  deploy-local             platform/kind.yml with ${DEV_INVENTORY} (needs docker/kind/kubectl)
  deploy-remote-test       platform/k3s-test.yml (k8s_test group)
  deploy-production-k3s    platform/k3s.yml (k8s_servers group, typed confirmation)
  cleanup-local            Delete the local kind cluster
  status-local             Show kind clusters, kubectl context, nodes and pods

${C_BOLD}Validation${C_RESET}
  lint [paths...]          yamllint + ansible-lint
  syntax                   ansible-playbook --syntax-check for every playbook
  test [pytest args...]    python3 -m pytest -q tests
  gen-inventory            Regenerate ${DEFAULT_INVENTORY} from servers-config.yml (shows a diff first)

${C_BOLD}Options${C_RESET}
  -i, --inventory PATH     Inventory file (default: ${DEFAULT_INVENTORY}, or \$ANIXOPS_INVENTORY)
  -l, --limit, --target P  Limit to hosts/groups pattern P
  -t, --tags TAGS          Only run plays/tasks tagged TAGS (comma separated)
      --skip-tags TAGS     Skip plays/tasks tagged TAGS
  -n, --dry-run, --check   Check mode with diff; nothing is changed
  -e, --extra-vars K=V     Extra variable (repeatable)
  -v, --verbose            Increase ansible verbosity (repeatable: -v, -vv, -vvv)
  -y, --yes, --force       Skip confirmation prompts (required when stdin is not a TTY)
      --vault-password-file PATH / --ask-vault-pass
      --log-dir DIR        Where ansible logs are written (default: ${DEFAULT_LOG_DIR})
      --env-file PATH      Load this file instead of ./.env;  --no-env skips loading
      --scan-only          security-patch: report only (security_patch_apply_updates=false)
      --timestamp TS       rollback-files: pick the backup containing TS
      --keep-backups N     cleanup-role: number of backups to keep (default 5)
      --dev                setup: also install requirements-dev.txt
      --no-color           Disable colours (NO_COLOR=1 is honoured too)
  -h, --help               Show this help;  -V, --version prints the version
  --                       Everything after -- is passed to ansible-playbook unchanged

${C_BOLD}Exit codes${C_RESET}
  0 success   1 command failed   2 usage error   3 missing tool   4 cancelled   5 missing file
  (ansible-playbook failures propagate ansible's own exit status)

${C_BOLD}Examples${C_RESET}
  ${SCRIPT_NAME} deploy --dry-run --tags nginx --limit web_servers
  ${SCRIPT_NAME} security-patch --scan-only --limit jp-1
  ${SCRIPT_NAME} rollback-files nginx --timestamp 2026-04-24@12 --dry-run
  ${SCRIPT_NAME} deploy --yes -- --start-at-task "Deploy nginx configuration"
EOF
}

# --- Argument parsing --------------------------------------------------------
need_value() {
  # need_value <option> <value?>
  if [[ $# -lt 2 || -z "${2:-}" ]]; then
    die "Option $1 requires a value (see --help)" "$EX_USAGE"
  fi
}

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      -h|--help|help)
        usage
        exit "$EX_OK"
        ;;
      -V|--version)
        cmd_version
        exit "$EX_OK"
        ;;
      -i|--inventory)
        need_value "$@"; INVENTORY="$(abs_path "$2")"; INVENTORY_EXPLICIT=1; shift 2 ;;
      --inventory=*)
        INVENTORY="$(abs_path "${1#*=}")"; INVENTORY_EXPLICIT=1; shift ;;
      -l|--limit|--target)
        need_value "$@"; LIMIT=$2; shift 2 ;;
      --limit=*|--target=*)
        LIMIT=${1#*=}; shift ;;
      -t|--tags)
        need_value "$@"; TAGS=$2; shift 2 ;;
      --tags=*)
        TAGS=${1#*=}; shift ;;
      --skip-tags)
        need_value "$@"; SKIP_TAGS=$2; shift 2 ;;
      --skip-tags=*)
        SKIP_TAGS=${1#*=}; shift ;;
      -n|--dry-run|--check)
        DRY_RUN=1; shift ;;
      -e|--extra-vars)
        need_value "$@"; EXTRA_VARS+=("$2"); shift 2 ;;
      -v|--verbose)
        VERBOSE=$((VERBOSE + 1)); shift ;;
      -vv)   VERBOSE=$((VERBOSE + 2)); shift ;;
      -vvv)  VERBOSE=$((VERBOSE + 3)); shift ;;
      -vvvv) VERBOSE=$((VERBOSE + 4)); shift ;;
      -y|--yes|--force)
        ASSUME_YES=1; shift ;;
      --vault-password-file)
        need_value "$@"; VAULT_PASSWORD_FILE="$(abs_path "$2")"; shift 2 ;;
      --vault-password-file=*)
        VAULT_PASSWORD_FILE="$(abs_path "${1#*=}")"; shift ;;
      --ask-vault-pass)
        ASK_VAULT_PASS=1; shift ;;
      --log-dir)
        need_value "$@"; LOG_DIR="$(abs_path "$2")"; shift 2 ;;
      --log-dir=*)
        LOG_DIR="$(abs_path "${1#*=}")"; shift ;;
      --env-file)
        need_value "$@"; ENV_FILE="$(abs_path "$2")"; shift 2 ;;
      --no-env)
        NO_ENV=1; shift ;;
      --dev)
        WITH_DEV=1; shift ;;
      --scan-only)
        SCAN_ONLY=1; shift ;;
      --timestamp)
        need_value "$@"
        if [[ "$2" =~ [[:space:]] ]]; then
          die "--timestamp must not contain whitespace" "$EX_USAGE"
        fi
        ROLLBACK_TIMESTAMP=$2; shift 2 ;;
      --keep-backups)
        need_value "$@"
        if [[ ! "$2" =~ ^[0-9]+$ ]]; then
          die "--keep-backups expects a non-negative integer, got '$2'" "$EX_USAGE"
        fi
        KEEP_BACKUPS=$2; shift 2 ;;
      --no-color|--no-colour)
        export NO_COLOR=1; shift ;;
      --)
        shift
        PASSTHROUGH=("$@")
        break
        ;;
      -*)
        die "Unknown option: $1 (see --help)" "$EX_USAGE"
        ;;
      *)
        POSITIONAL+=("$1"); shift ;;
    esac
  done
}

# --- Main --------------------------------------------------------------------
main() {
  if (( BASH_VERSINFO[0] < 4 )); then
    printf 'anixops.sh requires bash >= 4 (found %s)\n' "$BASH_VERSION" >&2
    exit "$EX_DEPENDENCY"
  fi

  setup_colours
  parse_args "$@"
  setup_colours  # --no-color may have been given

  if (( ${#POSITIONAL[@]} == 0 )); then
    usage
    exit "$EX_USAGE"
  fi
  COMMAND="${POSITIONAL[0]}"
  ARGS=("${POSITIONAL[@]:1}")

  if [[ -z "$INVENTORY" ]]; then
    if [[ -n "${ANIXOPS_INVENTORY:-}" ]]; then
      INVENTORY="$(abs_path "$ANIXOPS_INVENTORY")"
    else
      INVENTORY="${PROJECT_ROOT}/${DEFAULT_INVENTORY}"
    fi
  fi
  if [[ -z "$LOG_DIR" ]]; then
    LOG_DIR="${PROJECT_ROOT}/${DEFAULT_LOG_DIR}"
  fi

  activate_venv
  load_env
  cd "$PROJECT_ROOT"

  case "$COMMAND" in
    setup)                              cmd_setup ;;
    doctor)                             cmd_doctor ;;
    version)                            cmd_version ;;
    ping)                               cmd_ping ;;
    facts)                              cmd_facts ;;
    list-hosts)                         cmd_list_hosts ;;
    deploy|deploy-all|site)             cmd_deploy ;;
    quick-setup)                        cmd_quick_setup ;;
    deploy-web|deploy-web-servers)      cmd_deploy_web ;;
    deploy-node-platform|node-platform) cmd_deploy_node_platform ;;
    health|health-check)                cmd_health ;;
    firewall|firewall-setup)            cmd_firewall ;;
    fix-docker)                         cmd_fix_docker ;;
    security-patch)                     cmd_security_patch ;;
    ssh-force-apply|ssh-fix)            cmd_ssh_force_apply ;;
    status)                             cmd_status ;;
    rollback)                           cmd_rollback ;;
    rollback-files)                     cmd_rollback_files ;;
    cleanup-role)                       cmd_cleanup_role ;;
    deploy-local)                       cmd_deploy_local ;;
    deploy-remote-test)                 cmd_deploy_remote_test ;;
    deploy-production-k3s|deploy-production) cmd_deploy_production_k3s ;;
    cleanup-local)                      cmd_cleanup_local ;;
    status-local)                       cmd_status_local ;;
    lint)                               cmd_lint ;;
    syntax|syntax-check)                cmd_syntax ;;
    test|tests)                         cmd_test ;;
    gen-inventory|generate-inventory)   cmd_gen_inventory ;;
    deploy-k8s-control-panel|cleanup-remote-test|cleanup-production|status-remote-test|status-production)
      die "Command '${COMMAND}' was removed: its playbook no longer exists. See --help for the current commands." "$EX_USAGE"
      ;;
    *)
      die "Unknown command: ${COMMAND} (see --help)" "$EX_USAGE"
      ;;
  esac
}

main "$@"
