# Dichotomy Purchase Strategy Example
#
# This example demonstrates the dichotomy purchase strategy, which uses
# exponentially decreasing purchase sizes based on coverage gap:
#
# Strategy Behavior (max_purchase_percent = 50%, target = 90%, min = 1%):
# - Month 1: At 0% → Try 50% (0+50=50% ✓) → Purchase 50%
# - Month 2: At 50% → Try 50% (100%) ✗ → Try 25% (75% ✓) → Purchase 25%
# - Month 3: At 75% → Try 50% ✗ → Try 25% (100%) ✗ → Try 12.5% (87.5% ✓) → Purchase 12.5%
# - Month 4: At 87.5% → Keep halving until fits → Purchase 1.6% (rounded from 1.5625%)
#
# Benefits:
# - Adaptive purchase sizing based on coverage gap
# - Creates stable, distributed commitments over time
# - Natural replacement of large expiring plans with smaller purchases
# - Prevents over-commitment through exponential halving

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

  # Resource naming (can be overridden for testing)
  name_prefix = var.name_prefix

  # Purchase strategy - DICHOTOMY for adaptive sizing
  purchase_strategy = {
    coverage_target_percent = 90 # Target 90% coverage
    max_coverage_cap        = 95 # Safety cap at 95%
    lookback_days           = 30 # 30 days of usage history
    min_data_days           = 14 # Require at least 14 days of data

    # Dichotomy strategy - exponentially decreasing purchase sizes
    dichotomy = {
      max_purchase_percent = 50 # Start at 50% of AWS recommendation
      min_purchase_percent = 1  # Minimum purchase granularity (never buy less)
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
    Strategy    = "dichotomy"
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
# Assuming $100/hour on-demand spend:
#
# Month 1:
# - Current coverage: 0%
# - Try: 50% → 0+50=50% ✓
# - AWS recommendation: $90/hour
# - Purchase: $45/hour (50% of $90)
# - New coverage: 50%
#
# Month 2:
# - Current coverage: 50%
# - Try: 50% (100%) ✗ → 25% (75%) ✓
# - AWS recommendation: $40/hour
# - Purchase: $10/hour (25% of $40)
# - New coverage: 75%
#
# Month 3:
# - Current coverage: 75%
# - Try: 50% ✗ → 25% (100%) ✗ → 12.5% (87.5%) ✓
# - AWS recommendation: $13.50/hour
# - Purchase: $1.69/hour (12.5% of $13.50)
# - New coverage: 87.5%
#
# Month 4:
# - Current coverage: 87.5%
# - Try: Keep halving → 1.5625% → round to 1.6% ✓
# - AWS recommendation: $2.50/hour
# - Purchase: $0.04/hour (1.6% of $2.50)
# - New coverage: 89.1%
#
# ...continues until 90% target reached
