# Single Account - Compute Savings Plans Only
#
# This example demonstrates the simplest deployment scenario:
# - Single AWS account (no Organizations)
# - Compute Savings Plans only (EC2, Lambda, Fargate)
# - Conservative coverage targets
# - Starts in dry-run mode for safety

terraform {
  required_version = ">= 1.2"

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
  version = "~> 1.0"

  # Enable Compute Savings Plans only
  enable_compute_sp  = true
  enable_database_sp = false

  # Coverage strategy - conservative targets
  coverage_target_percent = 80 # Target 80% coverage
  max_coverage_cap        = 90 # Never exceed 90% coverage

  # Risk management - gradual commitment growth
  max_purchase_percent = 5  # Max 5% of monthly spend per cycle
  lookback_days        = 30 # 30 days of usage history
  min_data_days        = 14 # Require at least 14 days of data

  # Compute SP configuration
  compute_sp_term_mix = {
    three_year = 0.70 # 70% in 3-year plans (higher discount)
    one_year   = 0.30 # 30% in 1-year plans (more flexibility)
  }
  compute_sp_payment_option = "ALL_UPFRONT" # Maximum savings

  # Scheduling - 3-day review window
  scheduler_schedule = "cron(0 8 1 * ? *)" # 1st of month at 8:00 AM UTC
  purchaser_schedule = "cron(0 8 4 * ? *)" # 4th of month at 8:00 AM UTC

  # Notifications
  notification_emails = [
    "devops@example.com",
    "finops@example.com"
  ]

  # Operations
  dry_run              = true # Start in dry-run mode - emails only
  send_no_action_email = true # Get notified even when no action needed

  # Monitoring
  enable_lambda_error_alarm = true
  enable_dlq_alarm          = true
  lambda_error_threshold    = 1

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
