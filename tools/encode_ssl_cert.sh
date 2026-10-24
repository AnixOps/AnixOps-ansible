#!/usr/bin/env bash
# =============================================================================
# SSL certificate encoder | SSL 证书编码工具
# =============================================================================
# Encodes a PEM certificate chain and its private key as single-line base64 so
# they can be stored in .env (SSL_CERTIFICATE_PEM / SSL_CERTIFICATE_KEY_PEM)
# and in GitHub Actions secrets.
#
#   Usage: tools/encode_ssl_cert.sh <fullchain.pem> <privkey.pem> [--write]
#
#   --write   also update (or append) both variables in the project's .env;
#             a timestamped backup of .env is kept next to it.
#
# The decoded values are never printed to the terminal by the deploy tooling;
# keep the output of this script out of shell history and chat logs.
# =============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
else
  GREEN=""; YELLOW=""; RED=""; NC=""
fi

usage() {
  cat <<EOF
Usage: $(basename "$0") <cert.pem> <key.pem> [--write]

Encodes the certificate chain and private key as base64 for .env / CI secrets.
  --write    update SSL_CERTIFICATE_PEM / SSL_CERTIFICATE_KEY_PEM in ${ENV_FILE}
Example:
  $(basename "$0") /etc/letsencrypt/live/example.com/fullchain.pem \\
                   /etc/letsencrypt/live/example.com/privkey.pem --write
EOF
}

die() {
  printf '%sError:%s %s\n' "$RED" "$NC" "$1" >&2
  exit 1
}

encode_file() {
  # Portable single-line base64 (GNU `base64 -w 0` is not available on macOS).
  base64 < "$1" | tr -d '\n'
}

upsert_env_var() {
  # upsert_env_var <KEY> <value> <file>: replace the existing line or append one.
  local key=$1 value=$2 file=$3 tmp
  tmp="$(mktemp "${file}.XXXXXX")"
  if grep -q "^${key}=" "$file"; then
    # awk avoids sed delimiter problems with arbitrary base64 payloads.
    awk -v key="$key" -v value="$value" \
      'index($0, key "=") == 1 { print key "=" value; next } { print }' "$file" > "$tmp"
    printf '%s[OK]%s updated %s\n' "$GREEN" "$NC" "$key"
  else
    cat "$file" > "$tmp"
    printf '%s=%s\n' "$key" "$value" >> "$tmp"
    printf '%s[OK]%s added %s\n' "$GREEN" "$NC" "$key"
  fi
  mv "$tmp" "$file"
}

main() {
  local cert_file="" key_file="" write=0 arg
  for arg in "$@"; do
    case "$arg" in
      -h|--help) usage; exit 0 ;;
      --write) write=1 ;;
      -*) die "unknown option: ${arg}" ;;
      *)
        if [[ -z "$cert_file" ]]; then
          cert_file=$arg
        elif [[ -z "$key_file" ]]; then
          key_file=$arg
        else
          die "too many arguments"
        fi
        ;;
    esac
  done

  if [[ -z "$cert_file" || -z "$key_file" ]]; then
    usage >&2
    exit 1
  fi
  [[ -f "$cert_file" ]] || die "certificate file not found: ${cert_file}"
  [[ -f "$key_file" ]] || die "key file not found: ${key_file}"
  grep -q "BEGIN CERTIFICATE" "$cert_file" || die "${cert_file} does not look like a PEM certificate"
  grep -q "PRIVATE KEY" "$key_file" || die "${key_file} does not look like a PEM private key"

  local cert_b64 key_b64
  cert_b64="$(encode_file "$cert_file")"
  key_b64="$(encode_file "$key_file")"

  printf '%s# Add these lines to .env (or store them as CI secrets):%s\n' "$YELLOW" "$NC"
  printf 'SSL_CERTIFICATE_PEM=%s\n' "$cert_b64"
  printf 'SSL_CERTIFICATE_KEY_PEM=%s\n' "$key_b64"
  printf '\n%sKeep these values secret. Never commit .env.%s\n' "$YELLOW" "$NC" >&2

  if (( write )); then
    [[ -f "$ENV_FILE" ]] || die ".env not found at ${ENV_FILE} (cp .env.example .env first)"
    local backup
    backup="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$ENV_FILE" "$backup"
    printf '%s[OK]%s backed up .env to %s\n' "$GREEN" "$NC" "$backup" >&2
    upsert_env_var SSL_CERTIFICATE_PEM "$cert_b64" "$ENV_FILE"
    upsert_env_var SSL_CERTIFICATE_KEY_PEM "$key_b64" "$ENV_FILE"
    printf '%s[OK]%s .env updated\n' "$GREEN" "$NC" >&2
  fi
}

main "$@"
