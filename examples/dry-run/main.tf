# Conservative Dry-Run Evaluation
#
# This example demonstrates the safest way to evaluate AWS Savings Plans automation:
# - Dry-run mode enabled (NO actual purchases)
# - Ultra-conservative coverage targets
# - Email-only notifications to evaluate recommendations
# - Perfect for initial evaluation and building confidence
#
# Use this configuration to:
# - Understand your usage patterns
# - See what AWS recommends
# - Evaluate potential savings
# - Build confidence before enabling purchases

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
  version = "~> 1.0"

  # Enable Compute Savings Plans only (simplest starting point)
  enable_compute_sp  = true
  enable_database_sp = false

  # Ultra-conservative coverage targets for evaluation
  coverage_target_percent = 60 # Very conservative 60% target
  max_coverage_cap        = 70 # Low ceiling to limit exposure

  # Minimal purchase limits (won't be used in dry-run, but sets expectations)
  max_purchase_percent = 3  # Only 3% of monthly spend per cycle
  lookback_days        = 30 # 30 days of usage history
  min_data_days        = 21 # Require 3 weeks of data for confidence

  # Conservative compute SP configuration
  compute_sp_term_mix = {
    three_year = 0.50 # 50/50 split for flexibility
    one_year   = 0.50
  }
  compute_sp_payment_option = "PARTIAL_UPFRONT" # Balance between savings and cash flow

  # Extended review window (though not used in dry-run)
  scheduler_schedule = "cron(0 8 1 * ? *)" # 1st of month at 8:00 AM UTC
  purchaser_schedule = "cron(0 8 8 * ? *)" # 8th of month at 8:00 AM UTC (7-day window)

  # Notifications - evaluation reports sent here
  notification_emails = [
    "finops@example.com" # Replace with your email for evaluation reports
  ]

  # DRY-RUN MODE - THE CRITICAL SETTING
  dry_run              = true # KEEPS THIS SAFE - emails only, no purchases
  send_no_action_email = true # Get reports even when no action recommended

  # Monitoring (for infrastructure health only)
  enable_lambda_error_alarm = true
  enable_dlq_alarm          = true
  lambda_error_threshold    = 1

  # Tagging
  tags = {
    Environment = "evaluation"
    ManagedBy   = "terraform"
    Purpose     = "savings-plans-evaluation"
    Mode        = "dry-run"
  }
}

# Outputs for monitoring evaluation infrastructure
output "scheduler_lambda_name" {
  description = "Name of the scheduler Lambda (use to trigger manual evaluations)"
  value       = module.savings_plans.scheduler_lambda_name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for evaluation reports"
  value       = module.savings_plans.sns_topic_arn
}

output "module_configuration" {
  description = "Summary of module configuration"
  value       = module.savings_plans.module_configuration
}

output "dry_run_status" {
  description = "Confirms dry-run mode is enabled (should be true)"
  value       = true # Hardcoded reminder that this is a dry-run example
}
