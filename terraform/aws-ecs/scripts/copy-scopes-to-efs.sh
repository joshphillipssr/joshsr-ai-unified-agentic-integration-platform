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
TERRAFORM_PARENT="$(dirname "$TERRAFORM_DIR")"
REPO_ROOT="$(dirname "$TERRAFORM_PARENT")"

# Source file
SCOPES_SRC="${REPO_ROOT}/auth_server/scopes.yml"

if [ ! -f "$SCOPES_SRC" ]; then
    echo -e "${RED}Error: scopes.yml not found at $SCOPES_SRC${NC}"
    exit 1
fi

echo "Source file: $SCOPES_SRC"

# --- S3 Bucket Setup ---
echo -e "${YELLOW}Setting up S3 bucket for scopes.yml...${NC}"

# Get AWS account ID for bucket naming
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
S3_BUCKET_NAME="mcp-gateway-scopes-${ACCOUNT_ID}"

echo "S3 Bucket Name: $S3_BUCKET_NAME"

# Check if bucket exists, if not create it
if aws s3 ls "s3://${S3_BUCKET_NAME}" 2>&1 | grep -q 'NoSuchBucket'; then
    echo -e "${YELLOW}Creating S3 bucket: $S3_BUCKET_NAME${NC}"
    aws s3 mb "s3://${S3_BUCKET_NAME}" --region us-west-2
    echo -e "${GREEN}S3 bucket created${NC}"
else
    echo "S3 bucket already exists"
fi

# Upload scopes.yml to S3
echo -e "${YELLOW}Uploading scopes.yml to S3...${NC}"
aws s3 cp "$SCOPES_SRC" "s3://${S3_BUCKET_NAME}/scopes.yml" --region us-west-2
echo -e "${GREEN}scopes.yml uploaded to S3${NC}"

# Get EFS file system ID from terraform output or AWS CLI
cd "$TERRAFORM_DIR"
EFS_ID=$(terraform output -json 2>/dev/null | jq -r '.mcp_gateway_efs_id.value // empty' 2>/dev/null || echo "")

# If not found in terraform output, get from AWS CLI
if [ -z "$EFS_ID" ]; then
    echo "EFS ID not in terraform output, fetching from AWS..."
    EFS_ID=$(aws efs describe-file-systems --region us-west-2 --query 'FileSystems[?Tags[?Key==`Name` && contains(Value, `mcp-gateway`)]].FileSystemId' --output text)
fi

if [ -z "$EFS_ID" ]; then
    echo -e "${RED}Error: Could not get EFS ID from terraform output or AWS${NC}"
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

# Download scopes.yml from S3 and copy to EFS
echo -e "${YELLOW}Downloading scopes.yml from S3 and copying to EFS...${NC}"
TEMP_SCOPES="/tmp/scopes-$$.yml"
aws s3 cp "s3://${S3_BUCKET_NAME}/scopes.yml" "$TEMP_SCOPES" --region us-west-2
sudo cp "$TEMP_SCOPES" "${AUTH_CONFIG_DIR}/scopes.yml"
rm -f "$TEMP_SCOPES"
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
