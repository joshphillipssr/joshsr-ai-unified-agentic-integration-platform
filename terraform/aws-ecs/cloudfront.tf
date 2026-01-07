#
# CloudFront Distributions for HTTPS without Custom Domain
#
# Enables HTTPS access using default *.cloudfront.net certificates
# when custom Route53 DNS is not available (workshops, demos, evaluations)
#

# Data sources for managed CloudFront policies
data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

# CloudFront distribution for MCP Gateway ALB
resource "aws_cloudfront_distribution" "mcp_gateway" {
  count = var.enable_cloudfront ? 1 : 0

  enabled             = true
  comment             = "${var.name} MCP Gateway Registry CloudFront Distribution"
  default_root_object = ""
  price_class         = "PriceClass_100"

  origin {
    domain_name = module.mcp_gateway.alb_dns_name
    origin_id   = "mcp-gateway-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    # Custom header that ALB won't overwrite (unlike x-forwarded-proto)
    custom_header {
      name  = "X-Cloudfront-Forwarded-Proto"
      value = "https"
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "mcp-gateway-alb"

    # Disable caching for dynamic content
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    # Forward all headers to origin
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id

    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.name}-mcp-gateway-cloudfront"
      Component = "mcp-gateway"
    }
  )
}

# CloudFront distribution for Keycloak ALB
resource "aws_cloudfront_distribution" "keycloak" {
  count = var.enable_cloudfront ? 1 : 0

  enabled     = true
  comment     = "${var.name} Keycloak CloudFront Distribution"
  price_class = "PriceClass_100"

  origin {
    domain_name = aws_lb.keycloak.dns_name
    origin_id   = "keycloak-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    # Custom header that ALB won't overwrite
    custom_header {
      name  = "X-Cloudfront-Forwarded-Proto"
      value = "https"
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "keycloak-alb"

    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id

    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.name}-keycloak-cloudfront"
      Component = "keycloak"
    }
  )
}
