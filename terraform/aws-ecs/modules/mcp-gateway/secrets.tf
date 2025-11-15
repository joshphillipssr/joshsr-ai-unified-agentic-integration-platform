# Secrets Manager resources for MCP Gateway Registry

# Random passwords for application secrets

resource "random_password" "secret_key" {
  length  = 64
  special = true
}

resource "random_password" "admin_password" {
  length      = 32
  special     = true
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
  min_special = 1
}

# Core application secrets

resource "aws_secretsmanager_secret" "secret_key" {
  name_prefix = "${local.name_prefix}-secret-key-"
  description = "Secret key for MCP Gateway Registry"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "secret_key" {
  secret_id     = aws_secretsmanager_secret.secret_key.id
  secret_string = random_password.secret_key.result
}

resource "aws_secretsmanager_secret" "admin_password" {
  name_prefix = "${local.name_prefix}-admin-password-"
  description = "Admin password for MCP Gateway Registry"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "admin_password" {
  secret_id     = aws_secretsmanager_secret.admin_password.id
  secret_string = random_password.admin_password.result
}