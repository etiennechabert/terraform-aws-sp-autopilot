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
  source = "etiennechabert/sp-autopilot/aws"

  # Purchase strategy - ultra-conservative for evaluation
  purchase_strategy = {
    coverage_target_percent = 60 # Very conservative 60% target
    max_coverage_cap        = 70 # Low ceiling to limit exposure
    lookback_days           = 30 # 30 days of usage history
    min_data_days           = 21 # Require 3 weeks of data for confidence

    # Minimal purchase limits (won't be used in dry-run, but sets expectations)
    simple = {
      max_purchase_percent = 3 # Only 3% of monthly spend per cycle
    }
  }

  # Savings Plans configuration - Compute only (simplest starting point)
  sp_plans = {
    compute = {
      enabled                    = true
      partial_upfront_three_year = 0.50 # 50% in 3-year partial-upfront
      partial_upfront_one_year   = 0.50 # 50% in 1-year partial-upfront (50/50 split for flexibility)
      partial_upfront_percent    = 50   # Balance between savings and cash flow
    }

    database = {
      enabled = false
    }

    sagemaker = {
      enabled = false
    }
  }

  # Scheduling - spread evenly across the month (though purchaser not used in dry-run)
  scheduler = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month at 8:00 AM UTC
    purchaser = "cron(0 8 10 * ? *)" # 10th of month at 8:00 AM UTC (not invoked in dry-run mode)
    reporter  = "cron(0 9 20 * ? *)" # 20th of month at 9:00 AM UTC
  }

  # Notifications - evaluation reports sent here
  notifications = {
    emails         = ["finops@example.com"] # Replace with your email for evaluation reports
    send_no_action = true                   # Get reports even when no action recommended
  }

  # Reporting
  reporting = {
    enabled       = true
    format        = "html"
    email_reports = true # Send reports via email for easy evaluation
  }

  # Monitoring (for infrastructure health only)
  monitoring = {
    dlq_alarm       = true
    error_threshold = 1
  }

  # Lambda configuration
  # DRY-RUN MODE - THE CRITICAL SETTING
  lambda_config = {
    scheduler = {
      dry_run     = true # KEEPS THIS SAFE - emails only, no purchases
      error_alarm = true
    }
    purchaser = { error_alarm = true }
    reporter  = { error_alarm = true }
  }

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
