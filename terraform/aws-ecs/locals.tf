locals {
  # Dynamic domain construction based on region
  # Format: kc.{region}.mycorp.click and registry.{region}.mycorp.click
  keycloak_domain = var.use_regional_domains ? "kc.${var.aws_region}.${var.base_domain}" : var.keycloak_domain
  root_domain     = var.use_regional_domains ? "${var.aws_region}.${var.base_domain}" : var.root_domain

  common_tags = {
    Project     = "mcp-gateway-registry"
    Component   = "keycloak"
    Environment = "production"
    ManagedBy   = "terraform"
    CreatedAt   = timestamp()
  }
}
