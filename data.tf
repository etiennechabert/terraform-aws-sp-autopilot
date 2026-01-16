# AWS Savings Plans Automation Module
# Version: 2.0 - Refactored with transformation locals
# Purpose: Data sources and local variables

# ============================================================================
# Data Sources
# ============================================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# ============================================================================
# Local Variables - Transformation from Nested to Flat Structure
# ============================================================================

locals {
  # ==========================================================================
  # Common Tags
  # ==========================================================================

  common_tags = merge(
    {
      ManagedBy = "terraform-aws-sp-autopilot"
      Module    = "savings-plans-automation"
    },
    var.tags
  )

  # Module name for resource naming
  module_name = "sp-autopilot"

  # ==========================================================================
  # Lambda Enable Flags
  # ==========================================================================

  lambda_scheduler_enabled = try(var.lambda_config.scheduler.enabled, true)
  lambda_purchaser_enabled = try(var.lambda_config.purchaser.enabled, true)
  lambda_reporter_enabled  = try(var.lambda_config.reporter.enabled, true)

  # Per-Lambda error alarm flags
  lambda_scheduler_error_alarm_enabled = try(var.lambda_config.scheduler.error_alarm, true)
  lambda_purchaser_error_alarm_enabled = try(var.lambda_config.purchaser.error_alarm, true)
  lambda_reporter_error_alarm_enabled  = try(var.lambda_config.reporter.error_alarm, true)

  # ==========================================================================
  # Compute SP Configuration
  # ==========================================================================

  compute_enabled = try(var.sp_plans.compute.enabled, false)

  # Calculate term mix (sum of all 3-year options vs sum of all 1-year options)
  compute_term_mix = local.compute_enabled ? {
    three_year = try(
      var.sp_plans.compute.all_upfront_three_year +
      var.sp_plans.compute.partial_upfront_three_year +
      var.sp_plans.compute.no_upfront_three_year,
      0
    )
    one_year = try(
      var.sp_plans.compute.all_upfront_one_year +
      var.sp_plans.compute.partial_upfront_one_year +
      var.sp_plans.compute.no_upfront_one_year,
      0
    )
  } : { three_year = 0, one_year = 0 }

  # Determine dominant payment option (highest percentage)
  # Note: This is a simplification. If user mixes payment types, we pick the dominant one.
  # Future: Lambda code could support mixed payment options
  compute_all_upfront_total = try(
    var.sp_plans.compute.all_upfront_three_year + var.sp_plans.compute.all_upfront_one_year, 0
  )
  compute_partial_upfront_total = try(
    var.sp_plans.compute.partial_upfront_three_year + var.sp_plans.compute.partial_upfront_one_year, 0
  )
  compute_no_upfront_total = try(
    var.sp_plans.compute.no_upfront_three_year + var.sp_plans.compute.no_upfront_one_year, 0
  )

  compute_payment_option = local.compute_enabled ? (
    local.compute_all_upfront_total >= local.compute_partial_upfront_total &&
    local.compute_all_upfront_total >= local.compute_no_upfront_total ? "ALL_UPFRONT" :
    local.compute_partial_upfront_total >= local.compute_no_upfront_total ? "PARTIAL_UPFRONT" :
    "NO_UPFRONT"
  ) : "ALL_UPFRONT"

  compute_partial_upfront_percent = try(var.sp_plans.compute.partial_upfront_percent, 50)

  # ==========================================================================
  # Database SP Configuration
  # ==========================================================================

  database_enabled           = try(var.sp_plans.database.enabled, false)
  database_sp_term           = "ONE_YEAR"   # AWS constraint
  database_sp_payment_option = "NO_UPFRONT" # AWS constraint

  # ==========================================================================
  # SageMaker SP Configuration
  # ==========================================================================

  sagemaker_enabled = try(var.sp_plans.sagemaker.enabled, false)

  sagemaker_term_mix = local.sagemaker_enabled ? {
    three_year = try(
      var.sp_plans.sagemaker.all_upfront_three_year +
      var.sp_plans.sagemaker.partial_upfront_three_year +
      var.sp_plans.sagemaker.no_upfront_three_year,
      0
    )
    one_year = try(
      var.sp_plans.sagemaker.all_upfront_one_year +
      var.sp_plans.sagemaker.partial_upfront_one_year +
      var.sp_plans.sagemaker.no_upfront_one_year,
      0
    )
  } : { three_year = 0, one_year = 0 }

  sagemaker_all_upfront_total = try(
    var.sp_plans.sagemaker.all_upfront_three_year + var.sp_plans.sagemaker.all_upfront_one_year, 0
  )
  sagemaker_partial_upfront_total = try(
    var.sp_plans.sagemaker.partial_upfront_three_year + var.sp_plans.sagemaker.partial_upfront_one_year, 0
  )
  sagemaker_no_upfront_total = try(
    var.sp_plans.sagemaker.no_upfront_three_year + var.sp_plans.sagemaker.no_upfront_one_year, 0
  )

  sagemaker_payment_option = local.sagemaker_enabled ? (
    local.sagemaker_all_upfront_total >= local.sagemaker_partial_upfront_total &&
    local.sagemaker_all_upfront_total >= local.sagemaker_no_upfront_total ? "ALL_UPFRONT" :
    local.sagemaker_partial_upfront_total >= local.sagemaker_no_upfront_total ? "PARTIAL_UPFRONT" :
    "NO_UPFRONT"
  ) : "ALL_UPFRONT"

  sagemaker_partial_upfront_percent = try(var.sp_plans.sagemaker.partial_upfront_percent, 50)

  # ==========================================================================
  # Purchase Strategy
  # ==========================================================================

  purchase_strategy_type = (
    var.purchase_strategy.simple != null ? "simple" :
    var.purchase_strategy.dichotomy != null ? "dichotomy" :
    "simple" # default
  )

  max_purchase_percent = (
    local.purchase_strategy_type == "simple" ?
    var.purchase_strategy.simple.max_purchase_percent :
    var.purchase_strategy.dichotomy.max_purchase_percent
  )

  min_purchase_percent = (
    local.purchase_strategy_type == "dichotomy" ?
    var.purchase_strategy.dichotomy.min_purchase_percent :
    1.0 # default for simple strategy (not used, but included for consistency)
  )

  # ==========================================================================
  # Scheduler Dry-Run Mode
  # ==========================================================================

  dry_run = try(var.lambda_config.scheduler.dry_run, false)

  # ==========================================================================
  # Notification Settings
  # ==========================================================================

  notification_emails  = var.notifications.emails
  slack_webhook_url    = try(var.notifications.slack_webhook, null)
  teams_webhook_url    = try(var.notifications.teams_webhook, null)
  send_no_action_email = try(var.notifications.send_no_action, true)

  # ==========================================================================
  # Reporting Settings
  # ==========================================================================

  enable_reports        = try(var.reporting.enabled, true)
  report_format         = try(var.reporting.format, "html")
  email_reports         = try(var.reporting.email_reports, false)
  report_retention_days = try(var.reporting.retention_days, 365)

  s3_lifecycle_transition_ia_days         = try(var.reporting.s3_lifecycle.transition_ia_days, 90)
  s3_lifecycle_transition_glacier_days    = try(var.reporting.s3_lifecycle.transition_glacier_days, 180)
  s3_lifecycle_expiration_days            = try(var.reporting.s3_lifecycle.expiration_days, 365)
  s3_lifecycle_noncurrent_expiration_days = try(var.reporting.s3_lifecycle.noncurrent_expiration_days, 90)

  # ==========================================================================
  # Monitoring Settings
  # ==========================================================================

  enable_dlq_alarm       = try(var.monitoring.dlq_alarm, true)
  lambda_error_threshold = try(var.monitoring.error_threshold, 1)

  # ==========================================================================
  # Scheduling (null = disabled)
  # ==========================================================================

  scheduler_schedule = var.scheduler.scheduler # Can be null to disable
  purchaser_schedule = var.scheduler.purchaser # Can be null to disable
  report_schedule    = var.scheduler.reporter  # Can be null to disable

  # ==========================================================================
  # Lambda Configuration
  # ==========================================================================

  lambda_scheduler_memory_size     = try(var.lambda_config.scheduler.memory_mb, 128)
  lambda_scheduler_timeout         = try(var.lambda_config.scheduler.timeout, 300)
  lambda_scheduler_assume_role_arn = try(var.lambda_config.scheduler.assume_role_arn, null)

  lambda_purchaser_memory_size     = try(var.lambda_config.purchaser.memory_mb, 128)
  lambda_purchaser_timeout         = try(var.lambda_config.purchaser.timeout, 300)
  lambda_purchaser_assume_role_arn = try(var.lambda_config.purchaser.assume_role_arn, null)

  lambda_reporter_memory_size     = try(var.lambda_config.reporter.memory_mb, 128)
  lambda_reporter_timeout         = try(var.lambda_config.reporter.timeout, 300)
  lambda_reporter_assume_role_arn = try(var.lambda_config.reporter.assume_role_arn, null)

  # ==========================================================================
  # Purchase Strategy Settings (extract from nested object)
  # ==========================================================================

  coverage_target_percent = var.purchase_strategy.coverage_target_percent
  max_coverage_cap        = var.purchase_strategy.max_coverage_cap
  lookback_days           = try(var.purchase_strategy.lookback_days, 30)
  min_data_days           = try(var.purchase_strategy.min_data_days, 14)
  renewal_window_days     = try(var.purchase_strategy.renewal_window_days, 7)
  min_commitment_per_plan = try(var.purchase_strategy.min_commitment_per_plan, 0.001)

  # ==========================================================================
  # Encryption Settings
  # ==========================================================================

  sns_kms_key           = try(var.encryption.sns_kms_key, "alias/aws/sns")
  sqs_kms_key           = try(var.encryption.sqs_kms_key, "alias/aws/sqs")
  s3_encryption_enabled = try(var.encryption.s3.enabled, true)
  s3_kms_key            = try(var.encryption.s3.kms_key, null) # null = AES256, otherwise SSE-KMS
}
