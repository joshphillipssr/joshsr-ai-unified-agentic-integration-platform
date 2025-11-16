# MCP Gateway Registry - AWS ECS Deployment

Production-ready deployment of MCP Gateway Registry on AWS ECS Fargate with auto-scaling, monitoring, and multi-AZ high availability.

## 🎯 What This Deploys

This Terraform configuration creates a complete production infrastructure:

### **Infrastructure Components**
- **VPC**: Multi-AZ network with 3 availability zones
- **NAT Gateways**: 3 gateways (one per AZ) for high availability
- **ECS Cluster**: Fargate-based container orchestration
- **Application Load Balancer**: HTTP/HTTPS traffic distribution
- **Aurora PostgreSQL**: Serverless v2 database (0.5-2.0 ACU)
- **Security Groups**: Least-privilege network access
- **VPC Endpoints**: Private AWS API access (S3, STS)

### **MCP Gateway Services**
- **Registry Service**: Web UI and REST API (port 7860)
- **Auth Server**: Authentication and authorization (port 8888)
- **Keycloak**: Identity provider (port 8080)

### **Production Features**
- ✅ **Auto-scaling**: 2-4 tasks based on CPU (70%) and memory (80%)
- ✅ **Multi-AZ**: Services distributed across 3 availability zones
- ✅ **Monitoring**: 11 CloudWatch alarms with email notifications
- ✅ **HTTPS**: Optional ACM certificate integration
- ✅ **High Availability**: No single points of failure

## 📋 Prerequisites

### **Required**
- AWS Account with appropriate permissions
- Terraform >= 1.0
- AWS CLI configured with credentials

### **Optional**
- ACM certificate for HTTPS (recommended for production)
- Email address for CloudWatch alarm notifications

## 🚀 Quick Start

### **Step 1: Configure**
```bash
cd terraform/aws-ecs/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
```

### **Step 2: Initialize**
```bash
terraform init
```

### **Step 3: Plan**
```bash
terraform plan
```

### **Step 4: Deploy**
```bash
terraform apply
```

### **Step 5: Access**
```bash
# Get the ALB DNS name
terraform output mcp_gateway_alb_dns

# Access the registry
open http://$(terraform output -raw mcp_gateway_alb_dns)
```

## ⚙️ Configuration Options

### **Basic Configuration**
```hcl
# terraform.tfvars
name       = "mcp-gateway"      # Deployment name
aws_region = "us-east-1"        # AWS region
vpc_cidr   = "10.0.0.0/16"      # VPC CIDR block
```

### **HTTPS Configuration**
```hcl
# Provide ACM certificate ARN to enable HTTPS
certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/xxxxx"
```

### **Monitoring Configuration**
```hcl
enable_monitoring = true
alarm_email       = "ops@example.com"  # Receives CloudWatch alarms
```

## 📊 What Gets Created

### **Network Resources**
- 1 VPC
- 3 Public Subnets (one per AZ)
- 3 Private Subnets (one per AZ)
- 3 NAT Gateways (one per AZ)
- 1 Internet Gateway
- Route Tables and Routes
- VPC Endpoints (S3, STS)

### **Compute Resources**
- 1 ECS Cluster
- 3 ECS Services (Registry, Auth, Keycloak)
- 6-12 ECS Tasks (2-4 per service with auto-scaling)
- 1 Application Load Balancer
- 3 Target Groups

### **Database Resources**
- 1 Aurora PostgreSQL Cluster (Serverless v2)
- 2 Aurora Instances (Multi-AZ)

### **Monitoring Resources**
- 11 CloudWatch Alarms
- 1 SNS Topic (for alarm notifications)
- CloudWatch Log Groups

## 💰 Cost Estimate

| Component | Monthly Cost (USD) |
|-----------|-------------------|
| NAT Gateways (3) | $97 |
| ECS Fargate | $50-150 (auto-scaled) |
| Aurora PostgreSQL | $30-60 (serverless) |
| Application Load Balancer | $16 |
| CloudWatch | $5 |
| **Total** | **$198-328/month** |

**Note:** Costs vary based on:
- Auto-scaling (task count)
- Database usage (ACU hours)
- Data transfer
- CloudWatch metrics/logs

## 🔧 Advanced Configuration

### **Custom Docker Images**
To use custom-built images instead of pre-built ones:

```hcl
# In modules/mcp-gateway/ecs-services.tf
# Update image URIs to point to your registry
```

### **Scaling Configuration**
Adjust auto-scaling parameters in `main.tf`:

```hcl
module "mcp_gateway" {
  # ...
  autoscaling_min_capacity  = 2   # Minimum tasks
  autoscaling_max_capacity  = 10  # Maximum tasks
  autoscaling_target_cpu    = 70  # CPU target %
  autoscaling_target_memory = 80  # Memory target %
}
```

### **Database Configuration**
Adjust Aurora capacity in `modules/mcp-gateway/database.tf`:

```hcl
serverlessv2_scaling_configuration {
  min_capacity = 0.5  # Minimum ACU
  max_capacity = 4.0  # Maximum ACU
}
```

## 📈 Monitoring

### **CloudWatch Alarms**
11 alarms monitor critical metrics:

**ECS Services (6 alarms):**
- Registry CPU > 85%
- Registry Memory > 85%
- Auth CPU > 85%
- Auth Memory > 85%
- Keycloak CPU > 85%
- Keycloak Memory > 85%

**Load Balancer (3 alarms):**
- Unhealthy targets > 0
- 5xx errors > 10/5min
- Response time > 1s

**Database (2 alarms):**
- RDS CPU > 80%
- RDS connections > 80

### **Accessing Logs**
```bash
# View ECS service logs
aws logs tail /aws/ecs/mcp-gateway --follow

# View specific service
aws logs tail /aws/ecs/mcp-gateway/registry --follow
```

## 🔒 Security

### **Network Security**
- All services in private subnets
- ALB in public subnets (only entry point)
- Security groups with least-privilege rules
- VPC endpoints for AWS API calls (no internet)

### **Access Control**
- IAM roles for ECS tasks
- Secrets Manager for sensitive data
- Keycloak for user authentication
- Fine-grained authorization via scopes

## 🎬 Post-Deployment Setup

After Terraform completes, follow these steps to configure Keycloak, create users, and register servers.

### **Step 1: Save Terraform Outputs**
```bash
cd /home/ubuntu/repos/mcp-gateway-registry/terraform/aws-ecs

# Save outputs to JSON file for scripts to use
./scripts/save-terraform-outputs.sh
```

### **Step 2: Initialize Keycloak**
```bash
# Initialize Keycloak realm, clients, groups, and users
# This automatically loads configuration from terraform-outputs.json
cd scripts
./init-keycloak.sh
```

**What this creates:**
- Realm: `mcp-gateway`
- OAuth2 Clients: `mcp-gateway-web`, `mcp-gateway-m2m`
- Groups: `mcp-registry-admin`, `mcp-servers-unrestricted`, `mcp-servers-restricted`, etc.
- Users: `admin`, `testuser`
- Service account: `service-account-mcp-gateway-m2m`

**⚠️ IMPORTANT:** You must complete this step before creating additional users in Step 4, as it creates the required groups.

### **Step 3: Copy Auth Server Configuration to EFS**
```bash
# Copy scopes.yml to EFS for runtime configuration
# This allows updating scopes without rebuilding the auth server image
./copy-scopes-to-efs.sh
```

**What this does:**
- Mounts the EFS file system temporarily
- Copies `auth_server/scopes.yml` to EFS at `/auth_config/scopes.yml`
- Makes the file available to auth server containers at runtime
- Allows scope updates without image rebuilds

**Note:** The auth server will automatically use the EFS-mounted scopes.yml file. If the file doesn't exist on EFS, it falls back to the version baked into the Docker image.

### **Step 4: Create M2M Admin Bot Account**
```bash
# Create a generic M2M admin bot for server management
# The script automatically loads Keycloak URL and credentials
./user_mgmt.sh create-m2m \
  --name registry-admin-bot \
  --groups 'mcp-registry-admin' \
  --description 'Registry admin bot for server management and administration tasks'
```

**Credentials saved to:**
- `.oauth-tokens/registry-admin-bot.json` - Client credentials
- `.oauth-tokens/registry-admin-bot-token.json` - Access token
- `.oauth-tokens/registry-admin-bot.env` - Environment variables

### **Step 5: Register MCP Servers**

#### **Example: Register Cloudflare Documentation Server**
```bash
# The script automatically loads Gateway URL from terraform-outputs.json
./service_mgmt.sh add /home/ubuntu/repos/mcp-gateway-registry/cli/examples/cloudflare-docs-server-config.json
```

#### **Register Your Own Server**
Create a config file:
```json
{
  "server_name": "My MCP Server",
  "path": "/my-server",
  "proxy_pass_url": "https://my-server.example.com/mcp",
  "description": "Description of what this server does",
  "tags": ["productivity", "automation"],
  "supported_transports": ["streamable-http"]
}
```

Then register:
```bash
./service_mgmt.sh add /path/to/your-server-config.json
```

### **Step 6: Create Additional Users**

#### **Create M2M Service Account**
```bash
# For agent/bot access
./user_mgmt.sh create-m2m \
  --name finance-analyst-bot \
  --groups 'mcp-servers-finance/read,mcp-servers-finance/execute' \
  --description 'Finance analyst bot with restricted access'
```

#### **Create Human User**
```bash
# For web UI access
./user_mgmt.sh create-human \
  --username jdoe \
  --email jdoe@example.com \
  --firstname John \
  --lastname Doe \
  --groups 'mcp-servers-restricted/read'
```

### **Step 7: Verify Deployment**

#### **Test Keycloak Login**
```bash
# Web UI login
open https://registry.mycorp.click
# Login with: admin / changeme (change this password!)

# Keycloak admin console
open https://kc.mycorp.click/admin
# Login with Keycloak admin credentials
```

#### **Monitor Services**
```bash
# Check all services health
./service_mgmt.sh monitor

# View CloudWatch logs
./scripts/view-cloudwatch-logs.sh --component auth-server --minutes 10
```

#### **List Users and Groups**
```bash
# List all users
./user_mgmt.sh list-users

# List all groups
./user_mgmt.sh list-groups
```

### **Configuration Loading**

All scripts automatically load configuration from:
1. **Environment variables** (highest priority)
2. **terraform-outputs.json** (automatic fallback)
3. **AWS SSM Parameter Store** (for sensitive values)
4. **Default values** (last resort)

You can override with environment variables:
```bash
export KEYCLOAK_URL="https://kc.mycorp.click"
export GATEWAY_URL="https://registry.mycorp.click"
export KEYCLOAK_ADMIN_PASSWORD="your-password"
```

## 🐍 Python Registry Client (Alternative to Bash)

For programmatic access or Python-based workflows, use the type-safe Python client located in `scripts/`:

### **Installation**
```bash
cd scripts
uv pip install -r requirements.txt
```

### **Quick Examples**

#### **Register a Server**
```bash
uv run python registry_management.py register --config server-config.json
```

#### **List All Servers**
```bash
uv run python registry_management.py list
```

#### **Toggle Server Status**
```bash
uv run python registry_management.py toggle --path /cloudflare-docs
```

#### **Health Check**
```bash
uv run python registry_management.py healthcheck
```

#### **Group Management**
```bash
# Add server to groups
uv run python registry_management.py add-to-groups --server my-server --groups finance,analytics

# List all groups
uv run python registry_management.py list-groups
```

### **Using as a Library**
```python
import subprocess
from registry_client import RegistryClient, InternalServiceRegistration

# Get token
result = subprocess.run(
    ["./get-m2m-token.sh", "registry-admin-bot"],
    capture_output=True, text=True, check=True
)
token = result.stdout.strip()

# Create client
client = RegistryClient(
    registry_url="https://registry.mycorp.click",
    token=token
)

# Register server
registration = InternalServiceRegistration(
    service_path="/my-server",
    name="My MCP Server",
    proxy_pass_url="https://my-server.example.com/mcp",
    supported_transports=["streamable-http"]
)
client.register_service(registration)
```

### **Key Features**
- **Type Safety**: Full Pydantic models for all API operations
- **Token Management**: Automatic JWT retrieval with SSM caching
- **Security**: Tokens redacted in logs (shows only first 8 characters)
- **CLI & Library**: Use as command-line tool or import as Python library

### **Documentation**
See [scripts/PYTHON_CLIENT_README.md](scripts/PYTHON_CLIENT_README.md) for complete documentation.

## 🔄 Updates and Maintenance

### **Update Infrastructure**
```bash
# Pull latest changes
git pull

# Review changes
terraform plan

# Apply updates
terraform apply
```

### **Update Application**
```bash
# ECS will automatically pull new images on task restart
# Force new deployment
aws ecs update-service \
  --cluster mcp-gateway-ecs-cluster \
  --service mcp-gateway-registry \
  --force-new-deployment
```

## 🗑️ Cleanup

### **Destroy Infrastructure**
```bash
terraform destroy
```

**Warning:** This will delete:
- All ECS services and tasks
- Aurora database (with final snapshot)
- VPC and networking
- CloudWatch alarms
- All data (unless backed up)

## 📚 Additional Resources

- [MCP Gateway Documentation](../../docs/)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

## 🆘 Troubleshooting

### **Services Not Starting**
```bash
# Check ECS service events
aws ecs describe-services \
  --cluster mcp-gateway-ecs-cluster \
  --services mcp-gateway-registry

# Check task logs
aws logs tail /aws/ecs/mcp-gateway/registry --follow
```

### **Database Connection Issues**
```bash
# Verify security group rules
aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=mcp-gateway*"

# Check Aurora cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier mcp-gateway-postgres
```

### **ALB Health Checks Failing**
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>
```

## 📞 Support

For issues and questions:
- [GitHub Issues](https://github.com/agentic-community/mcp-gateway-registry/issues)
- [Documentation](../../docs/)
- [Community Discussions](https://github.com/agentic-community/mcp-gateway-registry/discussions)
