# Data sources and local variables


data "aws_caller_identity" "current" {}

data "aws_region" "current" {}


locals {
  # Common Tags

  common_tags = merge(
    {
      ManagedBy = "terraform-aws-sp-autopilot"
      Module    = "savings-plans-automation"
    },
    var.tags
  )

  # Module name for resource naming (from name_prefix variable)
  module_name = var.name_prefix

  # Lambda Enable Flags

  lambda_scheduler_enabled = try(var.lambda_config.scheduler.enabled, true)
  lambda_purchaser_enabled = try(var.lambda_config.purchaser.enabled, true)
  lambda_reporter_enabled  = try(var.lambda_config.reporter.enabled, true)

  # Per-Lambda error alarm flags
  lambda_scheduler_error_alarm_enabled = try(var.lambda_config.scheduler.error_alarm, true)
  lambda_purchaser_error_alarm_enabled = try(var.lambda_config.purchaser.error_alarm, true)
  lambda_reporter_error_alarm_enabled  = try(var.lambda_config.reporter.error_alarm, true)

  # Compute SP Configuration

  compute_enabled   = var.sp_plans.compute.enabled
  compute_plan_type = var.sp_plans.compute.plan_type # Guaranteed non-null when enabled=true by validation

  # Parse plan_type into term and payment_option
  compute_term = local.compute_enabled ? (
    strcontains(local.compute_plan_type, "three_year") ? "THREE_YEAR" : "ONE_YEAR"
  ) : "THREE_YEAR"

  compute_payment_option = local.compute_enabled ? (
    strcontains(local.compute_plan_type, "all_upfront") ? "ALL_UPFRONT" :
    strcontains(local.compute_plan_type, "partial_upfront") ? "PARTIAL_UPFRONT" :
    "NO_UPFRONT"
  ) : "ALL_UPFRONT"

  # Database SP Configuration

  database_enabled           = var.sp_plans.database.enabled
  database_plan_type         = var.sp_plans.database.plan_type # Guaranteed "no_upfront_one_year" when enabled=true
  database_sp_term           = "ONE_YEAR"                      # AWS constraint
  database_sp_payment_option = "NO_UPFRONT"                    # AWS constraint

  # SageMaker SP Configuration

  sagemaker_enabled   = var.sp_plans.sagemaker.enabled
  sagemaker_plan_type = var.sp_plans.sagemaker.plan_type # Guaranteed non-null when enabled=true by validation

  # Parse plan_type into term and payment_option
  sagemaker_term = local.sagemaker_enabled ? (
    strcontains(local.sagemaker_plan_type, "three_year") ? "THREE_YEAR" : "ONE_YEAR"
  ) : "THREE_YEAR"

  sagemaker_payment_option = local.sagemaker_enabled ? (
    strcontains(local.sagemaker_plan_type, "all_upfront") ? "ALL_UPFRONT" :
    strcontains(local.sagemaker_plan_type, "partial_upfront") ? "PARTIAL_UPFRONT" :
    "NO_UPFRONT"
  ) : "ALL_UPFRONT"

  # Purchase Strategy

  purchase_strategy_type = (
    var.purchase_strategy.follow_aws != null ? "follow_aws" :
    var.purchase_strategy.fixed != null ? "fixed" :
    var.purchase_strategy.dichotomy != null ? "dichotomy" :
    "follow_aws" # default
  )

  max_purchase_percent = (
    local.purchase_strategy_type == "follow_aws" ? 100.0 :
    local.purchase_strategy_type == "fixed" ?
    var.purchase_strategy.fixed.max_purchase_percent :
    var.purchase_strategy.dichotomy.max_purchase_percent
  )

  min_purchase_percent = (
    local.purchase_strategy_type == "dichotomy" ?
    var.purchase_strategy.dichotomy.min_purchase_percent :
    1.0 # default for other strategies (not used, but included for consistency)
  )

  # Scheduler Dry-Run Mode

  dry_run = try(var.lambda_config.scheduler.dry_run, false)

  # Notification Settings

  notification_emails  = var.notifications.emails
  slack_webhook_url    = try(var.notifications.slack_webhook, null)
  teams_webhook_url    = try(var.notifications.teams_webhook, null)
  send_no_action_email = try(var.notifications.send_no_action, true)

  # Reporting Settings

  enable_reports        = try(var.reporting.enabled, true)
  report_format         = try(var.reporting.format, "html")
  email_reports         = try(var.reporting.email_reports, false)
  report_retention_days = try(var.reporting.retention_days, 365)

  s3_lifecycle_transition_ia_days         = try(var.reporting.s3_lifecycle.transition_ia_days, 90)
  s3_lifecycle_transition_glacier_days    = try(var.reporting.s3_lifecycle.transition_glacier_days, 180)
  s3_lifecycle_expiration_days            = try(var.reporting.s3_lifecycle.expiration_days, 365)
  s3_lifecycle_noncurrent_expiration_days = try(var.reporting.s3_lifecycle.noncurrent_expiration_days, 90)

  # Monitoring Settings

  enable_dlq_alarm          = try(var.monitoring.dlq_alarm, true)
  lambda_error_threshold    = try(var.monitoring.error_threshold, 1)
  low_utilization_threshold = try(var.monitoring.low_utilization_threshold, 70)

  # Scheduling (null = disabled)

  scheduler_schedule = var.scheduler.scheduler # Can be null to disable
  purchaser_schedule = var.scheduler.purchaser # Can be null to disable
  report_schedule    = var.scheduler.reporter  # Can be null to disable

  # Lambda Configuration

  lambda_scheduler_memory_size     = try(var.lambda_config.scheduler.memory_mb, 128)
  lambda_scheduler_timeout         = try(var.lambda_config.scheduler.timeout, 300)
  lambda_scheduler_assume_role_arn = try(var.lambda_config.scheduler.assume_role_arn, null)

  lambda_purchaser_memory_size     = try(var.lambda_config.purchaser.memory_mb, 128)
  lambda_purchaser_timeout         = try(var.lambda_config.purchaser.timeout, 300)
  lambda_purchaser_assume_role_arn = try(var.lambda_config.purchaser.assume_role_arn, null)

  lambda_reporter_memory_size     = try(var.lambda_config.reporter.memory_mb, 128)
  lambda_reporter_timeout         = try(var.lambda_config.reporter.timeout, 300)
  lambda_reporter_assume_role_arn = try(var.lambda_config.reporter.assume_role_arn, null)

  # Purchase Strategy Settings (extract from nested object)

  coverage_target_percent = var.purchase_strategy.coverage_target_percent
  max_coverage_cap        = var.purchase_strategy.max_coverage_cap
  lookback_days           = try(var.purchase_strategy.lookback_days, 30)
  min_data_days           = try(var.purchase_strategy.min_data_days, 14)
  granularity             = try(var.purchase_strategy.granularity, "HOURLY")
  renewal_window_days     = try(var.purchase_strategy.renewal_window_days, 7)
  min_commitment_per_plan = try(var.purchase_strategy.min_commitment_per_plan, 0.001)

  # Encryption Settings

  sns_kms_key           = try(var.encryption.sns_kms_key, "alias/aws/sns")
  sqs_kms_key           = try(var.encryption.sqs_kms_key, "alias/aws/sqs")
  s3_encryption_enabled = try(var.encryption.s3.enabled, true)
  s3_kms_key            = try(var.encryption.s3.kms_key, null) # null = AES256, otherwise SSE-KMS
}
