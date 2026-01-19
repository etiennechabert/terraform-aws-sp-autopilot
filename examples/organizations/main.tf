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

  # Purchase strategy - production targets for organization
  purchase_strategy = {
    coverage_target_percent = 85 # Target 85% coverage across organization
    max_coverage_cap        = 95 # Hard cap at 95% to maintain flexibility
    lookback_days           = 30 # 30 days of usage history
    min_data_days           = 14 # Require at least 14 days of data

    # Moderate commitment growth for organization
    fixed = {
      max_purchase_percent = 8 # Max 8% of monthly org spend per cycle
    }
  }

  # Savings Plans configuration - both Compute and Database for comprehensive coverage
  sp_plans = {
    compute = {
      enabled                = true
      all_upfront_three_year = 0.67 # 67% in 3-year all-upfront (higher discount)
      all_upfront_one_year   = 0.33 # 33% in 1-year all-upfront (flexibility for growth)
    }

    database = {
      enabled             = true
      no_upfront_one_year = 1 # AWS constraint: only 1-year NO_UPFRONT available
    }

    sagemaker = {
      enabled = false
    }
  }

  # Scheduling - spread evenly across the month
  scheduler = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month at 8:00 AM UTC
    purchaser = "cron(0 8 10 * ? *)" # 10th of month at 8:00 AM UTC (9-day review window)
    reporter  = "cron(0 9 20 * ? *)" # 20th of month at 9:00 AM UTC
  }

  # Notifications - multiple stakeholders for org-wide changes
  notifications = {
    emails = [
      "finops@example.com",           # FinOps team
      "cloud-governance@example.com", # Cloud governance team
      "aws-admins@example.com"        # AWS administrators
    ]
    send_no_action = true # Get notified even when no action needed
  }

  # Reporting
  reporting = {
    enabled       = true
    format        = "html"
    email_reports = true # Email reports to stakeholders
  }

  # Monitoring - critical for organization-level automation
  monitoring = {
    dlq_alarm       = true
    error_threshold = 1
  }

  # Lambda configuration - AWS Organizations cross-account roles with error alarms
  # Each Lambda can assume a different role in the management account
  lambda_config = {
    scheduler = {
      dry_run         = true # Start in dry-run mode - emails only
      assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansSchedulerRole"
      error_alarm     = true
    }
    purchaser = {
      # Role to assume for Savings Plans purchase operations
      assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansPurchaserRole"
      error_alarm     = true
    }
    reporter = {
      # Role to assume for Cost Explorer read operations
      assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansReporterRole"
      error_alarm     = true
    }
  }

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
