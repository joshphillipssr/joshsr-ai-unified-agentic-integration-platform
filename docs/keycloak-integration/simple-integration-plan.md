# Simple Keycloak Integration Plan for mcp-gateway-registry

## 🚨 CRITICAL: READ THIS ENTIRE SECTION BEFORE STARTING 🚨

**For Junior Engineers**: This is a **complete, step-by-step guide**. Follow it **exactly in order**. Do NOT skip steps. Do NOT improvise. Your job depends on following these instructions precisely.

**What This Guide Does**:
1. ✅ **PHASE 0**: Remove ALL broken Keycloak code (CRITICAL FIRST STEP)
2. ✅ **PHASE 1-6**: Add working Keycloak integrated with existing infrastructure
3. ✅ **Verification**: Test everything works

**Time Required**: 6-8 hours total
**Difficulty**: Medium (if you follow instructions exactly)
**Risk**: Low (if you don't skip steps)

---

## The Expert DevOps Take

**Situation**:
- mcp-gateway-registry has broken Keycloak (using `start-dev`, infinite spinner, CORS issues)
- We have a working Keycloak implementation
- Auth server needs to talk to Keycloak
- Everything is in testing - NO PRODUCTION DEPLOYMENTS

**Goal**:
Replace broken Keycloak with working one, sharing infrastructure (VPC, networking) for simplicity and maintainability.

**Anti-Pattern to Avoid**:
❌ Separate VPCs requiring VPC peering, transit gateways, cross-VPC security groups = COMPLEXITY HELL

**The Right Way**:
✅ Shared VPC, integrated services, simple security group rules, one Terraform workspace

---

## Architecture Decision: Shared Infrastructure

```
┌─────────────────────────────────────────────────────────────┐
│                    Shared VPC (mcp-gateway)                  │
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐  │
│  │  Auth Server │─────▶│   Keycloak   │◀─────│  ALB      │  │
│  │  (ECS Task)  │      │  (ECS Task)  │      │  (Public) │  │
│  └──────────────┘      └──────────────┘      └───────────┘  │
│         │                      │                              │
│         │                      │                              │
│         ▼                      ▼                              │
│  ┌──────────────────────────────────────┐                    │
│  │   Aurora MySQL (Keycloak DB)         │                    │
│  │   RDS Proxy for connection pooling   │                    │
│  └──────────────────────────────────────┘                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Why This Works**:
- ✅ All services in same VPC = simple security group rules
- ✅ No VPC peering, no transit gateway, no cross-VPC complexity
- ✅ Lower costs (one NAT gateway, one VPC)
- ✅ Easier troubleshooting (everything in one network)
- ✅ Auth server → Keycloak = simple internal communication

---

## 📋 COMPLETE IMPLEMENTATION CHECKLIST

Use this to track your progress:

- [ ] **PHASE 0**: Remove all broken Keycloak code (2-3 hours)
- [ ] **PHASE 0 VERIFICATION**: Confirm zero Keycloak remnants
- [ ] **PHASE 1**: Backup and branch setup (15 min)
- [ ] **PHASE 2**: Copy Dockerfile (15 min)
- [ ] **PHASE 3**: Add Terraform files (2-3 hours)
- [ ] **PHASE 4**: Build Docker image (30 min)
- [ ] **PHASE 5**: Deploy with Terraform (1 hour)
- [ ] **PHASE 6**: Post-deployment verification (30 min)
- [ ] **FINAL VERIFICATION**: Full system test

**Total Time**: 6-8 hours

---

## Step-by-Step Implementation Plan

### ⚠️ PHASE 0: REMOVE ALL BROKEN KEYCLOAK CODE (CRITICAL - DO THIS FIRST!)

**⏱️ Time**: 2-3 hours
**❗ IMPORTANCE**: CRITICAL - Skipping this will cause massive conflicts and deployment failures

**Why This Step is First**:
The mcp-gateway-registry has **284 references to broken Keycloak code** across 13 files. If you try to add our working Keycloak without removing the old one first, you will get:
- ❌ Resource naming conflicts (AWS won't allow duplicate resource names)
- ❌ Variable conflicts (Terraform will error on duplicate variables)
- ❌ Runtime errors (environment variables will conflict)
- ❌ Complete deployment failure

**📄 Required Document**: `keycloak-removal-checklist.md` (in same directory as this file)

#### Step 0.1: Read the Removal Checklist

```bash
# Open and READ the entire removal checklist
cat .scratchpad/keycloak-removal-checklist.md

# OR open in your editor
code .scratchpad/keycloak-removal-checklist.md
```

**What you'll find**:
- Exact line numbers for every change
- Before/after code snippets
- 13 files to modify
- 1 file to delete completely
- 8 documentation files to remove

#### Step 0.2: Create Backup Branch

```bash
cd ~/repos/mcp-gateway-registry

# Create backup of current broken state
git checkout -b backup-broken-keycloak-$(date +%Y%m%d-%H%M%S)
git add -A
git commit -m "Backup: Broken Keycloak implementation before removal"
git push origin backup-broken-keycloak-$(date +%Y%m%d-%H%M%S)

# Create working branch
git checkout main
git pull origin main
git checkout -b feature/remove-broken-keycloak
```

#### Step 0.3: Remove Broken Keycloak Code

**Follow the removal checklist EXACTLY**. It tells you:
- Which files to delete entirely
- Which lines to remove from each file
- How to verify each step

**Key files to modify** (see checklist for exact line numbers):
1. ✅ `terraform/aws-ecs/modules/mcp-gateway/database.tf` - **DELETE ENTIRE FILE**
2. ✅ `terraform/aws-ecs/modules/mcp-gateway/secrets.tf` - Remove lines 19-120
3. ✅ `terraform/aws-ecs/modules/mcp-gateway/networking.tf` - Remove lines 163-289
4. ✅ `terraform/aws-ecs/modules/mcp-gateway/ecs-services.tf` - Remove multiple sections (see checklist!)
5. ✅ `terraform/aws-ecs/modules/mcp-gateway/locals.tf` - Remove lines 14-20
6. ✅ `terraform/aws-ecs/modules/mcp-gateway/iam.tf` - Modify line 18
7. ✅ `terraform/aws-ecs/modules/mcp-gateway/variables.tf` - Remove lines 53-281
8. ✅ `terraform/aws-ecs/modules/mcp-gateway/outputs.tf` - Remove multiple sections
9. ✅ `terraform/aws-ecs/modules/mcp-gateway/monitoring.tf` - Remove lines 62-141
10. ✅ `terraform/aws-ecs/main.tf` - Remove lines 41, 55-61
11. ✅ `terraform/aws-ecs/variables.tf` - Remove lines 25-73
12. ✅ `terraform/aws-ecs/outputs.tf` - Remove lines 46-104
13. ✅ `terraform/aws-ecs/terraform.tfvars` - Remove lines 28-79

**Delete documentation files**:
```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

rm -f KEYCLOAK_HTTPS_SETUP.md
rm -f KEYCLOAK_SPINNER_FIX.md
rm -f disable-keycloak-strict-hostname.sh
rm -f fix-keycloak-client.sh
rm -f get-keycloak-password.sh
rm -f init-keycloak-https.sh
rm -f kcadm-fix-commands.sh
rm -f init-keycloak-https-run2.log
rm -f .admin_password
```

#### Step 0.4: CRITICAL VERIFICATION (DO NOT SKIP!)

After removing all Keycloak code, verify complete removal:

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Test 1: Search for any remaining Keycloak references
# EXPECTED RESULT: ZERO results (empty output)
grep -r "keycloak" --include="*.tf" --include="*.tfvars" -i | grep -v ".terraform"

# Test 2: Validate Terraform syntax
# EXPECTED RESULT: "Success! The configuration is valid."
terraform init
terraform validate

# Test 3: Check Terraform plan
# EXPECTED RESULT: Plan shows ONLY destructions, no adds or changes
terraform plan

# Test 4: Verify file was deleted
# EXPECTED RESULT: "No such file or directory"
ls modules/mcp-gateway/database.tf
```

**🚨 STOP! Do not proceed unless ALL tests pass:**
- ✅ Test 1: Zero "keycloak" references found
- ✅ Test 2: Terraform validate succeeds
- ✅ Test 3: Plan shows only destructions
- ✅ Test 4: database.tf is deleted

#### Step 0.5: Destroy Old Keycloak Resources in AWS

**⚠️ WARNING**: This will destroy the broken Keycloak infrastructure in AWS.

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Destroy Keycloak resources
terraform destroy \
  -target='module.mcp_gateway.module.aurora_postgresql' \
  -target='module.mcp_gateway.module.ecs_service_keycloak' \
  -target='module.mcp_gateway.module.keycloak_alb'

# Type "yes" when prompted

# Verify they're gone
aws ecs describe-services \
  --cluster mcp-gateway-dev \
  --services mcp-gateway-dev-keycloak \
  --region us-east-1 2>&1 | grep "ServiceNotFoundException"
# EXPECTED: Should see "ServiceNotFoundException"
```

#### Step 0.6: Commit the Removal

```bash
cd ~/repos/mcp-gateway-registry

git add -A
git commit -m "Remove broken Keycloak implementation

- Deleted database.tf (PostgreSQL only for Keycloak)
- Removed all Keycloak secrets (database, admin, client)
- Removed Keycloak ALB and listeners
- Removed Keycloak ECS service (was using start-dev mode)
- Removed all Keycloak variables and outputs
- Removed Keycloak CloudWatch alarms
- Deleted Keycloak documentation and scripts
- Total: 284 references removed across 13 files

Ref: keycloak-removal-checklist.md for full details"

git push origin feature/remove-broken-keycloak
```

#### ✅ PHASE 0 COMPLETE - Verification Checklist

Before proceeding to Phase 1, confirm:

- [ ] All 13 files modified per removal checklist
- [ ] database.tf deleted
- [ ] 8 documentation files deleted
- [ ] `grep -r "keycloak"` returns ZERO results
- [ ] `terraform validate` succeeds
- [ ] `terraform plan` shows only destructions
- [ ] AWS resources destroyed
- [ ] Changes committed to Git

**🚨 IF ANY CHECKBOX IS UNCHECKED, GO BACK AND FIX IT BEFORE PROCEEDING! 🚨**

---

### Phase 1: Backup and Branch Setup (15 min)

**✅ PREREQUISITE**: Phase 0 MUST be complete and verified

```bash
cd ~/repos/mcp-gateway-registry

# 1. Find their VPC setup
find . -name "vpc.tf" -o -name "network.tf" -o -name "*vpc*"

# 2. Find their ECS setup
find . -name "ecs*.tf" -o -name "*ecs*"

# 3. Find their broken Keycloak
find . -name "*keycloak*"

# 4. Understand their security groups
grep -r "aws_security_group" --include="*.tf"
```

**Questions to Answer**:
- Where is their VPC defined? → We'll USE IT
- Where is their ECS cluster? → We'll ADD Keycloak service to it
- Where is their broken Keycloak? → We'll REPLACE IT
- How are security groups organized? → We'll ADD Keycloak rules

---

### Phase 2: Remove Broken Keycloak (15 min)

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Find all Keycloak-related files
grep -r "keycloak" --include="*.tf" -l

# Common files to check/remove:
# - ecs-services.tf (line 531: command = ["start-dev"])
# - variables.tf (Keycloak variables)
# - Any keycloak-specific .tf files
```

**Action**:
1. Create a backup branch: `git checkout -b backup-broken-keycloak`
2. Commit current state
3. Create new branch: `git checkout -b feature/working-keycloak`
4. Remove/comment out broken Keycloak resources

---

### Phase 3: Add Working Keycloak Components (2-3 hours)

#### 3.1: Add Keycloak Database (database.tf or keycloak-database.tf)

```hcl
# terraform/aws-ecs/keycloak-database.tf

#
# Aurora MySQL Database for Keycloak
# Uses existing VPC and security groups from mcp-gateway
#
module "keycloak_database" {
  source = "github.com/cds-snc/terraform-modules//rds?ref=v9.1.0"
  name   = "keycloak-${var.environment}"

  database_name  = "keycloak"
  engine         = "aurora-mysql"
  engine_version = "8.0.mysql_aurora.3.11.0"
  instances      = 2
  instance_class = "db.serverless"
  username       = var.keycloak_database_username
  password       = var.keycloak_database_password

  serverless_min_capacity = var.keycloak_database_min_acu
  serverless_max_capacity = var.keycloak_database_max_acu

  backup_retention_period      = 7
  preferred_backup_window      = "02:00-04:00"
  performance_insights_enabled = false

  # USE EXISTING VPC (key integration point!)
  vpc_id             = module.vpc.vpc_id              # ← Their existing VPC
  subnet_ids         = module.vpc.private_subnet_ids  # ← Their existing subnets
  security_group_ids = [aws_security_group.keycloak_db.id]

  billing_tag_value = var.billing_tag_value
}

# SSM Parameters for Keycloak database connection
resource "aws_ssm_parameter" "keycloak_database_url" {
  name  = "/keycloak/${var.environment}/database_url"
  type  = "SecureString"
  value = "jdbc:mysql://${module.keycloak_database.proxy_endpoint}:3306/keycloak"
  tags  = local.common_tags
}

resource "aws_ssm_parameter" "keycloak_database_username" {
  name  = "/keycloak/${var.environment}/database_username"
  type  = "SecureString"
  value = var.keycloak_database_username
  tags  = local.common_tags
}

resource "aws_ssm_parameter" "keycloak_database_password" {
  name  = "/keycloak/${var.environment}/database_password"
  type  = "SecureString"
  value = var.keycloak_database_password
  tags  = local.common_tags
}
```

#### 3.2: Add Keycloak ECS Service (keycloak-ecs.tf)

```hcl
# terraform/aws-ecs/keycloak-ecs.tf

locals {
  keycloak_container_env = [
    {
      "name"  = "AWS_REGION",
      "value" = var.aws_region
    },
    {
      "name"  = "KC_PROXY",
      "value" = "edge"
    },
    {
      "name"  = "KC_HOSTNAME_STRICT",
      "value" = "false"
    },
    {
      "name"  = "KC_HOSTNAME",
      "value" = var.keycloak_domain
    },
    {
      "name"  = "KC_HEALTH_ENABLED",
      "value" = "true"
    },
    {
      "name"  = "KEYCLOAK_LOGLEVEL",
      "value" = var.keycloak_log_level
    },
    {
      "name"  = "PROXY_ADDRESS_FORWARDING",
      "value" = "true"
    }
  ]

  keycloak_container_secrets = [
    {
      "name"      = "KEYCLOAK_ADMIN"
      "valueFrom" = aws_ssm_parameter.keycloak_admin.arn
    },
    {
      "name"      = "KEYCLOAK_ADMIN_PASSWORD"
      "valueFrom" = aws_ssm_parameter.keycloak_admin_password.arn
    },
    {
      "name"      = "KC_DB_URL"
      "valueFrom" = aws_ssm_parameter.keycloak_database_url.arn
    },
    {
      "name"      = "KC_DB_USERNAME"
      "valueFrom" = aws_ssm_parameter.keycloak_database_username.arn
    },
    {
      "name"      = "KC_DB_PASSWORD"
      "valueFrom" = aws_ssm_parameter.keycloak_database_password.arn
    },
  ]
}

module "keycloak_ecs" {
  source = "github.com/cds-snc/terraform-modules//ecs?ref=v9.1.0"

  # Use EXISTING ECS cluster or create dedicated one
  cluster_name = "keycloak-${var.environment}"
  service_name = "keycloak"
  task_cpu     = 1024
  task_memory  = 2048

  enable_execute_command = true

  # Scaling
  enable_autoscaling       = true
  desired_count            = 1
  autoscaling_min_capacity = 1
  autoscaling_max_capacity = 2

  # Task definition - PRODUCTION MODE, NOT start-dev!
  container_image                     = "${aws_ecr_repository.keycloak.repository_url}:latest"
  container_host_port                 = 8080
  container_port                      = 8080
  container_environment               = local.keycloak_container_env
  container_secrets                   = local.keycloak_container_secrets
  container_read_only_root_filesystem = false

  task_exec_role_policy_documents = [
    data.aws_iam_policy_document.keycloak_task_ssm_parameters.json
  ]
  task_role_policy_documents = [
    data.aws_iam_policy_document.keycloak_task_create_tunnel.json
  ]

  # USE EXISTING VPC AND NETWORKING
  lb_target_group_arn = aws_lb_target_group.keycloak.arn
  subnet_ids          = module.vpc.private_subnet_ids  # ← Their existing subnets
  security_group_ids  = [aws_security_group.keycloak_ecs.id]

  billing_tag_value = var.billing_tag_value
}

# IAM policies for ECS task
data "aws_iam_policy_document" "keycloak_task_ssm_parameters" {
  statement {
    sid    = "GetSSMParameters"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      aws_ssm_parameter.keycloak_admin.arn,
      aws_ssm_parameter.keycloak_admin_password.arn,
      aws_ssm_parameter.keycloak_database_url.arn,
      aws_ssm_parameter.keycloak_database_username.arn,
      aws_ssm_parameter.keycloak_database_password.arn,
    ]
  }
}

data "aws_iam_policy_document" "keycloak_task_create_tunnel" {
  statement {
    sid    = "CreateSSMTunnel"
    effect = "Allow"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel"
    ]
    resources = ["*"]
  }
}

# SSM Parameters for Keycloak admin credentials
resource "aws_ssm_parameter" "keycloak_admin" {
  name  = "/keycloak/${var.environment}/admin_username"
  type  = "SecureString"
  value = var.keycloak_admin
  tags  = local.common_tags
}

resource "aws_ssm_parameter" "keycloak_admin_password" {
  name  = "/keycloak/${var.environment}/admin_password"
  type  = "SecureString"
  value = var.keycloak_admin_password
  tags  = local.common_tags
}
```

#### 3.3: Add Security Groups (keycloak-security-groups.tf)

```hcl
# terraform/aws-ecs/keycloak-security-groups.tf

#
# Security groups for Keycloak
# Integrated with existing VPC security groups
#

# Keycloak ECS Task
resource "aws_security_group" "keycloak_ecs" {
  name        = "keycloak-ecs-${var.environment}"
  description = "Security group for Keycloak ECS tasks"
  vpc_id      = module.vpc.vpc_id
  tags        = local.common_tags
}

# Ingress from ALB to Keycloak
resource "aws_security_group_rule" "keycloak_ecs_ingress_lb" {
  description              = "Ingress from load balancer to Keycloak ECS task"
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = aws_security_group.keycloak_ecs.id
  source_security_group_id = aws_security_group.keycloak_lb.id
}

# CRITICAL: Ingress from Auth Server to Keycloak
resource "aws_security_group_rule" "keycloak_ecs_ingress_auth_server" {
  description              = "Allow auth server to communicate with Keycloak"
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = aws_security_group.keycloak_ecs.id
  source_security_group_id = aws_security_group.auth_server.id  # ← Their existing auth server SG
}

# Egress to database
resource "aws_security_group_rule" "keycloak_ecs_egress_db" {
  description              = "Egress from Keycloak ECS task to database"
  type                     = "egress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  security_group_id        = aws_security_group.keycloak_ecs.id
  source_security_group_id = aws_security_group.keycloak_db.id
}

# Egress to internet (for external integrations)
resource "aws_security_group_rule" "keycloak_ecs_egress_internet" {
  description       = "Egress from Keycloak ECS task to internet (HTTPS)"
  type              = "egress"
  to_port           = 443
  from_port         = 443
  protocol          = "tcp"
  security_group_id = aws_security_group.keycloak_ecs.id
  cidr_blocks       = ["0.0.0.0/0"]
}

# Keycloak Database
resource "aws_security_group" "keycloak_db" {
  name        = "keycloak-db-${var.environment}"
  description = "Security group for Keycloak database"
  vpc_id      = module.vpc.vpc_id
  tags        = local.common_tags
}

resource "aws_security_group_rule" "keycloak_db_ingress_ecs" {
  description              = "Ingress to database from Keycloak ECS task"
  type                     = "ingress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  security_group_id        = aws_security_group.keycloak_db.id
  source_security_group_id = aws_security_group.keycloak_ecs.id
}

# Keycloak Load Balancer
resource "aws_security_group" "keycloak_lb" {
  name        = "keycloak-lb-${var.environment}"
  description = "Security group for Keycloak load balancer"
  vpc_id      = module.vpc.vpc_id
  tags        = local.common_tags
}

resource "aws_security_group_rule" "keycloak_lb_ingress_internet_http" {
  description       = "Ingress from internet to load balancer (HTTP)"
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  security_group_id = aws_security_group.keycloak_lb.id
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "keycloak_lb_ingress_internet_https" {
  description       = "Ingress from internet to load balancer (HTTPS)"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  security_group_id = aws_security_group.keycloak_lb.id
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "keycloak_lb_egress_ecs" {
  description              = "Egress from load balancer to Keycloak ECS task"
  type                     = "egress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = aws_security_group.keycloak_lb.id
  source_security_group_id = aws_security_group.keycloak_ecs.id
}
```

#### 3.4: Add Load Balancer (keycloak-alb.tf)

```hcl
# terraform/aws-ecs/keycloak-alb.tf

resource "aws_lb" "keycloak" {
  name               = "keycloak-${var.environment}"
  internal           = false
  load_balancer_type = "application"

  drop_invalid_header_fields = true
  enable_deletion_protection = var.environment == "production" ? true : false

  security_groups = [aws_security_group.keycloak_lb.id]
  subnets         = module.vpc.public_subnet_ids  # ← Their existing public subnets

  tags = local.common_tags
}

resource "random_string" "keycloak_alb_tg_suffix" {
  length  = 3
  special = false
  upper   = false
}

resource "aws_lb_target_group" "keycloak" {
  name                 = "keycloak-tg-${random_string.keycloak_alb_tg_suffix.result}"
  port                 = 8080
  protocol             = "HTTP"
  target_type          = "ip"
  deregistration_delay = 30
  vpc_id               = module.vpc.vpc_id

  health_check {
    enabled  = true
    protocol = "HTTP"
    path     = "/health"
    matcher  = "200"
  }

  stickiness {
    type = "lb_cookie"
  }

  tags = local.common_tags

  lifecycle {
    create_before_destroy = true
    ignore_changes = [
      stickiness[0].cookie_name
    ]
  }
}

resource "aws_lb_listener" "keycloak_https" {
  load_balancer_arn = aws_lb.keycloak.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.keycloak.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.keycloak.arn
  }

  tags = local.common_tags
}

resource "aws_lb_listener" "keycloak_http_redirect" {
  load_balancer_arn = aws_lb.keycloak.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = local.common_tags
}
```

#### 3.5: Add Certificate & DNS (keycloak-dns.tf)

```hcl
# terraform/aws-ecs/keycloak-dns.tf

# Route53 zone (or use existing)
data "aws_route53_zone" "root" {
  name         = var.root_domain
  private_zone = false
}

# Subdomain zone for Keycloak
resource "aws_route53_zone" "keycloak" {
  name = var.keycloak_domain

  tags = local.common_tags
}

# NS records in parent zone
resource "aws_route53_record" "keycloak_ns" {
  zone_id = data.aws_route53_zone.root.zone_id
  name    = var.keycloak_domain
  type    = "NS"
  ttl     = 300
  records = aws_route53_zone.keycloak.name_servers
}

# A record pointing to ALB
resource "aws_route53_record" "keycloak" {
  zone_id = aws_route53_zone.keycloak.zone_id
  name    = var.keycloak_domain
  type    = "A"

  alias {
    name                   = aws_lb.keycloak.dns_name
    zone_id                = aws_lb.keycloak.zone_id
    evaluate_target_health = true
  }
}

# ACM Certificate
resource "aws_acm_certificate" "keycloak" {
  domain_name       = var.keycloak_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = local.common_tags
}

# Certificate validation
resource "aws_route53_record" "keycloak_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.keycloak.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.keycloak.zone_id
}

resource "aws_acm_certificate_validation" "keycloak" {
  certificate_arn         = aws_acm_certificate.keycloak.arn
  validation_record_fqdns = [for record in aws_route53_record.keycloak_cert_validation : record.fqdn]
}
```

#### 3.6: Add ECR Repository (keycloak-ecr.tf)

```hcl
# terraform/aws-ecs/keycloak-ecr.tf

resource "aws_ecr_repository" "keycloak" {
  name                 = "keycloak"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_lifecycle_policy" "keycloak" {
  repository = aws_ecr_repository.keycloak.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus     = "any"
        countType     = "imageCountMoreThan"
        countNumber   = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}
```

#### 3.7: Add Variables (variables.tf)

```hcl
# terraform/aws-ecs/variables.tf
# Add these to existing variables file

variable "keycloak_domain" {
  description = "Full domain for Keycloak (e.g., kc.mycorp.click)"
  type        = string
}

variable "root_domain" {
  description = "Root domain with Route53 hosted zone (e.g., mycorp.click)"
  type        = string
}

variable "keycloak_admin" {
  description = "Keycloak admin username"
  type        = string
  sensitive   = true
  default     = "admin"
}

variable "keycloak_admin_password" {
  description = "Keycloak admin password"
  type        = string
  sensitive   = true
}

variable "keycloak_database_username" {
  description = "Keycloak database username"
  type        = string
  sensitive   = true
  default     = "keycloak"
}

variable "keycloak_database_password" {
  description = "Keycloak database password"
  type        = string
  sensitive   = true
}

variable "keycloak_database_min_acu" {
  description = "Minimum Aurora Capacity Units"
  type        = number
  default     = 0.5
}

variable "keycloak_database_max_acu" {
  description = "Maximum Aurora Capacity Units"
  type        = number
  default     = 2
}

variable "keycloak_log_level" {
  description = "Keycloak log level"
  type        = string
  default     = "INFO"
}
```

#### 3.8: Add Outputs (outputs.tf)

```hcl
# terraform/aws-ecs/outputs.tf
# Add these to existing outputs file

output "keycloak_url" {
  description = "Keycloak URL"
  value       = "https://${var.keycloak_domain}"
}

output "keycloak_admin_console" {
  description = "Keycloak admin console URL"
  value       = "https://${var.keycloak_domain}/admin"
}

output "keycloak_database_endpoint" {
  description = "Keycloak database endpoint"
  value       = module.keycloak_database.proxy_endpoint
  sensitive   = true
}

output "keycloak_ecr_repository" {
  description = "Keycloak ECR repository URL"
  value       = aws_ecr_repository.keycloak.repository_url
}
```

**✅ PHASE 3 COMPLETE - Verification Checklist**:

Before proceeding, verify all files were added:

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Check all new files exist
ls -1 keycloak-*.tf
# EXPECTED OUTPUT:
# keycloak-alb.tf
# keycloak-database.tf
# keycloak-dns.tf
# keycloak-ecr.tf
# keycloak-ecs.tf
# keycloak-security-groups.tf

# Verify they reference existing VPC (NOT creating new one)
grep "module.vpc.vpc_id" keycloak-*.tf
# EXPECTED: Should see multiple references to module.vpc.vpc_id

# Count lines added
wc -l keycloak-*.tf
# EXPECTED: ~800-1000 lines total
```

**Commit all Keycloak files**:
```bash
git add keycloak-*.tf
git commit -m "Add working Keycloak Terraform infrastructure

Added files:
- keycloak-database.tf: Aurora MySQL Serverless v2 + RDS Proxy
- keycloak-ecs.tf: ECS service with production mode (start --optimized)
- keycloak-security-groups.tf: Security groups with auth server integration
- keycloak-alb.tf: Application Load Balancer with HTTPS
- keycloak-dns.tf: Route53 zone and ACM certificate
- keycloak-ecr.tf: ECR repository for Docker images

Key integrations:
- Uses EXISTING VPC (module.vpc.vpc_id)
- Allows auth server to communicate with Keycloak
- Auto-validated SSL certificate
- Production-ready configuration"
```

---

### Phase 4: Build and Push Docker Image (30 min)

```bash
# 1. Copy Dockerfile
mkdir -p ~/repos/mcp-gateway-registry/docker/keycloak
cp ~/repos/aws-ecs-keycloak/docker/Dockerfile ~/repos/mcp-gateway-registry/docker/keycloak/

# 2. Build image
cd ~/repos/mcp-gateway-registry
docker build -t keycloak:latest -f docker/keycloak/Dockerfile docker/keycloak/

# 3. Get ECR repository URL (after terraform apply creates it)
ECR_REPO=$(terraform -chdir=terraform/aws-ecs output -raw keycloak_ecr_repository)

# 4. Login to ECR
aws ecr get-login-password --region us-west-2 | \
    docker login --username AWS --password-stdin $ECR_REPO

# 5. Tag and push
docker tag keycloak:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
```

**Pro Tip**: Create a Makefile for this:

```makefile
# Makefile
.PHONY: build-keycloak push-keycloak deploy-keycloak

REGION ?= us-west-2
ECR_REPO = $(shell terraform -chdir=terraform/aws-ecs output -raw keycloak_ecr_repository 2>/dev/null)

build-keycloak:
	docker build -t keycloak:latest -f docker/keycloak/Dockerfile docker/keycloak/

push-keycloak: build-keycloak
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(ECR_REPO)
	docker tag keycloak:latest $(ECR_REPO):latest
	docker push $(ECR_REPO):latest

deploy-keycloak: push-keycloak
	aws ecs update-service --cluster keycloak-$(ENV) --service keycloak --force-new-deployment
```

**✅ PHASE 4 COMPLETE - Verification**:

```bash
# Verify image was pushed
aws ecr describe-images \
  --repository-name keycloak \
  --region us-west-2 \
  --query 'imageDetails[0].imageTags'
# EXPECTED: ["latest"]

# Verify image size (should be ~500-700MB)
aws ecr describe-images \
  --repository-name keycloak \
  --region us-west-2 \
  --query 'imageDetails[0].imageSizeInBytes'
```

---

### Phase 5: Deploy with Terraform (1 hour)

#### Step 5.1: Check Existing terraform.tfvars

**⚠️ CRITICAL: Do NOT overwrite existing terraform.tfvars!**

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Check if terraform.tfvars exists
ls -la terraform.tfvars

# View current contents (they have registry, auth server config here!)
cat terraform.tfvars
```

**You should see existing configuration** like:
- environment
- aws_region
- vpc_cidr
- ingress_cidr_blocks
- alb_scheme
- etc.

**❌ DO NOT OVERWRITE THIS FILE!**

#### Step 5.2: Add Keycloak Variables to terraform.tfvars

**APPEND** the Keycloak variables to the existing file:

```bash
# Backup first (safety!)
cp terraform.tfvars terraform.tfvars.backup

# Open in editor to ADD Keycloak variables
nano terraform.tfvars
# OR
code terraform.tfvars
```

**Add these lines to the END of the file**:

```hcl
# ==========================================
# Keycloak Configuration (Added for working Keycloak)
# ==========================================

# Keycloak domain configuration
keycloak_domain = "kc.mycorp.click"      # Change to your domain
root_domain     = "mycorp.click"          # Change to your root domain

# Keycloak admin credentials
keycloak_admin          = "admin"
keycloak_admin_password = "YourSecurePassword123!"  # CHANGE THIS!

# Keycloak database credentials
keycloak_database_username = "keycloak"
keycloak_database_password = "DatabasePassword456!" # CHANGE THIS!

# Keycloak database capacity
keycloak_database_min_acu = 0.5
keycloak_database_max_acu = 2
```

**Save the file** (Ctrl+O, Enter, Ctrl+X for nano)

#### Step 5.3: Verify terraform.tfvars

```bash
# Verify Keycloak variables were added
grep -A 15 "Keycloak Configuration" terraform.tfvars

# Should show the new Keycloak variables
# Should STILL show old variables (environment, aws_region, etc.)

# Count lines to ensure nothing was deleted
wc -l terraform.tfvars.backup terraform.tfvars
# New file should have ~15-20 MORE lines than backup
```

**🚨 STOP! Verify**:
- [ ] terraform.tfvars still has existing variables (environment, aws_region, etc.)
- [ ] terraform.tfvars has NEW Keycloak variables at the end
- [ ] Backup file exists (terraform.tfvars.backup)

#### Step 5.4: Initialize Terraform (if needed)

```bash
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs

# Initialize Terraform (downloads providers/modules)
terraform init
```

#### Step 5.5: Plan the Deployment

```bash
# Create a plan to see what will be created
terraform plan -out=tfplan

# REVIEW THE PLAN CAREFULLY!
# You should see:
# - Resources to ADD: ~15-20 (Keycloak infrastructure)
# - Resources to CHANGE: 0
# - Resources to DESTROY: 0

# If you see DESTROY, STOP and investigate!
```

**Expected resources to be created**:
- Aurora MySQL cluster and instances
- RDS Proxy
- ECS service (keycloak)
- Application Load Balancer
- Target groups
- Security groups (3 new ones)
- Route53 zone and records
- ACM certificate
- ECR repository
- SSM parameters (secrets)

#### Step 5.6: Apply the Deployment

```bash
# Apply the plan
terraform apply tfplan

# This will take ~10-15 minutes
# Watch for any errors

# When complete, you'll see outputs
terraform output
```

**Expected Outputs**:
```
keycloak_url = "https://kc.mycorp.click"
keycloak_admin_console = "https://kc.mycorp.click/admin"
keycloak_ecr_repository = "123456789.dkr.ecr.us-west-2.amazonaws.com/keycloak"
keycloak_database_endpoint = "keycloak-dev-cluster.cluster-xxx.us-west-2.rds.amazonaws.com"
nameservers = [
  "ns-123.awsdns-45.com",
  "ns-678.awsdns-90.net",
  ...
]

# Plus all your EXISTING outputs (registry, auth, etc.) should still be there
```

**✅ PHASE 5 COMPLETE - Verification**:

```bash
# Test 1: Check outputs (should have NEW Keycloak outputs)
terraform output | grep keycloak
# EXPECTED: Should see keycloak_url, keycloak_admin_console, nameservers

# Test 2: Check outputs (should STILL have OLD outputs)
terraform output | grep -E "registry|auth"
# EXPECTED: Should still see registry_url, auth_url, etc.

# Test 3: Verify no drift
terraform plan
# EXPECTED: "No changes. Your infrastructure matches the configuration."

# Test 4: Verify terraform.tfvars has both old and new
grep "environment" terraform/aws-ecs/terraform.tfvars
grep "keycloak_domain" terraform/aws-ecs/terraform.tfvars
# EXPECTED: Both should return results
```

**🚨 CRITICAL CHECKS**:
- [ ] Keycloak outputs exist (keycloak_url, etc.)
- [ ] Old outputs STILL exist (registry, auth, etc.)
- [ ] terraform.tfvars has BOTH old and new variables
- [ ] No Terraform drift (plan shows no changes)
- [ ] Backup file exists (terraform.tfvars.backup)

**Commit Terraform changes**:
```bash
cd ~/repos/mcp-gateway-registry

git add terraform/aws-ecs/terraform.tfvars
git add terraform/aws-ecs/terraform.tfvars.backup
git commit -m "Add Keycloak deployment variables

- Added keycloak_domain and root_domain
- Added keycloak admin credentials
- Added keycloak database configuration
- Preserved existing registry/auth configuration
- Created backup of previous tfvars"

git push origin feature/add-working-keycloak
```

---

### Phase 6: Post-Deployment Verification (30 min)

```bash
# 1. Update nameservers (if needed)
# Output will show Route53 nameservers for kc.mycorp.click
# Add NS records to mycorp.click zone if not using aws_route53_record.keycloak_ns

# 2. Wait for certificate validation (~5 minutes)
aws acm describe-certificate --certificate-arn <cert-arn> --region us-west-2 \
    --query 'Certificate.Status'
# Wait until: "ISSUED"

# 3. Verify ECS service is running
aws ecs describe-services \
    --cluster keycloak-dev \
    --services keycloak \
    --region us-west-2 \
    --query 'services[0].runningCount'
# Expected: 1

# 4. Test Keycloak
curl -I https://kc.mycorp.click/health
# Expected: HTTP/2 200

# 5. Access admin console
open https://kc.mycorp.click/admin
# Login with admin / YourSecurePassword123!
```

---

## File Organization Strategy

```
mcp-gateway-registry/
├── terraform/
│   └── aws-ecs/
│       ├── main.tf                    # Main config (existing)
│       ├── vpc.tf                     # VPC (existing - SHARED with Keycloak)
│       ├── variables.tf               # All variables (ADD Keycloak vars)
│       ├── outputs.tf                 # All outputs (ADD Keycloak outputs)
│       ├── locals.tf                  # Common tags, etc. (existing)
│       │
│       ├── auth-server.tf             # Existing auth server
│       ├── auth-server-sg.tf          # Existing auth server security groups
│       │
│       ├── keycloak-database.tf       # NEW: Keycloak database
│       ├── keycloak-ecs.tf            # NEW: Keycloak ECS service
│       ├── keycloak-security-groups.tf # NEW: Keycloak security groups
│       ├── keycloak-alb.tf            # NEW: Keycloak load balancer
│       ├── keycloak-dns.tf            # NEW: Keycloak Route53 + ACM
│       └── keycloak-ecr.tf            # NEW: Keycloak ECR repository
│
├── docker/
│   └── keycloak/
│       └── Dockerfile                 # NEW: Production-optimized Keycloak
│
└── Makefile                           # NEW: Build/deploy automation
```

**Principles**:
1. ✅ One file per logical component (database, ECS, ALB, etc.)
2. ✅ Clear naming: `keycloak-*.tf` for all Keycloak resources
3. ✅ Shared `vpc.tf` - both auth server and Keycloak use it
4. ✅ Easy to understand, easy to maintain

---

## Security Group Communication Matrix

```
┌──────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│              │ Auth Server │  Keycloak   │ Keycloak DB │     ALB     │
├──────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ Auth Server  │      -      │  → :8080    │      -      │      -      │
│ Keycloak     │      -      │      -      │  → :3306    │      -      │
│ Keycloak DB  │      -      │      -      │      -      │      -      │
│ ALB          │      -      │  → :8080    │      -      │      -      │
│ Internet     │      -      │      -      │      -      │  → :80/443  │
└──────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

**Key Rules**:
1. `aws_security_group_rule.keycloak_ecs_ingress_auth_server` - Auth → Keycloak
2. `aws_security_group_rule.keycloak_ecs_ingress_lb` - ALB → Keycloak
3. `aws_security_group_rule.keycloak_ecs_egress_db` - Keycloak → Database
4. `aws_security_group_rule.keycloak_lb_ingress_internet_https` - Internet → ALB

---

## What Makes This Maintainable

### 1. Shared Infrastructure
- ✅ One VPC for everything
- ✅ Reuse existing NAT gateway, internet gateway
- ✅ No VPC peering, no transit gateway complexity
- ✅ Lower costs, simpler troubleshooting

### 2. Clear File Organization
- ✅ `keycloak-*.tf` files are clearly separated
- ✅ Easy to find, easy to modify
- ✅ Can remove Keycloak entirely by deleting `keycloak-*.tf` files

### 3. Simple Security Model
- ✅ All security groups in same VPC
- ✅ Clear communication paths
- ✅ Easy to add more rules as needed

### 4. Production-Ready Defaults
- ✅ Uses `start --optimized`, NOT `start-dev`
- ✅ Aurora Serverless for cost optimization
- ✅ RDS Proxy for connection pooling
- ✅ Auto-validated SSL certificates
- ✅ Proper health checks

### 5. Easy Updates
```bash
# Update Keycloak version
docker build -t keycloak:v24 -f docker/keycloak/Dockerfile docker/keycloak/
docker push $ECR_REPO:v24

# Update ECS service
aws ecs update-service --cluster keycloak-dev --service keycloak --force-new-deployment
```

---

**✅ PHASE 6 COMPLETE - Checklist**:

- [ ] Nameservers added to domain registrar
- [ ] Certificate status is "ISSUED"
- [ ] ECS service is running (1 task)
- [ ] Health endpoint returns 200
- [ ] Admin console accessible
- [ ] Can login to admin console
- [ ] No infinite spinner (the old bug!)

---

## 🎯 FINAL VERIFICATION - Complete System Test

**This is the final test before declaring success.**

### Test 1: Infrastructure Health

```bash
# 1. Verify Keycloak is running
aws ecs describe-services --cluster keycloak-dev --services keycloak \
    --query 'services[0].runningCount'
# Expected: 1

# 2. Verify ALB target health
aws elbv2 describe-target-health --target-group-arn <tg-arn> \
    --query 'TargetHealthDescriptions[0].TargetHealth.State'
# Expected: "healthy"

# 3. Test health endpoint
curl https://kc.mycorp.click/health
# Expected: {"status":"UP"}

# 4. Test admin console (NO infinite spinner!)
curl -I https://kc.mycorp.click/admin
# Expected: HTTP/2 200

# 5. Test from auth server (internal communication)
# SSH into auth server ECS task
aws ecs execute-command --cluster <cluster> --task <task-id> --command "/bin/bash"

# Inside auth server container:
curl http://keycloak.local:8080/health
# Expected: {"status":"UP"}

# 6. Test authentication flow
curl https://kc.mycorp.click/realms/master/.well-known/openid-configuration
# Expected: JSON response with endpoints
```

### Test 3: Auth Server Integration

```bash
# Test auth server can reach Keycloak internally
# (This requires the security group rule we added)

# Option A: Check auth server logs for Keycloak connection
aws logs tail /aws/ecs/mcp-gateway-dev-auth --follow --region us-east-1 | grep -i keycloak

# Option B: Execute command in auth server container to test connectivity
AUTH_TASK_ARN=$(aws ecs list-tasks \
  --cluster mcp-gateway-dev \
  --service-name mcp-gateway-dev-auth \
  --region us-east-1 \
  --query 'taskArns[0]' \
  --output text)

aws ecs execute-command \
  --cluster mcp-gateway-dev \
  --task $AUTH_TASK_ARN \
  --container auth \
  --command "curl -I http://keycloak.mcp-gateway-dev.local:8080/health" \
  --interactive \
  --region us-east-1

# EXPECTED: HTTP/1.1 200 OK
```

**✅ ALL TESTS PASSING?**

If all tests pass:
- ✅ Infrastructure is healthy
- ✅ Keycloak is working (no infinite spinner!)
- ✅ Auth server can communicate with Keycloak
- ✅ HTTPS is configured
- ✅ **SUCCESS! Working Keycloak is deployed!**

---

## 📊 Success Criteria - Final Sign-Off

Before declaring victory, confirm:

### Phase 0 (Removal):
- [x] All 284 Keycloak references removed
- [x] Zero grep results for "keycloak"
- [x] Old AWS resources destroyed
- [x] Committed to Git

### Phase 1-2 (Setup):
- [x] Dockerfile copied
- [x] Production mode verified (start --optimized)
- [x] Committed to Git

### Phase 3 (Terraform):
- [x] 6 new keycloak-*.tf files created
- [x] Using EXISTING VPC (module.vpc.vpc_id)
- [x] Security group allows auth server → Keycloak
- [x] Committed to Git

### Phase 4 (Docker):
- [x] Image built successfully
- [x] Image pushed to ECR
- [x] Image tagged as "latest"

### Phase 5 (Deployment):
- [x] terraform apply succeeded
- [x] No errors in output
- [x] Variables configured

### Phase 6 (Verification):
- [x] DNS configured
- [x] Certificate issued
- [x] ECS service running
- [x] Health checks passing
- [x] Admin console works (NO infinite spinner!)
- [x] Auth server can reach Keycloak

### Final Validation:
- [x] All tests in "Testing Checklist" pass
- [x] No errors in CloudWatch logs
- [x] No Terraform drift (plan shows no changes)

**TOTAL TIME SPENT**: _______ hours (expected: 6-8 hours)

**BLOCKERS ENCOUNTERED**: _________________________________

**RESULT**: ✅ SUCCESS / ❌ ISSUES (describe):

---

## 🆘 Troubleshooting Guide

### Problem: Grep still finds "keycloak" references after Phase 0

**Solution**:
```bash
# Show exactly what was found
grep -r "keycloak" --include="*.tf" -i -n | grep -v ".terraform"

# Go back to keycloak-removal-checklist.md
# Find the file and line number in the checklist
# Remove it manually
```

### Problem: terraform validate fails after Phase 0

**Error**: "Reference to undeclared resource"

**Solution**:
```bash
# You missed removing a reference to a Keycloak resource
# Check the error message for the resource name
# Search for it:
grep -r "RESOURCE_NAME" --include="*.tf"

# Remove the reference (see removal checklist)
```

### Problem: terraform plan shows "Error: Duplicate resource"

**Cause**: You didn't remove the old Keycloak resources before adding new ones

**Solution**: Go back to Phase 0 and complete the removal checklist

### Problem: terraform apply destroyed existing infrastructure!

**Cause**: You overwrote terraform.tfvars instead of appending to it

**Solution**:
```bash
# Restore from backup
cp terraform.tfvars.backup terraform.tfvars

# Re-add Keycloak variables using APPEND method in Phase 5
# Do NOT use `cat > terraform.tfvars` (that overwrites!)
# Instead, use nano/code to EDIT and ADD to the end
```

### Problem: Admin console shows infinite spinner (the old bug!)

**Cause**: Docker image is using `start-dev` instead of `start --optimized`

**Solution**:
```bash
# Check the Dockerfile
cat docker/keycloak/Dockerfile | grep ENTRYPOINT
# MUST show: ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized"]

# If it shows "start-dev", you copied the wrong Dockerfile
# Re-copy from aws-ecs-keycloak
```

### Problem: Auth server can't reach Keycloak

**Cause**: Missing security group rule

**Solution**:
```bash
# Verify security group rule exists
cd ~/repos/mcp-gateway-registry/terraform/aws-ecs
grep -A 10 "keycloak_ecs_ingress_auth_server" keycloak-security-groups.tf

# Should see:
# source_security_group_id = aws_security_group.auth_server.id
```

### Problem: Certificate stuck in "Pending Validation"

**Cause**: Nameservers not added to domain registrar

**Solution**:
```bash
# Get the nameservers
terraform output | grep nameservers

# Add NS records to your domain registrar
# Wait 5-60 minutes for DNS propagation
```

---

## 🎓 For Junior Engineers: What You Learned

By following this guide, you successfully:

1. ✅ **Removed legacy code**: Cleaned up 284 references to broken infrastructure
2. ✅ **Infrastructure as Code**: Used Terraform to deploy cloud resources
3. ✅ **Docker**: Built and pushed optimized container images
4. ✅ **Networking**: Configured VPCs, security groups, load balancers
5. ✅ **DNS & SSL**: Set up Route53 and ACM certificates
6. ✅ **ECS/Fargate**: Deployed containerized applications
7. ✅ **Best Practices**:
   - Production-optimized Keycloak (not dev mode)
   - Shared infrastructure (cost-effective)
   - Proper security group rules
   - Auto-validated certificates
   - Health checks and monitoring

**Skills Applied**:
- Git branching and commits
- Terraform (resources, modules, variables, outputs)
- AWS services (ECS, RDS, ALB, Route53, ACM, ECR)
- Docker (multi-stage builds, optimization)
- Bash scripting and verification
- Systematic troubleshooting

**Time to Master These Skills**: ~6-12 months of practice
**Your Progress**: You just did 6-8 hours of expert-level work!

---

## Rollback Plan

If something goes wrong:

```bash
# 1. Revert to previous branch
git checkout backup-broken-keycloak

# 2. Destroy Keycloak resources
terraform destroy -target=module.keycloak_database
terraform destroy -target=module.keycloak_ecs
terraform destroy -target=aws_lb.keycloak
# ... etc

# 3. Or, restore entire state
terraform apply

# 4. Investigate issues
aws logs tail /aws/ecs/keycloak-dev --follow
```

---

## Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| ECS Fargate (1 task, 1 vCPU, 2GB) | ~$30 |
| Aurora MySQL Serverless v2 (0.5-2 ACU) | ~$20-50 |
| NAT Gateway (shared with other services) | $0 (already exists) |
| ALB | ~$16 |
| Route53 hosted zone | $0.50 |
| Data transfer | ~$5-10 |
| **Total** | **~$71-106/month** |

**Savings from shared VPC**: ~$32/month (no additional NAT gateway)

---

## Timeline

| Phase | Task | Time | Can Parallelize? |
|-------|------|------|------------------|
| 1 | Understand current structure | 30 min | No |
| 2 | Remove broken Keycloak | 15 min | No |
| 3 | Add Terraform files | 2-3 hours | No |
| 4 | Build Docker image | 30 min | Yes (after Phase 2) |
| 5 | Deploy with Terraform | 1 hour | No |
| 6 | Post-deployment config | 15 min | No |
| **Total** | | **4-5 hours** | |

---

## The DevOps Expert Perspective

### Why This Approach Wins

1. **Simplicity**: Shared VPC = fewer moving parts
2. **Maintainability**: Clear file organization, easy to find things
3. **Cost-effective**: Reuse existing infrastructure
4. **Scalable**: Easy to add more services later
5. **Proven**: Uses working code from aws-ecs-keycloak
6. **Production-ready**: Proper start mode, health checks, autoscaling

### Common Pitfalls to Avoid

❌ **Creating separate VPC for Keycloak**
- Requires VPC peering or transit gateway
- More complex security groups
- Higher costs (additional NAT gateway)

❌ **Using `start-dev` mode**
- Admin console infinite spinner
- Poor performance
- Not production-ready

❌ **Hardcoding secrets in Terraform**
- Use SSM Parameter Store (as shown)
- Or AWS Secrets Manager for production

❌ **Forgetting to pre-build Keycloak**
- Must run `kc.sh build` in Dockerfile
- Otherwise features don't work properly

---

## Quick Start Commands

```bash
# 1. Clone and setup
cd ~/repos/mcp-gateway-registry
git checkout -b feature/working-keycloak

# 2. Copy Keycloak Terraform files
cp ~/repos/aws-ecs-keycloak/terragrunt/aws/database.tf terraform/aws-ecs/keycloak-database.tf
cp ~/repos/aws-ecs-keycloak/terragrunt/aws/ecs.tf terraform/aws-ecs/keycloak-ecs.tf
# ... (as shown in Phase 3)

# 3. Modify to use existing VPC
# Edit keycloak-*.tf files to reference module.vpc instead of module.keycloak_vpc

# 4. Copy Dockerfile
mkdir -p docker/keycloak
cp ~/repos/aws-ecs-keycloak/docker/Dockerfile docker/keycloak/

# 5. Deploy
cd terraform/aws-ecs
terraform init
terraform apply

# 6. Build and push image
make push-keycloak  # Or follow manual steps

# 7. Verify
curl https://kc.mycorp.click/health
open https://kc.mycorp.click/admin
```

---

## Success Criteria

✅ Keycloak admin console loads (NO infinite spinner!)
✅ Can login to admin console
✅ Auth server can communicate with Keycloak internally
✅ HTTPS works with valid certificate
✅ Health checks are passing
✅ ECS autoscaling works (scales to 2 tasks under load)
✅ Database connection pooling via RDS Proxy
✅ All resources tagged properly for cost tracking

---

## Next Steps After Integration

1. **Configure Keycloak realms and clients** for auth server
2. **Setup monitoring**: CloudWatch dashboards, alarms
3. **Implement CI/CD**: GitHub Actions for automated deployments
4. **Backup strategy**: Automated database backups, restore testing
5. **High availability**: Increase min tasks to 2 for production
6. **Performance tuning**: Adjust ACU limits based on usage

---

## 📁 Document Cross-References

This guide works together with:

1. **keycloak-removal-checklist.md** (REQUIRED for Phase 0)
   - Location: Same directory as this file
   - Purpose: Line-by-line removal of broken Keycloak
   - When to use: Phase 0 (FIRST)

2. **Terraform files from aws-ecs-keycloak** (source code)
   - Location: ~/repos/aws-ecs-keycloak/terragrunt/aws/
   - Purpose: Working Keycloak implementation to copy from
   - When to use: Phase 3

3. **Dockerfile** (production-ready image)
   - Location: ~/repos/aws-ecs-keycloak/docker/Dockerfile
   - Purpose: Pre-optimized Keycloak build
   - When to use: Phase 2

---

## Summary

**The Complete Plan** (in order):
0. **REMOVE ALL BROKEN KEYCLOAK** (284 references, 13 files) ← CRITICAL FIRST STEP
1. Create branches and backup
2. Copy production Dockerfile
3. Add working Keycloak Terraform files (6 new files)
4. Build and push Docker image to ECR
5. Deploy with Terraform (terraform apply)
6. Configure DNS and verify deployment

**Why It Works**:
- ✅ Shared VPC = simple networking
- ✅ Clear file organization = maintainable
- ✅ Production mode Keycloak = actually works
- ✅ Proven code from aws-ecs-keycloak

**Time**: ~6-8 hours total
**Complexity**: Low (if you follow the guide exactly)
**Maintainability**: High (clear structure, shared infrastructure)
**Your Job Security**: 100% safe 😎

**Documents You Need**:
1. This file (simple-integration-plan.md) - The main guide
2. keycloak-removal-checklist.md - REQUIRED for Phase 0
