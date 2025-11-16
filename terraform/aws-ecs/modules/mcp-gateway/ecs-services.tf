# ECS Services for MCP Gateway Registry

# ECS Service: Auth Server
module "ecs_service_auth" {
  source  = "terraform-aws-modules/ecs/aws//modules/service"
  version = "~> 6.0"

  name         = "${local.name_prefix}-auth"
  cluster_arn  = var.ecs_cluster_arn
  cpu          = tonumber(var.cpu)
  memory       = tonumber(var.memory)
  desired_count = var.enable_autoscaling ? var.autoscaling_min_capacity : var.auth_replicas
  enable_autoscaling = var.enable_autoscaling
  autoscaling_min_capacity = var.autoscaling_min_capacity
  autoscaling_max_capacity = var.autoscaling_max_capacity
  autoscaling_policies = var.enable_autoscaling ? {
    cpu = {
      policy_type = "TargetTrackingScaling"
      target_tracking_scaling_policy_configuration = {
        predefined_metric_specification = {
          predefined_metric_type = "ECSServiceAverageCPUUtilization"
        }
        target_value = var.autoscaling_target_cpu
      }
    }
    memory = {
      policy_type = "TargetTrackingScaling"
      target_tracking_scaling_policy_configuration = {
        predefined_metric_specification = {
          predefined_metric_type = "ECSServiceAverageMemoryUtilization"
        }
        target_value = var.autoscaling_target_memory
      }
    }
  } : {}

  requires_compatibilities = ["FARGATE", "EC2"]
  capacity_provider_strategy = {
    FARGATE = {
      capacity_provider = "FARGATE"
      weight = 100
      base   = 1
    }
  }

  # Task roles
  create_task_exec_iam_role = true
  task_exec_iam_role_policies = {
    SecretsManagerAccess = aws_iam_policy.ecs_secrets_access.arn
  }
  create_tasks_iam_role  = true
  tasks_iam_role_policies = {
    SecretsManagerAccess = aws_iam_policy.ecs_secrets_access.arn
  }

  # Enable Service Connect
  service_connect_configuration = {
    namespace = aws_service_discovery_private_dns_namespace.mcp.arn
    service = [{
      client_alias = {
        port     = 8888
        dns_name = "auth-server"
      }
      port_name      = "auth-server"
      discovery_name = "auth-server"
    }]
  }

  # Container definitions
  container_definitions = {
    auth-server = {
      cpu                    = tonumber(var.cpu)
      memory                 = tonumber(var.memory)
      essential              = true
      image                  = var.auth_server_image_uri
      readonlyRootFilesystem = false

      portMappings = [
        {
          name           = "auth-server"
          containerPort = 8888
          protocol       = "tcp"
        }
      ]

      environment = [
        {
          name  = "REGISTRY_URL"
          value = "https://${var.domain_name}"
        },
        {
          name  = "AUTH_SERVER_URL"
          value = "http://auth-server:8888"
        },
        {
          name  = "AUTH_SERVER_EXTERNAL_URL"
          value = "https://${var.domain_name}:8888"
        },
        {
          name  = "AWS_REGION"
          value = data.aws_region.current.id
        },
        {
          name  = "AUTH_PROVIDER"
          value = var.keycloak_domain != "" ? "keycloak" : "default"
        },
        {
          name  = "KEYCLOAK_URL"
          value = var.keycloak_domain != "" ? "https://${var.keycloak_domain}" : ""
        },
        {
          name  = "KEYCLOAK_EXTERNAL_URL"
          value = var.keycloak_domain != "" ? "https://${var.keycloak_domain}" : ""
        },
        {
          name  = "KEYCLOAK_REALM"
          value = "mcp-gateway"
        },
        {
          name  = "KEYCLOAK_CLIENT_ID"
          value = "mcp-gateway-web"
        },
        {
          name  = "SCOPES_CONFIG_PATH"
          value = "/efs/auth_config/scopes.yml"
        }
      ]

      secrets = [
        {
          name      = "SECRET_KEY"
          valueFrom = aws_secretsmanager_secret.secret_key.arn
        },
        {
          name      = "KEYCLOAK_CLIENT_SECRET"
          valueFrom = "${data.aws_secretsmanager_secret.keycloak_client_secret.arn}:client_secret::"
        }
      ]

      mountPoints = [
        {
          sourceVolume  = "mcp-logs"
          containerPath = "/app/logs"
          readOnly      = false
        },
        {
          sourceVolume  = "auth-config"
          containerPath = "/efs/auth_config"
          readOnly      = false
        }
      ]

      enable_cloudwatch_logging              = true
      cloudwatch_log_group_name             = "/ecs/${local.name_prefix}-auth-server"
      cloudwatch_log_group_retention_in_days = 30

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8888/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  }

  volume = {
    mcp-logs = {
      efs_volume_configuration = {
        file_system_id     = module.efs.id
        access_point_id    = module.efs.access_points["logs"].id
        transit_encryption = "ENABLED"
      }
    }
    auth-config = {
      efs_volume_configuration = {
        file_system_id     = module.efs.id
        access_point_id    = module.efs.access_points["auth_config"].id
        transit_encryption = "ENABLED"
      }
    }
  }

  load_balancer = {
    service = {
      target_group_arn = module.alb.target_groups["auth"].arn
      container_name   = "auth-server"
      container_port   = 8888
    }
  }

  subnet_ids = var.private_subnet_ids
  security_group_ingress_rules = {
    alb_8888 = {
      description                  = "Auth server port from ALB"
      from_port                    = 8888
      to_port                      = 8888
      ip_protocol                  = "tcp"
      referenced_security_group_id = module.alb.security_group_id
    }
  }
  security_group_egress_rules = {
    all = {
      ip_protocol = "-1"
      cidr_ipv4   = "0.0.0.0/0"
    }
  }

  tags = local.common_tags
}

# ECS Service: Registry (Main service with nginx, SSL, FAISS, models)
module "ecs_service_registry" {
  source  = "terraform-aws-modules/ecs/aws//modules/service"
  version = "~> 6.0"

  name         = "${local.name_prefix}-registry"
  cluster_arn  = var.ecs_cluster_arn
  cpu          = tonumber(var.cpu)
  memory       = tonumber(var.memory)
  desired_count = var.enable_autoscaling ? var.autoscaling_min_capacity : var.registry_replicas
  enable_autoscaling = var.enable_autoscaling
  autoscaling_min_capacity = var.autoscaling_min_capacity
  autoscaling_max_capacity = var.autoscaling_max_capacity
  autoscaling_policies = var.enable_autoscaling ? {
    cpu = {
      policy_type = "TargetTrackingScaling"
      target_tracking_scaling_policy_configuration = {
        predefined_metric_specification = {
          predefined_metric_type = "ECSServiceAverageCPUUtilization"
        }
        target_value = var.autoscaling_target_cpu
      }
    }
    memory = {
      policy_type = "TargetTrackingScaling"
      target_tracking_scaling_policy_configuration = {
        predefined_metric_specification = {
          predefined_metric_type = "ECSServiceAverageMemoryUtilization"
        }
        target_value = var.autoscaling_target_memory
      }
    }
  } : {}

  requires_compatibilities = ["FARGATE", "EC2"]
  capacity_provider_strategy = {
    FARGATE = {
      capacity_provider = "FARGATE"
      weight = 100
      base   = 1
    }
  }

  # Task roles
  create_task_exec_iam_role = true
  task_exec_iam_role_policies = {
    SecretsManagerAccess = aws_iam_policy.ecs_secrets_access.arn
  }
  create_tasks_iam_role  = true
  tasks_iam_role_policies = {
    SecretsManagerAccess = aws_iam_policy.ecs_secrets_access.arn
  }

  # Enable Service Connect
  service_connect_configuration = {
    namespace = aws_service_discovery_private_dns_namespace.mcp.arn
    service = [{
      client_alias = {
        port     = 7860
        dns_name = "registry"
      }
      port_name      = "registry"
      discovery_name = "registry"
    }]
  }

  # Container definitions
  container_definitions = {
    registry = {
      cpu                    = tonumber(var.cpu)
      memory                 = tonumber(var.memory)
      essential              = true
      image                  = var.registry_image_uri
      readonlyRootFilesystem = false

      portMappings = [
        {
          name           = "http"
          containerPort = 80
          protocol       = "tcp"
        },
        {
          name           = "https"
          containerPort = 443
          protocol       = "tcp"
        },
        {
          name           = "registry"
          containerPort = 7860
          protocol       = "tcp"
        }
      ]

      environment = [
        {
          name  = "GATEWAY_ADDITIONAL_SERVER_NAMES"
          value = var.domain_name != "" ? var.domain_name : ""
        },
        {
          name  = "EC2_PUBLIC_DNS"
          value = var.domain_name != "" ? var.domain_name : module.alb.dns_name
        },
        {
          name  = "AUTH_SERVER_URL"
          value = "http://auth-server:8888"
        },
        {
          name  = "AUTH_SERVER_EXTERNAL_URL"
          value = var.domain_name != "" ? "https://${var.domain_name}:8888" : "http://${module.alb.dns_name}:8888"
        },
        {
          name  = "KEYCLOAK_URL"
          value = var.keycloak_domain != "" ? "https://${var.keycloak_domain}" : ""
        },
        {
          name  = "KEYCLOAK_ENABLED"
          value = var.keycloak_domain != "" ? "true" : "false"
        },
        {
          name  = "KEYCLOAK_REALM"
          value = "mcp-gateway"
        },
        {
          name  = "KEYCLOAK_CLIENT_ID"
          value = "mcp-gateway-web"
        },
        {
          name  = "AUTH_PROVIDER"
          value = var.keycloak_domain != "" ? "keycloak" : "default"
        },
        {
          name  = "AWS_REGION"
          value = data.aws_region.current.id
        }
      ]

      secrets = [
        {
          name      = "SECRET_KEY"
          valueFrom = aws_secretsmanager_secret.secret_key.arn
        },
        {
          name      = "ADMIN_PASSWORD"
          valueFrom = aws_secretsmanager_secret.admin_password.arn
        },
        {
          name      = "KEYCLOAK_CLIENT_SECRET"
          valueFrom = "${data.aws_secretsmanager_secret.keycloak_client_secret.arn}:client_secret::"
        }
      ]

      mountPoints = [
        {
          sourceVolume  = "mcp-servers"
          containerPath = "/app/registry/servers"
          readOnly      = false
        },
        {
          sourceVolume  = "mcp-models"
          containerPath = "/app/registry/models"
          readOnly      = false
        },
        {
          sourceVolume  = "mcp-logs"
          containerPath = "/app/logs"
          readOnly      = false
        }
      ]

      enable_cloudwatch_logging              = true
      cloudwatch_log_group_name             = "/ecs/${local.name_prefix}-registry"
      cloudwatch_log_group_retention_in_days = 30

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:7860/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  }

  volume = {
    mcp-servers = {
      efs_volume_configuration = {
        file_system_id     = module.efs.id
        access_point_id    = module.efs.access_points["servers"].id
        transit_encryption = "ENABLED"
      }
    }
    mcp-models = {
      efs_volume_configuration = {
        file_system_id     = module.efs.id
        access_point_id    = module.efs.access_points["models"].id
        transit_encryption = "ENABLED"
      }
    }
    mcp-logs = {
      efs_volume_configuration = {
        file_system_id     = module.efs.id
        access_point_id    = module.efs.access_points["logs"].id
        transit_encryption = "ENABLED"
      }
    }
  }

  load_balancer = {
    http = {
      target_group_arn = module.alb.target_groups["registry"].arn
      container_name   = "registry"
      container_port   = 80
    }
    gradio = {
      target_group_arn = module.alb.target_groups["gradio"].arn
      container_name   = "registry"
      container_port   = 7860
    }
  }

  subnet_ids = var.private_subnet_ids
  security_group_ingress_rules = {
    alb_80 = {
      description                  = "HTTP port"
      from_port                    = 80
      to_port                      = 80
      ip_protocol                  = "tcp"
      referenced_security_group_id = module.alb.security_group_id
    }
    alb_443 = {
      description                  = "HTTPS port"
      from_port                    = 443
      to_port                      = 443
      ip_protocol                  = "tcp"
      referenced_security_group_id = module.alb.security_group_id
    }
    alb_7860 = {
      description                  = "Gradio port"
      from_port                    = 7860
      to_port                      = 7860
      ip_protocol                  = "tcp"
      referenced_security_group_id = module.alb.security_group_id
    }
  }
  security_group_egress_rules = {
    all = {
      ip_protocol = "-1"
      cidr_ipv4   = "0.0.0.0/0"
    }
  }

  tags = local.common_tags

  depends_on = [module.ecs_service_auth]
}


# Allow registry to communicate with auth server on port 8888
resource "aws_vpc_security_group_ingress_rule" "registry_to_auth" {
  security_group_id            = module.ecs_service_auth.security_group_id
  referenced_security_group_id = module.ecs_service_registry.security_group_id
  from_port                    = 8888
  to_port                      = 8888
  ip_protocol                  = "tcp"
  description                  = "Allow registry to access auth server"
  
  tags = local.common_tags
}
