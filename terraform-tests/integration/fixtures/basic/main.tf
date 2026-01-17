# Test Fixture: Basic Configuration
# Purpose: Minimal configuration for integration testing

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ============================================================================
# Provider Configuration
# ============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "test"
      TestFixture = "basic"
      ManagedBy   = "terratest"
    }
  }
}

# ============================================================================
# Module Under Test
# ============================================================================

module "sp_autopilot" {
  source = "../../../.."

  name_prefix       = var.name_prefix
  purchase_strategy = var.purchase_strategy
  sp_plans          = var.sp_plans
  scheduler         = var.scheduler
  notifications     = var.notifications
  reporting         = var.reporting
  monitoring        = var.monitoring
  lambda_config     = var.lambda_config
  tags              = var.tags
}
