#!/bin/bash
# Update ECS task definition to use versioned image tag
# Usage: ./scripts/update-registry-task-def.sh <image-tag>
# Example: ./scripts/update-registry-task-def.sh 0c5e349-test_pr-273-opensearch-abstraction

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ECS_CLUSTER="mcp-gateway-ecs-cluster"
ECS_SERVICE="mcp-gateway-v2-registry"
TASK_FAMILY="mcp-gateway-v2-registry"
ECR_REPO="mcp-gateway-registry"

# Get image tag from argument or determine from git
if [ -n "$1" ]; then
    IMAGE_TAG="$1"
    echo "Using provided image tag: $IMAGE_TAG"
else
    # Determine BUILD_VERSION from git (same logic as build-images.sh)
    cd "$REPO_ROOT"
    GIT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "")

    if [ -n "$GIT_TAG" ]; then
        IMAGE_TAG="${GIT_TAG#v}"
        echo "Using release tag: $IMAGE_TAG"
    else
        GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        # Sanitize branch name for Docker tag (replace / with -)
        GIT_BRANCH="${GIT_BRANCH//\//-}"
        GIT_DESCRIBE=$(git describe --tags --always 2>/dev/null || echo "dev")

        if [[ "$GIT_DESCRIBE" =~ ^[0-9] ]]; then
            IMAGE_TAG="${GIT_DESCRIBE#v}-${GIT_BRANCH}"
        else
            IMAGE_TAG="${GIT_DESCRIBE}-${GIT_BRANCH}"
        fi
        echo "Using development tag: $IMAGE_TAG"
    fi
fi

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"

echo "=========================================="
echo "Update ECS Task Definition"
echo "=========================================="
echo ""
echo "Task Family: $TASK_FAMILY"
echo "Image: $ECR_IMAGE"
echo ""

# Step 1: Get current task definition
echo "Step 1/3: Fetching current task definition..."
echo "------------------------------------------"
TASK_DEF=$(aws ecs describe-task-definition \
    --task-definition "$TASK_FAMILY" \
    --region "$AWS_REGION" \
    --query 'taskDefinition' \
    --output json)

# Extract essential fields and update container image
NEW_TASK_DEF=$(echo "$TASK_DEF" | jq --arg IMAGE "$ECR_IMAGE" '
    del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy) |
    .containerDefinitions[0].image = $IMAGE
')

# Step 2: Register new task definition
echo ""
echo "Step 2/3: Registering new task definition..."
echo "------------------------------------------"
NEW_REVISION=$(aws ecs register-task-definition \
    --cli-input-json "$NEW_TASK_DEF" \
    --region "$AWS_REGION" \
    --query 'taskDefinition.revision' \
    --output text)

echo "Registered new task definition revision: $NEW_REVISION"

# Step 3: Update service to use new task definition
echo ""
echo "Step 3/3: Updating service to use new task definition..."
echo "------------------------------------------"
aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --task-definition "${TASK_FAMILY}:${NEW_REVISION}" \
    --force-new-deployment \
    --region "$AWS_REGION" \
    --output json | jq '{service: .service.serviceName, taskDefinition: .service.taskDefinition, status: .service.status, desiredCount: .service.desiredCount}'

echo ""
echo "=========================================="
echo "Task definition updated successfully!"
echo "=========================================="
echo ""
echo "Service: $ECS_SERVICE"
echo "Task Definition: ${TASK_FAMILY}:${NEW_REVISION}"
echo "Image: $ECR_IMAGE"
echo ""
echo "Monitor deployment with:"
echo "  watch -n 5 'aws ecs describe-services --cluster $ECS_CLUSTER --service $ECS_SERVICE --region $AWS_REGION --query \"services[0].deployments\" --output table'"
