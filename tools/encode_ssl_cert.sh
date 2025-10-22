#!/bin/bash
# SSL Certificate Encoder
# 将 PEM 格式的 SSL 证书编码为 base64，用于存储在 .env 文件中

set -e

echo "=================================================="
echo "  SSL Certificate Encoder for AnixOps"
echo "=================================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查参数
if [ $# -lt 2 ]; then
    echo -e "${YELLOW}Usage:${NC}"
    echo "  $0 <cert.pem> <key.pem>"
    echo ""
    echo -e "${YELLOW}Example:${NC}"
    echo "  $0 /path/to/fullchain.pem /path/to/privkey.pem"
    echo ""
    exit 1
fi

CERT_FILE="$1"
KEY_FILE="$2"

# 检查文件是否存在
if [ ! -f "$CERT_FILE" ]; then
    echo -e "${RED}Error: Certificate file not found: $CERT_FILE${NC}"
    exit 1
fi

if [ ! -f "$KEY_FILE" ]; then
    echo -e "${RED}Error: Key file not found: $KEY_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}Encoding certificate...${NC}"
CERT_BASE64=$(cat "$CERT_FILE" | base64 -w 0)

echo -e "${GREEN}Encoding private key...${NC}"
KEY_BASE64=$(cat "$KEY_FILE" | base64 -w 0)

echo ""
echo "=================================================="
echo -e "${GREEN}✓ Encoding complete!${NC}"
echo "=================================================="
echo ""
echo "Add the following lines to your .env file:"
echo ""
echo -e "${YELLOW}SSL_CERTIFICATE_PEM=${NC}${CERT_BASE64}"
echo ""
echo -e "${YELLOW}SSL_CERTIFICATE_KEY_PEM=${NC}${KEY_BASE64}"
echo ""
echo "=================================================="
echo ""
echo -e "${YELLOW}Note:${NC} Keep these values secure. Do not commit .env to version control."
echo ""

# 可选：直接写入 .env 文件
read -p "Do you want to append these to .env file? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ENV_FILE="$(dirname "$0")/../.env"
    
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}Error: .env file not found at $ENV_FILE${NC}"
        exit 1
    fi
    
    # 备份 .env
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✓ Backed up .env file${NC}"
    
    # 更新或添加证书配置
    if grep -q "^SSL_CERTIFICATE_PEM=" "$ENV_FILE"; then
        sed -i "s|^SSL_CERTIFICATE_PEM=.*|SSL_CERTIFICATE_PEM=${CERT_BASE64}|" "$ENV_FILE"
        echo -e "${GREEN}✓ Updated SSL_CERTIFICATE_PEM in .env${NC}"
    else
        echo "SSL_CERTIFICATE_PEM=${CERT_BASE64}" >> "$ENV_FILE"
        echo -e "${GREEN}✓ Added SSL_CERTIFICATE_PEM to .env${NC}"
    fi
    
    if grep -q "^SSL_CERTIFICATE_KEY_PEM=" "$ENV_FILE"; then
        sed -i "s|^SSL_CERTIFICATE_KEY_PEM=.*|SSL_CERTIFICATE_KEY_PEM=${KEY_BASE64}|" "$ENV_FILE"
        echo -e "${GREEN}✓ Updated SSL_CERTIFICATE_KEY_PEM in .env${NC}"
    else
        echo "SSL_CERTIFICATE_KEY_PEM=${KEY_BASE64}" >> "$ENV_FILE"
        echo -e "${GREEN}✓ Added SSL_CERTIFICATE_KEY_PEM to .env${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}✓ .env file updated successfully!${NC}"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
