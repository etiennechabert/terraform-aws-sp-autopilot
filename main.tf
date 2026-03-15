# Main configuration - data sources and local variables
#
# This module is organized into domain-specific files:
#   sns.tf, sqs.tf, s3.tf, lambda.tf, iam.tf, cloudwatch.tf, eventbridge.tf, outputs.tf, variables.tf


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

  database_enabled   = var.sp_plans.database.enabled
  database_plan_type = var.sp_plans.database.plan_type

  # Parse plan_type into term and payment_option (same pattern as compute/sagemaker)
  database_sp_term = local.database_enabled ? (
    strcontains(local.database_plan_type, "three_year") ? "THREE_YEAR" : "ONE_YEAR"
  ) : "ONE_YEAR"

  database_sp_payment_option = local.database_enabled ? (
    strcontains(local.database_plan_type, "all_upfront") ? "ALL_UPFRONT" :
    strcontains(local.database_plan_type, "partial_upfront") ? "PARTIAL_UPFRONT" :
    "NO_UPFRONT"
  ) : "NO_UPFRONT"

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

  # Target Strategy

  target_strategy_type = (
    var.purchase_strategy.target.aws != null ? "aws" :
    "dynamic"
  )

  # Split Strategy

  split_strategy_type = (
    var.purchase_strategy.split.one_shot != null ? "one_shot" :
    var.purchase_strategy.split.fixed_step != null ? "fixed_step" :
    var.purchase_strategy.split.gap_split != null ? "gap_split" :
    "one_shot" # unreachable - validation ensures exactly one split is defined
  )

  # Coverage target (dynamic/aws targets resolve at runtime)
  coverage_target_percent = 90.0

  # Dynamic risk level
  dynamic_risk_level = (
    local.target_strategy_type == "dynamic" ?
    var.purchase_strategy.target.dynamic.risk_level :
    ""
  )

  # Prudent percentage (configurable, default 85%)
  prudent_percentage = (
    local.target_strategy_type == "dynamic" ?
    var.purchase_strategy.target.dynamic.prudent_percentage :
    85
  )

  # Split strategy params
  fixed_step_percent = (
    local.split_strategy_type == "fixed_step" ?
    try(var.purchase_strategy.split.fixed_step.step_percent, 10.0) :
    10.0
  )

  max_purchase_percent = (
    local.split_strategy_type == "fixed_step" ?
    local.fixed_step_percent :
    local.split_strategy_type == "gap_split" ?
    try(var.purchase_strategy.split.gap_split.max_purchase_percent, null) != null ?
    var.purchase_strategy.split.gap_split.max_purchase_percent : 100.0 :
    100.0
  )

  min_purchase_percent = (
    local.split_strategy_type == "gap_split" ?
    try(var.purchase_strategy.split.gap_split.min_purchase_percent, 1.0) :
    1.0
  )

  gap_split_divider = (
    local.split_strategy_type == "gap_split" ?
    try(var.purchase_strategy.split.gap_split.divider, 2.0) :
    2.0
  )

  # Notification Settings

  notification_emails = var.notifications.emails
  slack_webhook_url   = try(var.notifications.slack_webhook, null)
  teams_webhook_url   = try(var.notifications.teams_webhook, null)

  # Reporting Settings

  report_format      = try(var.reporting.format, "html")
  email_reports      = try(var.reporting.email_reports, false)
  include_debug_data = try(var.reporting.include_debug_data, false)

  s3_lifecycle_transition_ia_days         = try(var.reporting.s3_lifecycle.transition_ia_days, 90)
  s3_lifecycle_transition_glacier_days    = try(var.reporting.s3_lifecycle.transition_glacier_days, 180)
  s3_lifecycle_expiration_days            = try(var.reporting.s3_lifecycle.expiration_days, 365)
  s3_lifecycle_noncurrent_expiration_days = try(var.reporting.s3_lifecycle.noncurrent_expiration_days, 90)

  # Monitoring Settings

  enable_dlq_alarm          = try(var.monitoring.dlq_alarm, true)
  lambda_error_threshold    = try(var.monitoring.error_threshold, 1)
  low_utilization_threshold = try(var.monitoring.low_utilization_threshold, 70)

  # Scheduling (null = disabled)

  scheduler_schedule = var.cron_schedules.scheduler # Can be null to disable
  purchaser_schedule = var.cron_schedules.purchaser # Can be null to disable
  report_schedule    = var.cron_schedules.reporter  # Can be null to disable

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

  renewal_window_days     = try(var.purchase_strategy.renewal_window_days, 7)
  purchase_cooldown_days  = try(var.purchase_strategy.purchase_cooldown_days, 7)
  min_commitment_per_plan = try(var.purchase_strategy.min_commitment_per_plan, 0.001)

  # Decline Check Settings

  spike_guard_enabled             = try(var.purchase_strategy.spike_guard.enabled, true)
  spike_guard_long_lookback_days  = try(var.purchase_strategy.spike_guard.long_lookback_days, 90)
  spike_guard_short_lookback_days = try(var.purchase_strategy.spike_guard.short_lookback_days, 14)
  spike_guard_threshold_percent   = try(var.purchase_strategy.spike_guard.threshold_percent, 20)

  # Encryption Settings

  sns_kms_key = try(var.encryption.sns_kms_key, "alias/aws/sns")
  sqs_kms_key = try(var.encryption.sqs_kms_key, "alias/aws/sqs")
  s3_kms_key  = try(var.encryption.s3.kms_key, null) # null = AES256, otherwise SSE-KMS
}
