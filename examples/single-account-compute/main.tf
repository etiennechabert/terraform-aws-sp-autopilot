# Single Account - Compute Savings Plans Only
#
# This example demonstrates the simplest deployment scenario:
# - Single AWS account (no Organizations)
# - Compute Savings Plans only (EC2, Lambda, Fargate)
# - Conservative coverage targets
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
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 2.0"

  # Purchase strategy - conservative targets
  purchase_strategy = {
    coverage_target_percent = 80  # Target 80% coverage
    max_coverage_cap        = 90  # Never exceed 90% coverage
    lookback_days           = 30  # 30 days of usage history
    min_data_days           = 14  # Require at least 14 days of data

    # Simple strategy with gradual commitment growth
    simple = {
      max_purchase_percent = 5  # Max 5% of monthly spend per cycle
    }
  }

  # Savings Plans configuration - Compute only
  sp_plans = {
    compute = {
      enabled                = true
      all_upfront_three_year = 0.70  # 70% in 3-year all-upfront (maximum savings)
      all_upfront_one_year   = 0.30  # 30% in 1-year all-upfront (more flexibility)
    }

    database = {
      enabled = false
    }

    sagemaker = {
      enabled = false
    }
  }

  # Scheduling - 3-day review window
  scheduler = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month at 8:00 AM UTC
    purchaser = "cron(0 8 4 * ? *)"  # 4th of month at 8:00 AM UTC (3-day review window)
    reporter  = "cron(0 9 1 * ? *)"  # 1st of month at 9:00 AM UTC
  }

  # Notifications
  notifications = {
    emails         = ["devops@example.com", "finops@example.com"]
    send_no_action = true  # Get notified even when no action needed
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

  # Lambda configuration (using defaults with error alarms enabled)
  lambda_config = {
    scheduler = {
      dry_run     = true  # Start in dry-run mode - emails only
      error_alarm = true
    }
    purchaser = { error_alarm = true }
    reporter  = { error_alarm = true }
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
