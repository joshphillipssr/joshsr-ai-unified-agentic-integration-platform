#!/bin/bash

# Script to copy scopes.yml to EFS for auth server runtime configuration
# This allows updating scopes without rebuilding the Docker image

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Copying scopes.yml to EFS...${NC}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$TERRAFORM_DIR")"

# Source file
SCOPES_SRC="${REPO_ROOT}/auth_server/scopes.yml"

if [ ! -f "$SCOPES_SRC" ]; then
    echo -e "${RED}Error: scopes.yml not found at $SCOPES_SRC${NC}"
    exit 1
fi

echo "Source file: $SCOPES_SRC"

# Get EFS file system ID from terraform output
cd "$TERRAFORM_DIR"
EFS_ID=$(terraform output -json | jq -r '.mcp_gateway_efs_id.value // empty')

if [ -z "$EFS_ID" ]; then
    echo -e "${RED}Error: Could not get EFS ID from terraform output${NC}"
    exit 1
fi

echo "EFS File System ID: $EFS_ID"

# Get the first mount target to determine availability zone
MOUNT_TARGET=$(aws efs describe-mount-targets --file-system-id "$EFS_ID" --region us-west-2 --query 'MountTargets[0].IpAddress' --output text)

if [ -z "$MOUNT_TARGET" ] || [ "$MOUNT_TARGET" = "None" ]; then
    echo -e "${RED}Error: No mount targets found for EFS $EFS_ID${NC}"
    exit 1
fi

echo "Mount target IP: $MOUNT_TARGET"

# Create temporary mount point
MOUNT_POINT="/tmp/efs-mount-$$"
mkdir -p "$MOUNT_POINT"

echo -e "${YELLOW}Mounting EFS...${NC}"
# Mount EFS
sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport ${MOUNT_TARGET}:/ "$MOUNT_POINT"

# Create auth_config directory if it doesn't exist
AUTH_CONFIG_DIR="${MOUNT_POINT}/auth_config"
sudo mkdir -p "$AUTH_CONFIG_DIR"
sudo chown 1000:1000 "$AUTH_CONFIG_DIR"

# Copy scopes.yml
echo -e "${YELLOW}Copying scopes.yml...${NC}"
sudo cp "$SCOPES_SRC" "${AUTH_CONFIG_DIR}/scopes.yml"
sudo chown 1000:1000 "${AUTH_CONFIG_DIR}/scopes.yml"
sudo chmod 644 "${AUTH_CONFIG_DIR}/scopes.yml"

echo -e "${GREEN}Successfully copied scopes.yml to EFS${NC}"

# Unmount
echo -e "${YELLOW}Unmounting EFS...${NC}"
sudo umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"

echo -e "${GREEN}Done! scopes.yml is now available at /efs/auth_config/scopes.yml in auth server containers${NC}"
echo ""
echo -e "${YELLOW}Note: You may need to restart the auth server service to pick up the changes:${NC}"
echo "aws ecs update-service --cluster mcp-gateway-ecs-cluster --service mcp-gateway-v2-auth --force-new-deployment --region us-west-2"
