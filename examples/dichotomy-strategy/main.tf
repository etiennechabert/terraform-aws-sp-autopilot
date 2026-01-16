# Dichotomy Purchase Strategy Example
#
# This example demonstrates the dichotomy purchase strategy, which uses
# exponentially decreasing purchase sizes based on coverage gap:
#
# Strategy Behavior (max_purchase_percent = 50%, target = 90%):
# - Month 1: Coverage 0% → Gap 90% → Purchase 50% (max)
# - Month 2: Coverage 50% → Gap 40% → Purchase 25% (halved)
# - Month 3: Coverage 75% → Gap 15% → Purchase 12.5% (halved again)
# - Month 4: Coverage 87.5% → Gap 2.5% → Purchase 2.5% (exact gap)
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
  version = "~> 2.0"

  # Purchase strategy - DICHOTOMY for adaptive sizing
  purchase_strategy = {
    coverage_target_percent = 90 # Target 90% coverage
    max_coverage_cap        = 95 # Safety cap at 95%
    lookback_days           = 30 # 30 days of usage history
    min_data_days           = 14 # Require at least 14 days of data

    # Dichotomy strategy - exponentially decreasing purchase sizes
    dichotomy = {
      max_purchase_percent = 50 # Start at 50% of AWS recommendation
      min_purchase_percent = 1  # Don't purchase below 1%
    }
  }

  # Savings Plans configuration - Compute with balanced term mix
  sp_plans = {
    compute = {
      enabled                = true
      all_upfront_three_year = 0.50 # 50% in 3-year all-upfront
      all_upfront_one_year   = 0.30 # 30% in 1-year all-upfront
      partial_upfront_one_year = 0.20 # 20% in 1-year partial-upfront
      partial_upfront_percent = 60  # Pay 60% upfront for partial plans
    }

    database = {
      enabled = false
    }

    sagemaker = {
      enabled = false
    }
  }

  # Scheduling - monthly automation cycle
  scheduler = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month - analyze usage
    purchaser = "cron(0 8 4 * ? *)"  # 4th of month - execute purchases (3-day review)
    reporter  = "cron(0 9 1 * ? *)"  # 1st of month - generate reports
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

  # Lambda configuration - purchaser enabled for production use
  lambda_config = {
    scheduler = {
      dry_run     = false # Production mode - queue purchases
      error_alarm = true
    }
    purchaser = {
      enabled     = true # Enable purchaser Lambda
      error_alarm = true
    }
    reporter = {
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
# - Coverage gap: 90%
# - Dichotomy purchase %: 50% (max)
# - AWS recommendation: $90/hour
# - Purchase: $45/hour (50% of $90)
# - New coverage: 50%
#
# Month 2:
# - Current coverage: 50%
# - Coverage gap: 40%
# - Dichotomy purchase %: 25% (halved)
# - AWS recommendation: $40/hour
# - Purchase: $10/hour (25% of $40)
# - New coverage: 60%
#
# Month 3:
# - Current coverage: 60%
# - Coverage gap: 30%
# - Dichotomy purchase %: 25%
# - AWS recommendation: $30/hour
# - Purchase: $7.50/hour (25% of $30)
# - New coverage: 67.5%
#
# ...continues until 90% target reached
