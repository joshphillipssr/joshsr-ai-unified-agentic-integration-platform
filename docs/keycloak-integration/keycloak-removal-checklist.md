# KEYCLOAK REMOVAL CHECKLIST - mcp-gateway-registry
## CRITICAL: Complete Removal of ALL Keycloak Code Before Adding Working Implementation

**Auditor**: DevOps Engineer (Job Security Mode: MAXIMUM)
**Date**: 2025-11-15
**Repository**: mcp-gateway-registry/terraform/aws-ecs
**Total Keycloak References Found**: 284 across 13 files

---

## EXECUTIVE SUMMARY

Before adding our working Keycloak implementation, we must **completely eradicate** all traces of the broken Keycloak from mcp-gateway-registry. Leaving ANY remnants will cause:
- Resource naming conflicts
- Variable conflicts
- Runtime errors from old environment variables
- Terraform state issues
- Deployment failures

This document lists **EVERY SINGLE LINE** that must be removed or modified.

---

## REMOVAL STRATEGY

### Phase 1: Backup Current State
```bash
cd ~/repos/mcp-gateway-registry
git checkout -b backup-broken-keycloak-$(date +%Y%m%d)
git add -A
git commit -m "Backup: Broken Keycloak implementation before removal"
git push origin backup-broken-keycloak-$(date +%Y%m%d)
```

### Phase 2: Create Clean Branch
```bash
git checkout main
git pull origin main
git checkout -b feature/remove-broken-keycloak
```

### Phase 3: Remove Resources (Following this Checklist)

### Phase 4: Verify Removal
```bash
cd terraform/aws-ecs
grep -r "keycloak" --include="*.tf" --include="*.tfvars" -i
# Expected: ZERO results (except in .terraform/ directory which can be ignored)
```

---

## DETAILED REMOVAL CHECKLIST

### FILE 1: `terraform/aws-ecs/modules/mcp-gateway/database.tf`

**REMOVE ENTIRE FILE** - This is ONLY for Keycloak PostgreSQL database.

**Justification**:
- The entire Aurora PostgreSQL cluster is ONLY used by Keycloak
- No other service uses this database
- Line 1 comment confirms: "Aurora PostgreSQL Serverless database for Keycloak"

**Action**:
```bash
rm terraform/aws-ecs/modules/mcp-gateway/database.tf
```

**Resources Being Deleted**:
- `module.aurora_postgresql` (lines 2-61)
- `random_password.keycloak_postgres_password` (referenced from secrets.tf)

---

### FILE 2: `terraform/aws-ecs/modules/mcp-gateway/secrets.tf`

**REMOVE Lines 19-120** (Keycloak-specific secrets)

**Detailed Line-by-Line Removal**:

#### Section A: Random Passwords (Lines 19-35)
```hcl
# DELETE THESE:
resource "random_password" "keycloak_postgres_password" {
  length      = 64
  special     = false
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

resource "random_password" "keycloak_admin_password" {
  length      = 32
  special     = true
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
  min_special = 1
}
```

#### Section B: Database Secrets (Lines 62-82)
```hcl
# DELETE THESE:
resource "aws_secretsmanager_secret" "keycloak_database_url" {
  name_prefix = "${local.name_prefix}-keycloak-database-url-"
  description = "Database URL for Keycloak PostgreSQL"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "keycloak_database_url" {
  secret_id = aws_secretsmanager_secret.keycloak_database_url.id
  secret_string = "postgresql://${module.aurora_postgresql.cluster_master_username}:${module.aurora_postgresql.cluster_master_password}@${module.aurora_postgresql.cluster_endpoint}:${module.aurora_postgresql.cluster_port}/${module.aurora_postgresql.cluster_database_name}"
}

resource "aws_secretsmanager_secret" "keycloak_db_password" {
  name_prefix = "${local.name_prefix}-keycloak-db-password-"
  description = "Database password for Keycloak PostgreSQL"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "keycloak_db_password" {
  secret_id     = aws_secretsmanager_secret.keycloak_db_password.id
  secret_string = random_password.keycloak_postgres_password.result
}
```

#### Section C: Admin Secrets (Lines 84-93)
```hcl
# DELETE THESE:
resource "aws_secretsmanager_secret" "keycloak_admin_password" {
  name_prefix = "${local.name_prefix}-keycloak-admin-password-"
  description = "Admin password for Keycloak"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "keycloak_admin_password" {
  secret_id     = aws_secretsmanager_secret.keycloak_admin_password.id
  secret_string = random_password.keycloak_admin_password.result
}
```

#### Section D: Client Secrets (Lines 96-120)
```hcl
# DELETE THESE:
resource "aws_secretsmanager_secret" "keycloak_client_secret" {
  count       = var.keycloak_client_secret != "" ? 1 : 0
  name_prefix = "${local.name_prefix}-keycloak-client-secret-"
  description = "Keycloak client secret for MCP Gateway Registry"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "keycloak_client_secret" {
  count         = var.keycloak_client_secret != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.keycloak_client_secret[0].id
  secret_string = var.keycloak_client_secret
}

resource "aws_secretsmanager_secret" "keycloak_m2m_client_secret" {
  count       = var.keycloak_m2m_client_secret != "" ? 1 : 0
  name_prefix = "${local.name_prefix}-keycloak-m2m-client-secret-"
  description = "Keycloak M2M client secret for MCP Gateway Registry"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "keycloak_m2m_client_secret" {
  count         = var.keycloak_m2m_client_secret != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.keycloak_m2m_client_secret[0].id
  secret_string = var.keycloak_m2m_client_secret
}
```

**KEEP**: Lines 1-18, 37-60 (non-Keycloak secrets)

---

### FILE 3: `terraform/aws-ecs/modules/mcp-gateway/networking.tf`

**REMOVE Lines 163-289** (Entire Keycloak ALB section)

**Detailed Removal**:

#### Section A: Keycloak ALB Module (Lines 163-253)
```hcl
# DELETE THIS ENTIRE MODULE:
module "keycloak_alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "~> 9.0"

  name               = "${local.name_prefix}-kc-alb"
  load_balancer_type = "application"
  # ... (entire module - lines 163-253)
}
```

#### Section B: HTTPS Listener (Lines 255-269)
```hcl
# DELETE THIS:
resource "aws_lb_listener" "keycloak_https" {
  count = var.keycloak_certificate_arn != "" ? 1 : 0
  # ... (lines 255-269)
}
```

#### Section C: HTTP Redirect Listener (Lines 271-289)
```hcl
# DELETE THIS:
resource "aws_lb_listener" "keycloak_http_redirect" {
  count = var.keycloak_certificate_arn != "" ? 1 : 0
  # ... (lines 271-289)
}
```

**KEEP**: Lines 1-162 (main ALB and service discovery)

---

### FILE 4: `terraform/aws-ecs/modules/mcp-gateway/ecs-services.tf`

**COMPLEX FILE - Multiple Sections to Remove**

#### Section A: Auth Server Environment Variables (Lines 97-121)

**REMOVE Keycloak-specific environment variables**:
```hcl
# Lines 97-121 - DELETE THESE ENV VARS from auth service:
{
  name  = "AUTH_METHOD"
  value = "keycloak"
},
{
  name  = "KEYCLOAK_ENABLED"
  value = "true"
},
{
  name  = "KEYCLOAK_URL"
  value = "http://${module.keycloak_alb.dns_name}:8080"
},
{
  name  = "KEYCLOAK_EXTERNAL_URL"
  value = var.keycloak_external_url != "" ? var.keycloak_external_url : "http://${module.keycloak_alb.dns_name}:8080"
},
{
  name  = "KEYCLOAK_REALM"
  value = var.keycloak_realm
},
{
  name  = "KEYCLOAK_CLIENT_ID"
  value = var.keycloak_client_id
},
{
  name  = "KEYCLOAK_M2M_CLIENT_ID"
  value = var.keycloak_m2m_client_id
},
```

#### Section B: Auth Server Secrets (Lines 131-137)

**REMOVE Keycloak secrets from auth service**:
```hcl
# Lines 131-137 - DELETE THESE SECRETS:
var.keycloak_client_secret != "" ? [{
  name      = "KEYCLOAK_CLIENT_SECRET"
  valueFrom = aws_secretsmanager_secret.keycloak_client_secret[0].arn
}] : [],
var.keycloak_m2m_client_secret != "" ? [{
  name      = "KEYCLOAK_M2M_CLIENT_SECRET"
  valueFrom = aws_secretsmanager_secret.keycloak_m2m_client_secret[0].arn
}] : [],
```

#### Section C: Auth Server Dependency (Line 199)

**REMOVE Keycloak ALB dependency**:
```hcl
# Line 199 - CHANGE FROM:
depends_on = [module.keycloak_alb]

# TO:
depends_on = []
```

#### Section D: Registry Service Environment Variables (Lines 314-334)

**REMOVE Keycloak environment variables from registry service** (similar to auth server):
```hcl
# Lines 314-334 - DELETE THESE:
{
  name  = "AUTH_METHOD"
  value = "keycloak"
},
{
  name  = "KEYCLOAK_ENABLED"
  value = "true"
},
{
  name  = "KEYCLOAK_URL"
  value = "http://${module.keycloak_alb.dns_name}:8080"
},
{
  name  = "KEYCLOAK_EXTERNAL_URL"
  value = var.keycloak_external_url != "" ? var.keycloak_external_url : "http://${module.keycloak_alb.dns_name}:8080"
},
{
  name  = "KEYCLOAK_REALM"
  value = var.keycloak_realm
},
{
  name  = "KEYCLOAK_CLIENT_ID"
  value = var.keycloak_client_id
},
```

#### Section E: Registry Service Secrets (Lines 348-352)

**REMOVE Keycloak secrets**:
```hcl
# Lines 348-352 - DELETE THESE:
var.keycloak_client_secret != "" ? [{
  name      = "KEYCLOAK_CLIENT_SECRET"
  valueFrom = aws_secretsmanager_secret.keycloak_client_secret[0].arn
}] : [],
```

#### Section F: Registry Service Dependency (Line 455)

**REMOVE Keycloak ALB dependency**:
```hcl
# Line 455 - CHANGE FROM:
depends_on = [module.ecs_service_auth, module.keycloak_alb]

# TO:
depends_on = [module.ecs_service_auth]
```

#### Section G: ENTIRE KEYCLOAK ECS SERVICE (Lines 458-706)

**DELETE ENTIRE SECTION** - This is the broken Keycloak service definition:
```hcl
# Lines 458-706 - DELETE ENTIRE KEYCLOAK SERVICE:
# ECS Service: Keycloak
module "ecs_service_keycloak" {
  # ... ENTIRE MODULE (248 lines!)
}
```

**CRITICAL**: This module includes:
- ECS service definition with `command = ["start-dev"]` (line 531) ← THE BUG!
- Container definitions
- Environment variables (broken KC_HOSTNAME config)
- Secrets
- Load balancer attachments
- Service discovery
- All the broken Keycloak configuration

---

### FILE 5: `terraform/aws-ecs/modules/mcp-gateway/locals.tf`

**REMOVE Lines 14-20** (Keycloak secret ARNs)

```hcl
# Lines 14-20 - DELETE THESE:
# Keycloak secret ARNs for IAM policies
keycloak_secret_arns = compact([
  aws_secretsmanager_secret.keycloak_database_url.arn,
  aws_secretsmanager_secret.keycloak_db_password.arn,
  aws_secretsmanager_secret.keycloak_admin_password.arn,
  var.keycloak_client_secret != "" ? aws_secretsmanager_secret.keycloak_client_secret[0].arn : "",
  var.keycloak_m2m_client_secret != "" ? aws_secretsmanager_secret.keycloak_m2m_client_secret[0].arn : "",
])
```

**KEEP**: Other locals (common_tags, etc.)

---

### FILE 6: `terraform/aws-ecs/modules/mcp-gateway/iam.tf`

**MODIFY Line 18** - Remove Keycloak secret ARNs from IAM policy

```hcl
# Line 18 - CHANGE FROM:
], local.keycloak_secret_arns)

# TO:
])
```

**Context**: This is in a concat() statement that merges secret ARNs. After removing `local.keycloak_secret_arns` from locals.tf, this reference must be removed.

---

### FILE 7: `terraform/aws-ecs/modules/mcp-gateway/variables.tf`

**REMOVE Lines 53-281** (All Keycloak variables)

**Detailed Variable Removal**:

```hcl
# Line 53-56 - DELETE:
variable "keycloak_image_uri" {
  description = "Container image URI for Keycloak service"
  type        = string
  default     = "mcpgateway/keycloak:latest"
}

# Line 103-111 - DELETE:
variable "keycloak_replicas" {
  description = "Number of replicas for Keycloak service"
  type        = number
  default     = 1
  validation {
    condition     = var.keycloak_replicas > 0
    error_message = "Keycloak replicas must be greater than 0."
  }
}

# Lines 120-131 - DELETE (Database capacity):
variable "keycloak_postgres_min_capacity" {
  description = "Minimum ACU capacity for Keycloak PostgreSQL Serverless v2"
  type        = number
  default     = 0.5
}

variable "keycloak_postgres_max_capacity" {
  description = "Maximum ACU capacity for Keycloak PostgreSQL Serverless v2"
  type        = number
  default     = 16
}

# Lines 132-142 - DELETE (Database config):
variable "keycloak_db_name" {
  description = "Database name for Keycloak"
  type        = string
  default     = "keycloak"
}

variable "keycloak_db_username" {
  description = "Database username for Keycloak"
  type        = string
  default     = "keycloak"
}

# Lines 144-148 - DELETE:
variable "keycloak_admin_username" {
  description = "Keycloak admin username"
  type        = string
  default     = "admin"
}

# Lines 168-172 - DELETE:
variable "keycloak_url" {
  description = "Keycloak server URL (deprecated)"
  type        = string
  default     = ""
}

# Lines 174-182 - DELETE:
variable "keycloak_alb_scheme" {
  description = "Scheme for the Keycloak ALB (internal or internet-facing)"
  type        = string
  default     = "internal"
  validation {
    condition     = contains(["internal", "internet-facing"], var.keycloak_alb_scheme)
    error_message = "keycloak_alb_scheme must be either 'internal' or 'internet-facing'"
  }
}

# Lines 184-196 - DELETE (Ingress CIDRs):
variable "keycloak_ingress_cidr" {
  description = "CIDR block allowed to access Keycloak ALB"
  type        = string
  default     = "0.0.0.0/0"
}

variable "keycloak_ingress_cidr_ec2" {
  description = "EC2 instance CIDR for Keycloak access"
  type        = string
  default     = "0.0.0.0/0"
}

# Lines 202-206 - DELETE:
variable "keycloak_certificate_arn" {
  description = "ACM certificate ARN for Keycloak HTTPS"
  type        = string
  default     = ""
}

# Lines 250-281 - DELETE (Keycloak auth config):
variable "keycloak_external_url" {
  description = "External URL for Keycloak"
  type        = string
  default     = ""
}

variable "keycloak_realm" {
  description = "Keycloak realm name"
  type        = string
  default     = "master"
}

variable "keycloak_client_id" {
  description = "Keycloak client ID"
  type        = string
  default     = "mcp-gateway-web"
}

variable "keycloak_client_secret" {
  description = "Keycloak client secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "keycloak_m2m_client_id" {
  description = "Keycloak M2M client ID"
  type        = string
  default     = "mcp-gateway-m2m"
}

variable "keycloak_m2m_client_secret" {
  description = "Keycloak M2M client secret"
  type        = string
  sensitive   = true
  default     = ""
}
```

---

### FILE 8: `terraform/aws-ecs/modules/mcp-gateway/outputs.tf`

**REMOVE Lines 4-74, 85, 132-142, 151, 161, 172, 190-197**

**Detailed Output Removal**:

```hcl
# Lines 4-22 - DELETE (Database outputs):
output "keycloak_database_endpoint" {
  description = "Keycloak database endpoint"
  value       = module.aurora_postgresql.cluster_endpoint
}

output "keycloak_database_port" {
  description = "Keycloak database port"
  value       = module.aurora_postgresql.cluster_port
}

output "keycloak_database_name" {
  description = "Keycloak database name"
  value       = module.aurora_postgresql.cluster_database_name
}

output "keycloak_database_username" {
  description = "Keycloak database username"
  value       = module.aurora_postgresql.cluster_master_username
  sensitive   = true
}

# Lines 54-74 - DELETE (ALB outputs):
output "keycloak_alb_dns_name" {
  description = "DNS name of Keycloak ALB"
  value       = module.keycloak_alb.dns_name
}

output "keycloak_alb_zone_id" {
  description = "Zone ID of Keycloak ALB"
  value       = module.keycloak_alb.zone_id
}

output "keycloak_alb_arn" {
  description = "ARN of Keycloak ALB"
  value       = module.keycloak_alb.arn
}

output "keycloak_alb_security_group_id" {
  description = "Security group ID of Keycloak ALB"
  value       = module.keycloak_alb.security_group_id
}

# Line 85 - DELETE from service_urls output:
# CHANGE FROM:
service_urls = {
  registry = "http://${module.alb.dns_name}"
  auth     = "http://${module.alb.dns_name}:8888"
  gradio   = "http://${module.alb.dns_name}:7860"
  keycloak = "http://${module.keycloak_alb.dns_name}:8080"  # ← DELETE THIS LINE
}

# TO:
service_urls = {
  registry = "http://${module.alb.dns_name}"
  auth     = "http://${module.alb.dns_name}:8888"
  gradio   = "http://${module.alb.dns_name}:7860"
}

# Lines 132-142 - DELETE from secrets_arns output:
# CHANGE FROM:
secrets_arns = merge({
  secret_key       = aws_secretsmanager_secret.secret_key.arn
  admin_password   = aws_secretsmanager_secret.admin_password.arn
  keycloak_database_url    = aws_secretsmanager_secret.keycloak_database_url.arn  # ← DELETE
  keycloak_db_password     = aws_secretsmanager_secret.keycloak_db_password.arn   # ← DELETE
  keycloak_admin_password  = aws_secretsmanager_secret.keycloak_admin_password.arn # ← DELETE
  },
  var.keycloak_client_secret != "" ? {  # ← DELETE entire conditional
    keycloak_client_secret = aws_secretsmanager_secret.keycloak_client_secret[0].arn
  } : {},
  var.keycloak_m2m_client_secret != "" ? {  # ← DELETE entire conditional
    keycloak_m2m_client_secret = aws_secretsmanager_secret.keycloak_m2m_client_secret[0].arn
  } : {}
)

# TO:
secrets_arns = {
  secret_key     = aws_secretsmanager_secret.secret_key.arn
  admin_password = aws_secretsmanager_secret.admin_password.arn
}

# Line 151 - DELETE from service_ids output:
# Remove:    keycloak = module.ecs_service_keycloak.id

# Line 161 - DELETE from service_names output:
# Remove:    keycloak = module.ecs_service_keycloak.name

# Line 172 - DELETE from service_security_group_ids output:
# Remove:    keycloak = module.ecs_service_keycloak.security_group_id

# Lines 190-197 - DELETE entire output:
output "keycloak_admin_credentials" {
  description = "Keycloak admin credentials"
  value = {
    username = var.keycloak_admin_username
    url      = "http://${module.keycloak_alb.dns_name}:8080/admin"
    password_secret_arn = aws_secretsmanager_secret.keycloak_admin_password.arn
  }
  sensitive = true
}
```

---

### FILE 9: `terraform/aws-ecs/modules/mcp-gateway/monitoring.tf`

**REMOVE Lines 62-141** (Keycloak CloudWatch alarms)

```hcl
# Lines 62-77 - DELETE:
resource "aws_cloudwatch_metric_alarm" "keycloak_cpu_high" {
  count               = var.enable_monitoring ? 1 : 0
  alarm_name          = "${local.name_prefix}-keycloak-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Keycloak CPU utilization is too high"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  dimensions = {
    ClusterName = module.ecs_cluster.cluster_name
    ServiceName = module.ecs_service_keycloak.name
  }
}

# Lines 120-135 - DELETE:
resource "aws_cloudwatch_metric_alarm" "keycloak_memory_high" {
  count               = var.enable_monitoring ? 1 : 0
  alarm_name          = "${local.name_prefix}-keycloak-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Keycloak memory utilization is too high"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  dimensions = {
    ClusterName = module.ecs_cluster.cluster_name
    ServiceName = module.ecs_service_keycloak.name
  }
}
```

---

### FILE 10: `terraform/aws-ecs/main.tf`

**REMOVE/MODIFY Lines 41, 55-61** (Keycloak variables passed to module)

```hcl
# Line 41 - DELETE:
keycloak_certificate_arn   = var.keycloak_certificate_arn

# Lines 55-61 - DELETE:
keycloak_client_secret     = var.keycloak_client_secret
keycloak_m2m_client_secret = var.keycloak_m2m_client_secret

# Keycloak ALB
keycloak_alb_scheme        = var.keycloak_alb_scheme
keycloak_ingress_cidr      = var.keycloak_ingress_cidr
keycloak_ingress_cidr_ec2  = var.keycloak_ingress_cidr_ec2
```

---

### FILE 11: `terraform/aws-ecs/variables.tf`

**REMOVE Lines 25-73** (Root-level Keycloak variables)

```hcl
# Lines 25-28 - DELETE:
variable "keycloak_certificate_arn" {
  description = "ACM certificate ARN for Keycloak HTTPS"
  type        = string
  default     = ""
}

# Lines 43-54 - DELETE:
variable "keycloak_client_secret" {
  description = "Keycloak client secret"
  type        = string
  sensitive   = true
  default     = "change-me-to-keycloak-web-client-secret"
}

variable "keycloak_m2m_client_secret" {
  description = "Keycloak M2M client secret"
  type        = string
  sensitive   = true
  default     = "change-me-to-keycloak-m2m-client-secret"
}

# Lines 57-65 - DELETE:
variable "keycloak_alb_scheme" {
  description = "Keycloak ALB scheme"
  type        = string
  default     = "internal"
  validation {
    condition     = contains(["internal", "internet-facing"], var.keycloak_alb_scheme)
    error_message = "Must be 'internal' or 'internet-facing'"
  }
}

# Lines 67-73 - DELETE:
variable "keycloak_ingress_cidr" {
  description = "CIDR for Keycloak access"
  type        = string
  default     = "0.0.0.0/0"
}

variable "keycloak_ingress_cidr_ec2" {
  description = "EC2 CIDR for Keycloak access"
  type        = string
  default     = "0.0.0.0/0"
}
```

---

### FILE 12: `terraform/aws-ecs/outputs.tf`

**REMOVE Lines 46-104** (Keycloak outputs)

```hcl
# Lines 46-49 - DELETE:
output "mcp_gateway_keycloak_url" {
  description = "URL to access Keycloak"
  value       = var.keycloak_certificate_arn != "" ? "https://${module.mcp_gateway.keycloak_alb_dns_name}/" : module.mcp_gateway.service_urls.keycloak
}

# Lines 51-54 - DELETE:
output "keycloak_alb_dns" {
  description = "Keycloak ALB DNS name"
  value       = module.mcp_gateway.keycloak_alb_dns_name
}

# Lines 93-96 - DELETE:
output "mcp_gateway_keycloak_https_url" {
  description = "HTTPS URL for Keycloak (if certificate configured)"
  value       = var.keycloak_certificate_arn != "" ? "https://${module.mcp_gateway.keycloak_alb_dns_name}/" : null
}

# Line 104 - DELETE from deployment_info output:
# Remove:    keycloak_https_enabled  = var.keycloak_certificate_arn != ""
```

---

### FILE 13: `terraform/aws-ecs/terraform.tfvars`

**REMOVE Lines 28-79** (Keycloak configuration values)

```hcl
# Lines 28-32 - DELETE:
keycloak_ingress_cidr = "71.114.44.148/32"

# Allow EC2 instance to access Keycloak
keycloak_ingress_cidr_ec2 = "44.211.62.41/32"

# Lines 40 - DELETE:
keycloak_alb_scheme = "internet-facing"

# Lines 48-54 - DELETE:
# Default: "change-me-to-keycloak-web-client-secret"
keycloak_client_secret = "change-me-to-keycloak-web-client-secret"

# Machine-to-machine client secret (used for programmatic access)
# Default: "change-me-to-keycloak-m2m-client-secret"
keycloak_m2m_client_secret = "change-me-to-keycloak-m2m-client-secret"

# Line 79 - DELETE:
keycloak_certificate_arn = "arn:aws:acm:us-east-1:605134468121:certificate/7ebf5473-2840-440c-940c-15eb3c89458e"
```

---

## ADDITIONAL CLEANUP

### Documentation Files to Remove/Update

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Delete Keycloak troubleshooting docs
rm KEYCLOAK_HTTPS_SETUP.md
rm KEYCLOAK_SPINNER_FIX.md

# Delete Keycloak scripts
rm disable-keycloak-strict-hostname.sh
rm fix-keycloak-client.sh
rm get-keycloak-password.sh
rm init-keycloak-https.sh
rm kcadm-fix-commands.sh
rm init-keycloak-https-run2.log

# Clean up .admin_password (Keycloak admin password file)
rm .admin_password
```

### Terraform State Cleanup

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# BEFORE applying the removal, backup state
cp terraform.tfstate terraform.tfstate.backup-before-keycloak-removal

# After removal, remove Keycloak resources from state
terraform state rm 'module.mcp_gateway.module.aurora_postgresql'
terraform state rm 'module.mcp_gateway.module.ecs_service_keycloak'
terraform state rm 'module.mcp_gateway.module.keycloak_alb'
terraform state rm 'module.mcp_gateway.random_password.keycloak_postgres_password'
terraform state rm 'module.mcp_gateway.random_password.keycloak_admin_password'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret.keycloak_database_url'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret_version.keycloak_database_url'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret.keycloak_db_password'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret_version.keycloak_db_password'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret.keycloak_admin_password'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret_version.keycloak_admin_password'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret.keycloak_client_secret[0]'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret_version.keycloak_client_secret[0]'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret.keycloak_m2m_client_secret[0]'
terraform state rm 'module.mcp_gateway.aws_secretsmanager_secret_version.keycloak_m2m_client_secret[0]'
terraform state rm 'module.mcp_gateway.aws_lb_listener.keycloak_https[0]'
terraform state rm 'module.mcp_gateway.aws_lb_listener.keycloak_http_redirect[0]'
terraform state rm 'module.mcp_gateway.aws_cloudwatch_metric_alarm.keycloak_cpu_high[0]'
terraform state rm 'module.mcp_gateway.aws_cloudwatch_metric_alarm.keycloak_memory_high[0]'
```

---

## VERIFICATION CHECKLIST

After completing all removals, verify with these commands:

### 1. Grep for Any Remaining References
```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Check .tf files (should return ZERO results)
grep -r "keycloak" --include="*.tf" -i | grep -v ".terraform"

# Check .tfvars files (should return ZERO results)
grep -r "keycloak" --include="*.tfvars" -i

# Check for KC_ environment variables (should return ZERO results)
grep -r "KC_" --include="*.tf" -i | grep -v ".terraform"
```

**Expected Output**: NOTHING (empty results)

### 2. Validate Terraform Syntax
```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs
terraform init
terraform validate
```

**Expected Output**: "Success! The configuration is valid."

### 3. Terraform Plan (Should Show Destruction Only)
```bash
terraform plan
```

**Expected Changes**:
- Destroy: ~15-20 resources (all Keycloak-related)
- Add: 0 resources
- Change: 0 resources

### 4. File Count Check
```bash
# Count Terraform files
find . -maxdepth 1 -name "*.tf" -type f | wc -l

# Should be 5 files: main.tf, vpc.tf, variables.tf, outputs.tf, ecs.tf
```

### 5. Module File Count
```bash
# Count module files
ls -1 modules/mcp-gateway/*.tf | wc -l

# Should be 7 files (after removing database.tf):
# - ecs-services.tf
# - locals.tf
# - networking.tf
# - outputs.tf
# - secrets.tf
# - variables.tf
# - iam.tf
# - monitoring.tf
```

---

## DESTRUCTION OF AWS RESOURCES

**CRITICAL**: Before adding new Keycloak, destroy old Keycloak resources:

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Target destroy specific resources
terraform destroy \
  -target='module.mcp_gateway.module.aurora_postgresql' \
  -target='module.mcp_gateway.module.ecs_service_keycloak' \
  -target='module.mcp_gateway.module.keycloak_alb'

# Verify they're gone
aws ecs describe-services \
  --cluster mcp-gateway-dev \
  --services mcp-gateway-dev-keycloak \
  --region us-east-1 2>&1 | grep "ServiceNotFoundException"
# Expected: ServiceNotFoundException

aws rds describe-db-clusters \
  --db-cluster-identifier mcp-gateway-dev-postgres \
  --region us-east-1 2>&1 | grep "DBClusterNotFoundFault"
# Expected: DBClusterNotFoundFault
```

---

## SUMMARY

### Files to DELETE Entirely:
1. ✅ `modules/mcp-gateway/database.tf` (61 lines)

### Files to MODIFY (Remove Keycloak sections):
2. ✅ `modules/mcp-gateway/secrets.tf` (Remove lines 19-120)
3. ✅ `modules/mcp-gateway/networking.tf` (Remove lines 163-289)
4. ✅ `modules/mcp-gateway/ecs-services.tf` (Remove lines 97-121, 131-137, 199, 314-334, 348-352, 455, 458-706)
5. ✅ `modules/mcp-gateway/locals.tf` (Remove lines 14-20)
6. ✅ `modules/mcp-gateway/iam.tf` (Modify line 18)
7. ✅ `modules/mcp-gateway/variables.tf` (Remove lines 53-281)
8. ✅ `modules/mcp-gateway/outputs.tf` (Remove lines 4-74, 85, 132-142, 151, 161, 172, 190-197)
9. ✅ `modules/mcp-gateway/monitoring.tf` (Remove lines 62-141)
10. ✅ `main.tf` (Remove lines 41, 55-61)
11. ✅ `variables.tf` (Remove lines 25-73)
12. ✅ `outputs.tf` (Remove lines 46-104)
13. ✅ `terraform.tfvars` (Remove lines 28-79)

### Documentation/Scripts to DELETE:
- ✅ `KEYCLOAK_HTTPS_SETUP.md`
- ✅ `KEYCLOAK_SPINNER_FIX.md`
- ✅ `disable-keycloak-strict-hostname.sh`
- ✅ `fix-keycloak-client.sh`
- ✅ `get-keycloak-password.sh`
- ✅ `init-keycloak-https.sh`
- ✅ `kcadm-fix-commands.sh`
- ✅ `init-keycloak-https-run2.log`
- ✅ `.admin_password`

### Total Lines Removed: ~800+ lines of broken Keycloak code

---

## POST-REMOVAL STATE

After completing this checklist:
- ✅ ZERO Keycloak references in Terraform code
- ✅ Auth server and registry will have NO Keycloak environment variables
- ✅ No Keycloak database, ECS service, or load balancer
- ✅ Clean slate for adding working Keycloak implementation
- ✅ No resource naming conflicts
- ✅ No variable conflicts
- ✅ No Terraform state issues

**Job Security Status**: ✅ MAXIMUM - You did it right!

---

## FINAL SIGN-OFF

Before proceeding to add working Keycloak:

- [ ] All 284 Keycloak references removed
- [ ] Grep returns ZERO results
- [ ] Terraform validate passes
- [ ] Terraform plan shows only destructions
- [ ] AWS resources destroyed
- [ ] Git commit created with removal
- [ ] Backup branch created

**Sign-off**: ___________________________
**Date**: ___________________________

**Ready to add working Keycloak**: YES / NO
