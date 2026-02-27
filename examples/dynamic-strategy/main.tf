# Dynamic Target + Gap Split
#
# This example demonstrates the dynamic target + gap split strategy:
# - Target: dynamically calculated based on usage patterns (optimal risk level)
# - Split: gap_split divides the coverage gap by a configurable divider
#
# Dynamic Target (optimal):
# Uses the knee-point algorithm to find the optimal coverage target where
# marginal savings efficiency starts dropping significantly. This adapts
# automatically to your workload patterns.
#
# Gap Split Behavior (divider = 2):
# - Divides the coverage gap by the divider each cycle
# - Clamps result between min_purchase_percent and max_purchase_percent
# - If the gap is smaller than min_purchase_percent, purchases exactly the gap

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

  # Purchase strategy - dynamic target with gap split
  purchase_strategy = {
    target = {
      dynamic = { risk_level = "optimal" } # Knee-point algorithm
    }

    split = {
      gap_split = {
        divider = 2 # Halve the gap each cycle
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
  cron_schedules = {
    scheduler = try(var.cron_schedules.scheduler, "cron(0 8 1 * ? *)") # 1st of month - analyze usage
    purchaser = try(var.cron_schedules.purchaser, "cron(0 8 4 * ? *)") # 4th of month - execute purchases (3-day review)
    reporter  = try(var.cron_schedules.reporter, "cron(0 9 1 * ? *)")  # 1st of month - generate reports
  }

  # Notifications
  notifications = {
    emails = ["sre@example.com", "finops@example.com"]
  }

  # Reporting
  reporting = {
    format        = "html"
    email_reports = true
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
    Strategy    = "dynamic-gap-splitter"
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
