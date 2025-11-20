#!/bin/bash

################################################################################
# Build and Push Scopes Init Docker Image to ECR
#
# This script:
# 1. Builds the scopes-init Docker image locally
# 2. Logs into AWS ECR
# 3. Tags the image with repository URI
# 4. Pushes the image to ECR
# 5. Verifies the push was successful
#
# Usage:
#   ./scripts/build-and-push-scopes-init.sh [OPTIONS]
#
# Options:
#   --aws-region REGION        AWS region (default: us-west-2)
#   --image-tag TAG            Image tag (default: latest)
#   --aws-profile PROFILE      AWS profile to use (default: default)
#   --dockerfile PATH          Path to Dockerfile (default: docker/Dockerfile.scopes-init)
#   --build-context PATH       Docker build context (default: .)
#   --no-push                  Build only, don't push to ECR
#   --help                     Show this help message
#
# Examples:
#   # Build and push with defaults (latest tag to us-west-2)
#   ./scripts/build-and-push-scopes-init.sh
#
#   # Build and push with custom tag
#   ./scripts/build-and-push-scopes-init.sh --image-tag v1.0.0
#
#   # Build only, don't push
#   ./scripts/build-and-push-scopes-init.sh --no-push
#
#   # Use different AWS profile and region
#   ./scripts/build-and-push-scopes-init.sh --aws-profile prod --aws-region us-east-1
#
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration with defaults
AWS_REGION="${AWS_REGION:-us-west-2}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
AWS_PROFILE="${AWS_PROFILE:-default}"
DOCKERFILE="docker/Dockerfile.scopes-init"
BUILD_CONTEXT="."
PUSH_TO_ECR=true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

show_help() {
    grep '^#' "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --aws-region)
            AWS_REGION="$2"
            shift 2
            ;;
        --image-tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --aws-profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --dockerfile)
            DOCKERFILE="$2"
            shift 2
            ;;
        --build-context)
            BUILD_CONTEXT="$2"
            shift 2
            ;;
        --no-push)
            PUSH_TO_ECR=false
            shift
            ;;
        --help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# Validate inputs
if [[ ! -f "$REPO_ROOT/$DOCKERFILE" ]]; then
    log_error "Dockerfile not found: $REPO_ROOT/$DOCKERFILE"
    exit 1
fi

if [[ ! -d "$REPO_ROOT/$BUILD_CONTEXT" ]]; then
    log_error "Build context directory not found: $REPO_ROOT/$BUILD_CONTEXT"
    exit 1
fi

# Change to repo root
cd "$REPO_ROOT"

log_info "=========================================="
log_info "Scopes Init Docker Build & Push Script"
log_info "=========================================="
log_info "Repository Root: $REPO_ROOT"
log_info "Dockerfile: $DOCKERFILE"
log_info "Build Context: $BUILD_CONTEXT"
log_info "AWS Region: $AWS_REGION"
log_info "AWS Profile: $AWS_PROFILE"
log_info "Image Tag: $IMAGE_TAG"
log_info "Push to ECR: $PUSH_TO_ECR"
log_info "=========================================="

# Step 1: Build Docker image
log_info "Step 1/5: Building Docker image..."
IMAGE_NAME="mcp-gateway-scopes-init"

if docker build \
    -t "$IMAGE_NAME:$IMAGE_TAG" \
    -f "$DOCKERFILE" \
    "$BUILD_CONTEXT"; then
    log_success "Docker image built successfully: $IMAGE_NAME:$IMAGE_TAG"
else
    log_error "Failed to build Docker image"
    exit 1
fi

# If not pushing, exit here
if [[ "$PUSH_TO_ECR" == "false" ]]; then
    log_success "Build complete. Skipping ECR push as requested."
    log_info "To push manually, run:"
    log_info "  aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin <ECR_URI>"
    log_info "  docker tag $IMAGE_NAME:$IMAGE_TAG <ECR_URI>/$IMAGE_NAME:$IMAGE_TAG"
    log_info "  docker push <ECR_URI>/$IMAGE_NAME:$IMAGE_TAG"
    exit 0
fi

# Step 2: Get AWS account ID
log_info "Step 2/5: Getting AWS account information..."
if [[ -z "$AWS_PROFILE" || "$AWS_PROFILE" == "default" ]]; then
    AWS_ACCOUNT=$(aws sts get-caller-identity \
        --region "$AWS_REGION" \
        --query Account \
        --output text 2>/dev/null)
else
    AWS_ACCOUNT=$(aws sts get-caller-identity \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query Account \
        --output text 2>/dev/null)
fi

if [[ -z "$AWS_ACCOUNT" ]]; then
    log_error "Failed to get AWS account ID. Check AWS credentials and profile."
    exit 1
fi

ECR_REPO_URI="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$IMAGE_NAME"
log_success "AWS Account: $AWS_ACCOUNT"
log_success "ECR Repository URI: $ECR_REPO_URI"

# Create ECR repository if it doesn't exist
log_info "Checking if ECR repository exists..."
if [[ -z "$AWS_PROFILE" || "$AWS_PROFILE" == "default" ]]; then
    if ! aws ecr describe-repositories \
        --repository-names "$IMAGE_NAME" \
        --region "$AWS_REGION" &>/dev/null 2>&1; then
        log_info "Creating ECR repository: $IMAGE_NAME"
        aws ecr create-repository \
            --repository-name "$IMAGE_NAME" \
            --region "$AWS_REGION" &>/dev/null
        log_success "ECR repository created"
    else
        log_success "ECR repository already exists"
    fi
else
    if ! aws ecr describe-repositories \
        --repository-names "$IMAGE_NAME" \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" &>/dev/null 2>&1; then
        log_info "Creating ECR repository: $IMAGE_NAME"
        aws ecr create-repository \
            --repository-name "$IMAGE_NAME" \
            --region "$AWS_REGION" \
            --profile "$AWS_PROFILE" &>/dev/null
        log_success "ECR repository created"
    else
        log_success "ECR repository already exists"
    fi
fi

# Step 3: Login to ECR
log_info "Step 3/5: Logging into AWS ECR..."
if [[ -z "$AWS_PROFILE" || "$AWS_PROFILE" == "default" ]]; then
    if aws ecr get-login-password \
        --region "$AWS_REGION" | docker login \
        --username AWS \
        --password-stdin "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"; then
        log_success "Successfully logged into ECR"
    else
        log_error "Failed to login to ECR"
        exit 1
    fi
else
    if aws ecr get-login-password \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" | docker login \
        --username AWS \
        --password-stdin "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"; then
        log_success "Successfully logged into ECR"
    else
        log_error "Failed to login to ECR"
        exit 1
    fi
fi

# Step 4: Tag image for ECR
log_info "Step 4/5: Tagging image for ECR..."
if docker tag "$IMAGE_NAME:$IMAGE_TAG" "$ECR_REPO_URI:$IMAGE_TAG"; then
    log_success "Image tagged: $ECR_REPO_URI:$IMAGE_TAG"
else
    log_error "Failed to tag image"
    exit 1
fi

# Also tag as latest if not already latest
if [[ "$IMAGE_TAG" != "latest" ]]; then
    if docker tag "$IMAGE_NAME:$IMAGE_TAG" "$ECR_REPO_URI:latest"; then
        log_success "Image also tagged as latest"
    fi
fi

# Step 5: Push image to ECR
log_info "Step 5/5: Pushing image to ECR..."
if docker push "$ECR_REPO_URI:$IMAGE_TAG"; then
    log_success "Image pushed successfully: $ECR_REPO_URI:$IMAGE_TAG"
else
    log_error "Failed to push image to ECR"
    exit 1
fi

# Verify push
log_info "Verifying image in ECR..."
if [[ -z "$AWS_PROFILE" || "$AWS_PROFILE" == "default" ]]; then
    if aws ecr describe-images \
        --repository-name "$IMAGE_NAME" \
        --region "$AWS_REGION" \
        --query "imageDetails[?contains(imageTags, '$IMAGE_TAG')].[imageDigest,imageSizeInBytes,imageTags]" \
        --output table; then
        log_success "Image verification complete"
    else
        log_warning "Could not verify image in ECR (this may be a permissions issue)"
    fi
else
    if aws ecr describe-images \
        --repository-name "$IMAGE_NAME" \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query "imageDetails[?contains(imageTags, '$IMAGE_TAG')].[imageDigest,imageSizeInBytes,imageTags]" \
        --output table; then
        log_success "Image verification complete"
    else
        log_warning "Could not verify image in ECR (this may be a permissions issue)"
    fi
fi

log_success "=========================================="
log_success "Scopes Init image build and push complete!"
log_success "=========================================="
log_info "Image URI: $ECR_REPO_URI:$IMAGE_TAG"
log_info ""

exit 0
