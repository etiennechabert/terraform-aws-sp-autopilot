# Dynamic Target + Dichotomy Split
#
# This example demonstrates the dynamic target + dichotomy split strategy:
# - Target: dynamically calculated based on usage patterns (balanced risk level)
# - Split: dichotomy (binary search) for adaptive purchase sizing
#
# Dynamic Target (balanced):
# Uses the knee-point algorithm to find the optimal coverage target where
# marginal savings efficiency starts dropping significantly. This adapts
# automatically to your workload patterns.
#
# Dichotomy Split Behavior (max_purchase_percent = 50%, min = 1%):
# - Month 1: At 0% → Try 50% (fits under target) → Purchase 50%
# - Month 2: At 50% → Try 50% (exceeds target) → Try 25% (fits) → Purchase 25%
# - Month 3: At 75% → Keep halving until it fits under target
# - ...continues until target reached
#
# Benefits:
# - Target adapts to actual workload patterns (no manual tuning)
# - Dichotomy creates stable, distributed commitments over time
# - Prevents over-commitment through exponential halving

terraform {
  required_version = ">= 1.4"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

module "savings_plans" {
  source = "etiennechabert/sp-autopilot/aws"

  # Resource naming (can be overridden for testing)
  name_prefix = var.name_prefix

  # Purchase strategy - dynamic target with dichotomy split
  purchase_strategy = {
    max_coverage_cap = 95       # Safety cap at 95%
    lookback_days    = 13       # Max for HOURLY granularity (recommended)
    granularity      = "HOURLY" # Recommended for accurate analysis

    target = {
      dynamic = { risk_level = "balanced" } # Knee-point algorithm
    }

    split = {
      dichotomy = {
        max_purchase_percent = 50 # Start at 50%
        min_purchase_percent = 1  # Minimum purchase granularity
      }
    }
  }

  # Savings Plans configuration - Compute only
  sp_plans = {
    compute = {
      enabled   = true
      plan_type = "all_upfront_three_year" # Maximum savings
    }

    database = {
      enabled = false
    }

    sagemaker = {
      enabled = false
    }
  }

  # Scheduling - monthly automation cycle (can be overridden for testing)
  scheduler = {
    scheduler = try(var.scheduler.scheduler, "cron(0 8 1 * ? *)") # 1st of month - analyze usage
    purchaser = try(var.scheduler.purchaser, "cron(0 8 4 * ? *)") # 4th of month - execute purchases (3-day review)
    reporter  = try(var.scheduler.reporter, "cron(0 9 1 * ? *)")  # 1st of month - generate reports
  }

  # Notifications
  notifications = {
    emails         = ["sre@example.com", "finops@example.com"]
    send_no_action = true
  }

  # Reporting
  reporting = {
    enabled        = true
    format         = "html"
    email_reports  = true
    retention_days = 365
  }

  # Monitoring
  monitoring = {
    dlq_alarm       = true
    error_threshold = 1
  }

  # Lambda configuration - purchaser enabled for production use (can be overridden for testing)
  lambda_config = {
    scheduler = {
      dry_run     = try(var.lambda_config.scheduler.dry_run, false) # Production mode - queue purchases
      error_alarm = true
    }
    purchaser = {
      enabled     = try(var.lambda_config.purchaser.enabled, true) # Enable purchaser Lambda
      error_alarm = true
    }
    reporter = {
      enabled     = try(var.lambda_config.reporter.enabled, true)
      error_alarm = true
    }
  }

  # Tagging
  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
    Strategy    = "dynamic-dichotomy"
    Purpose     = "savings-plans-automation"
  }
}

# Outputs for monitoring and integration
output "scheduler_lambda_name" {
  description = "Name of the scheduler Lambda function"
  value       = module.savings_plans.scheduler_lambda_name
}

output "purchaser_lambda_name" {
  description = "Name of the purchaser Lambda function"
  value       = module.savings_plans.purchaser_lambda_name
}

output "queue_url" {
  description = "SQS queue URL for purchase intents"
  value       = module.savings_plans.queue_url
}

output "sns_topic_arn" {
  description = "SNS topic ARN for notifications"
  value       = module.savings_plans.sns_topic_arn
}

output "module_configuration" {
  description = "Summary of module configuration"
  value       = module.savings_plans.module_configuration
}
