# AWS Organizations - Enterprise Deployment
#
# This example demonstrates deploying Savings Plans automation across an
# AWS Organization:
# - Organization-wide Savings Plans (management account role)
# - Both Compute and Database Savings Plans
# - Production-grade coverage targets
# - Comprehensive monitoring and notifications
# - Deployed from a delegated administrator or management account

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

  # Enable both Compute and Database Savings Plans for comprehensive coverage
  enable_compute_sp  = true
  enable_database_sp = true

  # Coverage strategy - production targets
  coverage_target_percent = 85 # Target 85% coverage across organization
  max_coverage_cap        = 95 # Hard cap at 95% to maintain flexibility

  # Risk management - moderate commitment growth
  max_purchase_percent = 8  # Max 8% of monthly org spend per cycle
  lookback_days        = 30 # 30 days of usage history
  min_data_days        = 14 # Require at least 14 days of data

  # Compute SP configuration - balanced approach
  compute_sp_term_mix = {
    three_year = 0.67 # 67% in 3-year plans (higher discount)
    one_year   = 0.33 # 33% in 1-year plans (flexibility for growth)
  }
  compute_sp_payment_option = "ALL_UPFRONT" # Maximum savings

  # Database SP configuration (AWS constraints: 1-year, No Upfront only)
  # database_sp_term = "ONE_YEAR"           # Fixed by AWS
  # database_sp_payment_option = "NO_UPFRONT"  # Fixed by AWS

  # AWS Organizations - assume role in management account
  # This role must exist in the management account with permissions for:
  # - ce:GetSavingsPlansPurchaseRecommendation
  # - savingsplans:CreateSavingsPlan
  # - savingsplans:DescribeSavingsPlans
  management_account_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansAutomationRole"

  # Scheduling - 5-day review window for organization-level changes
  scheduler_schedule = "cron(0 8 1 * ? *)" # 1st of month at 8:00 AM UTC
  purchaser_schedule = "cron(0 8 6 * ? *)" # 6th of month at 8:00 AM UTC

  # Notifications - multiple stakeholders for org-wide changes
  notification_emails = [
    "finops@example.com",           # FinOps team
    "cloud-governance@example.com", # Cloud governance team
    "aws-admins@example.com"        # AWS administrators
  ]

  # Operations
  dry_run              = true # Start in dry-run mode - emails only
  send_no_action_email = true # Get notified even when no action needed

  # Monitoring - critical for organization-level automation
  enable_lambda_error_alarm = true
  enable_dlq_alarm          = true
  lambda_error_threshold    = 1

  # Tagging - organization standards
  tags = {
    Environment        = "production"
    ManagedBy          = "terraform"
    Purpose            = "savings-plans-automation"
    Scope              = "organization"
    CostCenter         = "shared-services"
    DataClassification = "internal"
    Compliance         = "finops-approved"
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
