# Test Fixture: Basic Configuration
# Purpose: Minimal configuration for integration testing

terraform {
  required_version = ">= 1.2"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ============================================================================
# Provider Configuration
# ============================================================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "test"
      TestFixture = "basic"
      ManagedBy   = "terratest"
    }
  }
}

# ============================================================================
# Module Under Test
# ============================================================================

module "sp_autopilot" {
  source = "../../.."

  # Savings Plan Types
  enable_compute_sp  = var.enable_compute_sp
  enable_database_sp = var.enable_database_sp

  # Coverage Strategy
  coverage_target_percent = var.coverage_target_percent
  max_coverage_cap        = var.max_coverage_cap
  lookback_days           = var.lookback_days

  # Risk Management
  max_purchase_percent    = var.max_purchase_percent
  min_data_days           = var.min_data_days
  min_commitment_per_plan = var.min_commitment_per_plan

  # Expiring Plans
  renewal_window_days = var.renewal_window_days

  # Compute SP Options
  compute_sp_term_mix       = var.compute_sp_term_mix
  compute_sp_payment_option = var.compute_sp_payment_option
  partial_upfront_percent   = var.partial_upfront_percent

  # Database SP Options (AWS constraints: ONE_YEAR, NO_UPFRONT)
  database_sp_term           = var.database_sp_term
  database_sp_payment_option = var.database_sp_payment_option

  # Scheduling
  scheduler_schedule = var.scheduler_schedule
  purchaser_schedule = var.purchaser_schedule

  # Operations
  dry_run              = var.dry_run
  send_no_action_email = var.send_no_action_email

  # Notifications
  notification_emails = var.notification_emails

  # Monitoring
  enable_lambda_error_alarm = var.enable_lambda_error_alarm
  enable_dlq_alarm          = var.enable_dlq_alarm

  # Cross-Account
  management_account_role_arn = var.management_account_role_arn

  # Tagging
  tags = var.tags
}
