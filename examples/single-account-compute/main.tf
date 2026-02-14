# Fixed Target + Linear Split
#
# This example demonstrates the fixed target + linear split strategy:
# - Target: fixed at 100% coverage
# - Split: linear steps of 10% per cycle
# - Single AWS account (no Organizations)
# - Compute Savings Plans only (EC2, Lambda, Fargate)
# - Starts in dry-run mode for safety

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

  # Purchase strategy - fixed target at 100% with linear 10% steps
  purchase_strategy = {
    max_coverage_cap = 100      # Allow up to 100% coverage
    lookback_days    = 13       # Max for HOURLY granularity (recommended)
    granularity      = "HOURLY" # Recommended for accurate analysis

    target = {
      fixed = { coverage_percent = 100 } # Target 100% coverage
    }

    split = {
      linear = { step_percent = 10 } # 10% of spend per cycle
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
  scheduler = {
    scheduler = try(var.scheduler.scheduler, "cron(0 8 1 * ? *)")  # 1st of month at 8:00 AM UTC
    purchaser = try(var.scheduler.purchaser, "cron(0 8 10 * ? *)") # 10th of month at 8:00 AM UTC (9-day review window)
    reporter  = try(var.scheduler.reporter, "cron(0 9 20 * ? *)")  # 20th of month at 9:00 AM UTC
  }

  # Notifications
  notifications = {
    emails         = ["devops@example.com", "finops@example.com"]
    send_no_action = true # Get notified even when no action needed
  }

  # Reporting (enabled by default)
  reporting = {
    enabled       = true
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
      dry_run     = try(var.lambda_config.scheduler.dry_run, true) # Start in dry-run mode - emails only
      error_alarm = true
    }
    purchaser = {
      enabled     = try(var.lambda_config.purchaser.enabled, true)
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
