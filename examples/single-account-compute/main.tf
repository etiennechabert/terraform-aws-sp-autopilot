# Dynamic Prudent Target + Fixed Step Split
#
# This example demonstrates the dynamic prudent target + fixed_step split strategy:
# - Target: dynamic prudent (85% of minimum hourly spend)
# - Split: fixed steps of 10% per cycle
# - Single AWS account (no Organizations)
# - Compute Savings Plans only (EC2, Lambda, Fargate)
# - Purchaser disabled by default for safety

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

  # Purchase strategy - dynamic prudent target with fixed 10% steps
  purchase_strategy = {
    target = {
      dynamic = { risk_level = "prudent" } # 85% of minimum hourly spend
    }

    split = {
      fixed_step = { step_percent = 10 } # 10% of spend per cycle
    }
  }

  # Savings Plans configuration - Compute only
  sp_plans = {
    compute = {
      enabled   = true
      plan_type = "all_upfront_one_year" # Or: all_upfront_three_year, partial_upfront_one_year, etc.
    }

    database = {
      enabled = false
      # plan_type not needed when disabled
    }

    sagemaker = {
      enabled = false
      # plan_type not needed when disabled
    }
  }

  # Scheduling - spread evenly across the month (can be overridden for testing)
  cron_schedules = {
    scheduler = try(var.cron_schedules.scheduler, "cron(0 8 1 * ? *)")  # 1st of month at 8:00 AM UTC
    purchaser = try(var.cron_schedules.purchaser, "cron(0 8 10 * ? *)") # 10th of month at 8:00 AM UTC (9-day review window)
    reporter  = try(var.cron_schedules.reporter, "cron(0 9 20 * ? *)")  # 20th of month at 9:00 AM UTC
  }

  # Notifications
  notifications = {
    emails = ["devops@example.com", "finops@example.com"]
  }

  # Reporting (enabled by default via lambda_config.reporter.enabled)
  reporting = {
    format        = "html"
    email_reports = false
  }

  # Monitoring
  monitoring = {
    dlq_alarm       = true
    error_threshold = 1
  }

  # Lambda configuration (using defaults with error alarms enabled, can be overridden for testing)
  lambda_config = {
    scheduler = {
      error_alarm = true
    }
    purchaser = {
      enabled     = try(var.lambda_config.purchaser.enabled, false) # Start with purchaser disabled for safety
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
