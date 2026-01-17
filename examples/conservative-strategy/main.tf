# Conservative Purchase Strategy Example
#
# This example demonstrates the conservative purchase strategy, which only
# purchases when the coverage gap exceeds a minimum threshold, reducing churn
# for stable workloads.
#
# Strategy Behavior (min_gap_threshold = 5%, max_purchase_percent = 50%):
# - Month 1: At 0% → Gap: 90% (>5%) → Purchase 50% of AWS recommendation
# - Month 2: At 87% → Gap: 3% (<5%) → No purchase (below threshold)
# - Month 3: At 84% → Gap: 6% (>5%) → Purchase 50% of AWS recommendation
# - Month 4: At 89% → Gap: 1% (<5%) → No purchase (below threshold)
#
# Benefits:
# - Reduces purchase churn when coverage is close to target
# - Prevents frequent small purchases for stable workloads
# - Simple threshold-based decision making
# - Configurable sensitivity via min_gap_threshold
# - Predictable purchase amounts via max_purchase_percent
#
# Use Cases:
# - Stable workloads with predictable usage patterns
# - When coverage naturally fluctuates around the target
# - Reducing administrative overhead from frequent purchases
# - Avoiding small purchases that don't materially impact coverage

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

  # Purchase strategy - CONSERVATIVE for threshold-based purchasing
  purchase_strategy = {
    coverage_target_percent = 90 # Target 90% coverage
    max_coverage_cap        = 95 # Safety cap at 95%
    lookback_days           = 30 # 30 days of usage history
    min_data_days           = 14 # Require at least 14 days of data

    # Conservative strategy - only purchase when gap exceeds threshold
    conservative = {
      min_gap_threshold    = 5.0 # Only purchase if coverage gap >= 5%
      max_purchase_percent = 50  # When purchasing, buy 50% of AWS recommendation
    }
  }

  # Savings Plans configuration - Compute with balanced term mix
  sp_plans = {
    compute = {
      enabled                  = true
      all_upfront_three_year   = 0.50 # 50% in 3-year all-upfront
      all_upfront_one_year     = 0.30 # 30% in 1-year all-upfront
      partial_upfront_one_year = 0.20 # 20% in 1-year partial-upfront
      partial_upfront_percent  = 60   # Pay 60% upfront for partial plans
    }

    database = {
      enabled = false
    }

    sagemaker = {
      enabled = false
    }
  }

  # Scheduling - monthly automation cycle (can be overridden for testing)
  scheduler = {
    scheduler = try(var.scheduler.scheduler, "cron(0 8 1 * ? *)") # 1st of month - analyze usage
    purchaser = try(var.scheduler.purchaser, "cron(0 8 4 * ? *)") # 4th of month - execute purchases (3-day review)
    reporter  = try(var.scheduler.reporter, "cron(0 9 1 * ? *)")  # 1st of month - generate reports
  }

  # Notifications
  notifications = {
    emails         = ["sre@example.com", "finops@example.com"]
    send_no_action = true
  }

  # Reporting
  reporting = {
    enabled        = true
    format         = "html"
    email_reports  = true
    retention_days = 365
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
    Strategy    = "conservative"
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

# Example progression simulation
# ===============================
# Assuming $100/hour on-demand spend, target 90%, threshold 5%:
#
# Month 1:
# - Current coverage: 0%
# - Coverage gap: 90% (target 90% - current 0%)
# - Gap >= 5% threshold? YES
# - AWS recommendation: $90/hour
# - Purchase: $45/hour (50% of $90)
# - New coverage: 50%
#
# Month 2:
# - Current coverage: 50%
# - Coverage gap: 40% (target 90% - current 50%)
# - Gap >= 5% threshold? YES
# - AWS recommendation: $40/hour
# - Purchase: $20/hour (50% of $40)
# - New coverage: 75%
#
# Month 3:
# - Current coverage: 75%
# - Coverage gap: 15% (target 90% - current 75%)
# - Gap >= 5% threshold? YES
# - AWS recommendation: $15/hour
# - Purchase: $7.50/hour (50% of $15)
# - New coverage: 87%
#
# Month 4:
# - Current coverage: 87%
# - Coverage gap: 3% (target 90% - current 87%)
# - Gap >= 5% threshold? NO
# - Action: Skip purchase (gap below threshold)
# - New coverage: 87% (unchanged)
#
# Month 5:
# - Current coverage: 84% (some plans expired)
# - Coverage gap: 6% (target 90% - current 84%)
# - Gap >= 5% threshold? YES
# - AWS recommendation: $6/hour
# - Purchase: $3/hour (50% of $6)
# - New coverage: 89%
#
# Month 6:
# - Current coverage: 89%
# - Coverage gap: 1% (target 90% - current 89%)
# - Gap >= 5% threshold? NO
# - Action: Skip purchase (gap below threshold)
# - New coverage: 89% (unchanged)
#
# This pattern continues, only purchasing when gap exceeds 5%, creating
# a stable coverage level with minimal purchase churn.
