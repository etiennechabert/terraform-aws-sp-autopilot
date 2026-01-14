# Single Account - Database Savings Plans Only
#
# This example demonstrates Database Savings Plans automation:
# - Single AWS account (no Organizations)
# - Database Savings Plans only (RDS, Aurora, DynamoDB, ElastiCache, etc.)
# - AWS-mandated constraints: 1-year term, No Upfront payment
# - Conservative coverage targets
# - Starts in dry-run mode for safety

terraform {
  required_version = ">= 1.0"

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
  version = "~> 1.0"

  # Enable Database Savings Plans only
  enable_compute_sp  = false
  enable_database_sp = true

  # Coverage strategy - conservative targets
  coverage_target_percent = 80  # Target 80% coverage
  max_coverage_cap        = 90  # Never exceed 90% coverage

  # Risk management - gradual commitment growth
  max_purchase_percent = 5      # Max 5% of monthly spend per cycle
  lookback_days        = 30     # 30 days of usage history
  min_data_days        = 14     # Require at least 14 days of data

  # Database SP configuration (AWS constraints - cannot be changed)
  # database_sp_term = "ONE_YEAR"           # Fixed: AWS only supports 1-year
  # database_sp_payment_option = "NO_UPFRONT"  # Fixed: AWS only supports no upfront

  # Scheduling - 3-day review window
  scheduler_schedule = "cron(0 8 1 * ? *)"  # 1st of month at 8:00 AM UTC
  purchaser_schedule = "cron(0 8 4 * ? *)"  # 4th of month at 8:00 AM UTC

  # Notifications
  notification_emails = [
    "database-team@example.com",
    "finops@example.com"
  ]

  # Operations
  dry_run              = true  # Start in dry-run mode - emails only
  send_no_action_email = true  # Get notified even when no action needed

  # Monitoring
  enable_lambda_error_alarm = true
  enable_dlq_alarm          = true
  lambda_error_threshold    = 1

  # Tagging
  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
    Purpose     = "database-savings-plans-automation"
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
