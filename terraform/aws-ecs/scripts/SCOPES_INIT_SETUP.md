# Scopes Init Container Setup

This guide explains how to initialize the scopes.yml file on the EFS mount using a specialized Docker container.

## Overview

The scopes initialization process uses a lightweight busybox container that:
1. Includes the scopes.yml file from the repository
2. Mounts the EFS auth-config volume
3. Copies scopes.yml to the EFS mount
4. Exits after successful copy

This allows the registry and auth-server containers to read scopes.yml from the shared EFS mount without needing local copies.

## Files

- **Dockerfile.scopes-init** - Minimal busybox container with scopes copy logic
- **build-and-push-scopes-init.sh** - Builds and pushes the container to ECR
- **run-scopes-init-task.sh** - Runs the scopes-init container as an ECS task

## Step 1: Build and Push Container to ECR

```bash
cd /home/ubuntu/repos/mcp-gateway-registry

# Build and push with default settings (latest tag to us-west-2)
./terraform/aws-ecs/scripts/build-and-push-scopes-init.sh

# Or with custom options
./terraform/aws-ecs/scripts/build-and-push-scopes-init.sh \
    --aws-region us-west-2 \
    --image-tag v1.0.0
```

Output will show the image URI, for example:
```
[SUCCESS] Image URI: 123456789.dkr.ecr.us-west-2.amazonaws.com/mcp-gateway-scopes-init:latest
```

## Step 2: Generate Terraform Outputs File

The task runner needs terraform outputs for cluster, EFS, and VPC configuration:

```bash
cd /home/ubuntu/repos/mcp-gateway-registry/terraform/aws-ecs

# Generate outputs file
terraform output -json > ./scripts/terraform-outputs.json
```

## Step 3: Run the Scopes Init Task

```bash
# Use the image URI from Step 1
./terraform/aws-ecs/scripts/run-scopes-init-task.sh \
    --image-uri 123456789.dkr.ecr.us-west-2.amazonaws.com/mcp-gateway-scopes-init:latest

# Or with custom options
./terraform/aws-ecs/scripts/run-scopes-init-task.sh \
    --image-uri <IMAGE_URI> \
    --aws-region us-west-2 \
    --aws-profile default \
    --wait-timeout 300
```

The script will:
1. Create an ECS task definition
2. Run the container on your cluster
3. Wait for completion
4. Display CloudWatch logs
5. Confirm scopes.yml is on the EFS mount

## Workflow Summary

```bash
# 1. Build and push image
./terraform/aws-ecs/scripts/build-and-push-scopes-init.sh

# 2. Generate terraform outputs
cd terraform/aws-ecs
terraform output -json > scripts/terraform-outputs.json
cd ../../

# 3. Run the initialization task
./terraform/aws-ecs/scripts/run-scopes-init-task.sh \
    --image-uri <IMAGE_URI_FROM_STEP_1>

# 4. Force redeploy registry and auth-server to load scopes.yml
aws ecs update-service \
    --cluster mcp-gateway-ecs-cluster \
    --service mcp-gateway-v2-registry \
    --force-new-deployment \
    --region us-west-2

aws ecs update-service \
    --cluster mcp-gateway-ecs-cluster \
    --service mcp-gateway-v2-auth-server \
    --force-new-deployment \
    --region us-west-2
```

## Verification

After the task completes, verify scopes.yml is accessible:

```bash
# Check registry logs for successful scopes loading
./scripts/view-cloudwatch-logs.sh --component registry --minutes 5

# Check auth-server logs
./scripts/view-cloudwatch-logs.sh --component auth-server --minutes 5
```

Look for log messages indicating:
- `SCOPES_CONFIG loaded successfully`
- `Found scope definitions: ...`
- Successful permission mappings

## Troubleshooting

### Task fails to start
- Verify the image URI is correct
- Check that terraform-outputs.json exists and is valid
- Verify AWS credentials and permissions

### Mount point not writable
- Check EFS security group allows access from ECS security group
- Verify EFS access point configuration in terraform

### Scopes.yml not found in container
- Verify auth_server/scopes.yml exists in the repository
- Rebuild the Docker image

### Registry/Auth-server still not loading scopes
- Force redeploy the services after the init task completes
- Check CloudWatch logs for detailed error messages
- Verify file permissions (should be 644 with uid:gid 1000:1000)

## File Locations

- **Local repository**: `/home/ubuntu/repos/mcp-gateway-registry/auth_server/scopes.yml`
- **EFS mount**: `/auth_config/scopes.yml` (root of EFS access point)
- **Container mount**: `/mnt/scopes.yml` (mounted to /auth_config on EFS)
- **Registry path**: `/app/auth_server/scopes.yml` (symlinked to EFS mount)
- **Auth-server path**: `/app/auth_server/scopes.yml` (symlinked to EFS mount)
