# Module input variables

# Lambda Control & Configuration

variable "lambda_config" {
  description = "Lambda function configuration including enable/disable controls, performance settings, cross-account role ARNs, and error alarms"
  type = object({
    scheduler = optional(object({
      enabled         = optional(bool, true)
      memory_mb       = optional(number, 128)
      timeout         = optional(number, 300)
      assume_role_arn = optional(string)     # Role to assume for Cost Explorer and Savings Plans APIs (AWS Orgs)
      error_alarm     = optional(bool, true) # Enable CloudWatch error alarm for this Lambda
    }), {})

    purchaser = optional(object({
      enabled         = optional(bool, true)
      memory_mb       = optional(number, 128)
      timeout         = optional(number, 300)
      assume_role_arn = optional(string)     # Role to assume for Savings Plans purchase APIs (AWS Orgs)
      error_alarm     = optional(bool, true) # Enable CloudWatch error alarm for this Lambda
    }), {})

    reporter = optional(object({
      enabled         = optional(bool, true)
      memory_mb       = optional(number, 128)
      timeout         = optional(number, 300)
      assume_role_arn = optional(string)     # Role to assume for Cost Explorer and Savings Plans APIs (AWS Orgs)
      error_alarm     = optional(bool, true) # Enable CloudWatch error alarm for this Lambda
    }), {})
  })
  default = {}
}

# Purchase Strategy Configuration

variable "purchase_strategy" {
  description = "Purchase strategy configuration with orthogonal target + split dimensions"
  type = object({
    renewal_window_days     = optional(number, 14)
    purchase_cooldown_days  = optional(number, 7)
    min_commitment_per_plan = optional(number, 0.001)

    target = object({
      aws = optional(object({}))
      dynamic = optional(object({
        risk_level         = string
        prudent_percentage = optional(number, 85)
      }))
      static = optional(object({
        commitment = number # Target hourly commitment in $/h
      }))
    })

    split = object({
      one_shot   = optional(object({}))
      fixed_step = optional(object({ step_percent = number }))
      gap_split = optional(object({
        divider              = number
        min_purchase_percent = optional(number)
        max_purchase_percent = optional(number)
      }))
    })

    spike_guard = optional(object({
      enabled             = optional(bool, true)
      long_lookback_days  = optional(number, 90)
      short_lookback_days = optional(number, 14)
      threshold_percent   = optional(number, 20)
    }), {})
  })

  validation {
    condition     = try(var.purchase_strategy.min_commitment_per_plan >= 0.001, true)
    error_message = "min_commitment_per_plan must be at least 0.001 (AWS minimum)."
  }

  validation {
    condition     = try(var.purchase_strategy.purchase_cooldown_days >= 2, true)
    error_message = "purchase_cooldown_days must be >= 2 (Cost Explorer data lags 24-48h)."
  }

  # Exactly one target must be defined
  validation {
    condition = (
      length([for k in ["aws", "dynamic", "static"] : k if lookup(var.purchase_strategy.target, k, null) != null]) == 1
    )
    error_message = "Exactly one target strategy (aws, dynamic, or static) must be defined."
  }

  # Exactly one split must be defined
  validation {
    condition = (
      (var.purchase_strategy.split.one_shot != null && var.purchase_strategy.split.fixed_step == null && var.purchase_strategy.split.gap_split == null) ||
      (var.purchase_strategy.split.one_shot == null && var.purchase_strategy.split.fixed_step != null && var.purchase_strategy.split.gap_split == null) ||
      (var.purchase_strategy.split.one_shot == null && var.purchase_strategy.split.fixed_step == null && var.purchase_strategy.split.gap_split != null)
    )
    error_message = "Exactly one split strategy (one_shot, fixed_step, or gap_split) must be defined."
  }

  # dynamic.prudent_percentage validation
  validation {
    condition = (
      var.purchase_strategy.target.dynamic != null ?
      var.purchase_strategy.target.dynamic.prudent_percentage >= 1 && var.purchase_strategy.target.dynamic.prudent_percentage <= 100 :
      true
    )
    error_message = "dynamic.prudent_percentage must be between 1 and 100."
  }

  # static.commitment validation
  validation {
    condition = (
      var.purchase_strategy.target.static != null ?
      var.purchase_strategy.target.static.commitment > 0 :
      true
    )
    error_message = "static.commitment must be greater than 0."
  }

  # dynamic.risk_level validation
  validation {
    condition = (
      var.purchase_strategy.target.dynamic != null ?
      contains(["prudent", "min_hourly", "optimal", "maximum"], var.purchase_strategy.target.dynamic.risk_level) :
      true
    )
    error_message = "dynamic.risk_level must be one of: prudent, min_hourly, optimal, maximum."
  }

  # fixed_step.step_percent validation
  validation {
    condition = (
      try(var.purchase_strategy.split.fixed_step, null) != null ?
      var.purchase_strategy.split.fixed_step.step_percent > 0 && var.purchase_strategy.split.fixed_step.step_percent <= 100 :
      true
    )
    error_message = "fixed_step.step_percent must be between 0 and 100."
  }

  # gap_split validation
  validation {
    condition = (
      try(var.purchase_strategy.split.gap_split, null) != null ?
      var.purchase_strategy.split.gap_split.divider > 0 :
      true
    )
    error_message = "For gap_split split: divider must be greater than 0."
  }

  validation {
    condition = (
      try(var.purchase_strategy.split.gap_split.min_purchase_percent, null) != null ?
      var.purchase_strategy.split.gap_split.min_purchase_percent > 0 :
      true
    )
    error_message = "For gap_split split: min_purchase_percent must be greater than 0 (or omit for auto)."
  }

  # spike_guard validations
  validation {
    condition = (
      try(var.purchase_strategy.spike_guard.long_lookback_days, 90) >
      try(var.purchase_strategy.spike_guard.short_lookback_days, 14)
    )
    error_message = "spike_guard.long_lookback_days must be greater than short_lookback_days."
  }

  validation {
    condition     = try(var.purchase_strategy.spike_guard.long_lookback_days, 90) <= 90
    error_message = "spike_guard.long_lookback_days must be <= 90."
  }

  validation {
    condition     = try(var.purchase_strategy.spike_guard.short_lookback_days, 14) >= 1
    error_message = "spike_guard.short_lookback_days must be >= 1."
  }

  validation {
    condition = (
      try(var.purchase_strategy.spike_guard.threshold_percent, 20) >= 1 &&
      try(var.purchase_strategy.spike_guard.threshold_percent, 20) <= 100
    )
    error_message = "spike_guard.threshold_percent must be between 1 and 100."
  }
}

# Savings Plans Configuration

variable "sp_plans" {
  description = "Savings Plans configuration for Compute, Database, and SageMaker"
  type = object({
    compute = object({
      enabled   = bool
      plan_type = optional(string)
    })

    database = object({
      enabled   = bool
      plan_type = optional(string) # AWS only supports "no_upfront_one_year" for Database SPs
    })

    sagemaker = object({
      enabled   = bool
      plan_type = optional(string)
    })
  })

  # At least one SP type must be enabled
  validation {
    condition = (
      var.sp_plans.compute.enabled ||
      var.sp_plans.database.enabled ||
      var.sp_plans.sagemaker.enabled
    )
    error_message = "At least one SP type (compute, database, or sagemaker) must be enabled."
  }

  # Compute plan_type is required when enabled
  validation {
    condition     = !var.sp_plans.compute.enabled || var.sp_plans.compute.plan_type != null
    error_message = "Compute plan_type is required when compute is enabled."
  }

  # Compute plan_type must be valid
  validation {
    condition = (
      !var.sp_plans.compute.enabled || var.sp_plans.compute.plan_type == null ?
      true :
      contains([
        "all_upfront_three_year",
        "all_upfront_one_year",
        "partial_upfront_three_year",
        "partial_upfront_one_year",
        "no_upfront_three_year",
        "no_upfront_one_year"
      ], var.sp_plans.compute.plan_type)
    )
    error_message = "Compute plan_type must be one of: all_upfront_three_year, all_upfront_one_year, partial_upfront_three_year, partial_upfront_one_year, no_upfront_three_year, no_upfront_one_year."
  }

  # Database plan_type is required when enabled
  validation {
    condition     = !var.sp_plans.database.enabled || var.sp_plans.database.plan_type != null
    error_message = "Database plan_type is required when database is enabled."
  }

  # Database plan_type must be valid (AWS only supports one option)
  validation {
    condition = (
      !var.sp_plans.database.enabled || var.sp_plans.database.plan_type == null ?
      true :
      var.sp_plans.database.plan_type == "no_upfront_one_year"
    )
    error_message = "Database plan_type must be 'no_upfront_one_year' (AWS only supports 1-year NO_UPFRONT for Database SPs)."
  }

  # SageMaker plan_type is required when enabled
  validation {
    condition     = !var.sp_plans.sagemaker.enabled || var.sp_plans.sagemaker.plan_type != null
    error_message = "SageMaker plan_type is required when sagemaker is enabled."
  }

  # SageMaker plan_type must be valid
  validation {
    condition = (
      !var.sp_plans.sagemaker.enabled || var.sp_plans.sagemaker.plan_type == null ?
      true :
      contains([
        "all_upfront_three_year",
        "all_upfront_one_year",
        "partial_upfront_three_year",
        "partial_upfront_one_year",
        "no_upfront_three_year",
        "no_upfront_one_year"
      ], var.sp_plans.sagemaker.plan_type)
    )
    error_message = "SageMaker plan_type must be one of: all_upfront_three_year, all_upfront_one_year, partial_upfront_three_year, partial_upfront_one_year, no_upfront_three_year, no_upfront_one_year."
  }
}

# Scheduling

variable "cron_schedules" {
  description = "EventBridge cron schedules for each Lambda function. Set to null to disable a schedule."
  type = object({
    scheduler = optional(string) # Set to null to disable. Default: "cron(0 8 1 * ? *)"
    purchaser = optional(string) # Set to null to disable. Default: "cron(0 8 10 * ? *)"
    reporter  = optional(string) # Set to null to disable. Default: "cron(0 9 24 * ? *)"
  })
  default = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month at 8am UTC
    purchaser = "cron(0 8 10 * ? *)" # 10th of month at 8am UTC
    reporter  = "cron(0 9 24 * ? *)" # 24th of month at 9am UTC
  }
}

# Notifications

variable "notifications" {
  description = "Notification configuration for email, Slack, and Teams"
  type = object({
    emails        = list(string)
    slack_webhook = optional(string)
    teams_webhook = optional(string)
  })

  validation {
    condition     = length(var.notifications.emails) > 0 || var.notifications.slack_webhook != null || var.notifications.teams_webhook != null
    error_message = "At least one notification method (emails, slack_webhook, or teams_webhook) must be configured."
  }
}

# Reporting

variable "reporting" {
  description = "Report generation and storage configuration"
  type = object({
    format             = optional(string, "html")
    email_reports      = optional(bool, false)
    include_debug_data = optional(bool, false)

    s3_lifecycle = optional(object({
      transition_ia_days         = optional(number, 90)
      transition_glacier_days    = optional(number, 180)
      expiration_days            = optional(number, 365)
      noncurrent_expiration_days = optional(number, 90)
    }), {})
  })
  default = {}

  validation {
    condition     = contains(["html", "pdf", "json"], try(var.reporting.format, "html"))
    error_message = "report_format must be one of: html, pdf, json."
  }

  validation {
    condition = (
      try(var.reporting.s3_lifecycle.transition_glacier_days, 180) >
      try(var.reporting.s3_lifecycle.transition_ia_days, 90)
    )
    error_message = "s3_lifecycle.transition_glacier_days must be greater than transition_ia_days."
  }

  validation {
    condition = (
      try(var.reporting.s3_lifecycle.expiration_days, 365) >=
      try(var.reporting.s3_lifecycle.transition_glacier_days, 180)
    )
    error_message = "s3_lifecycle.expiration_days must be >= transition_glacier_days."
  }

  validation {
    condition     = try(var.reporting.s3_lifecycle.transition_ia_days >= 1, true)
    error_message = "s3_lifecycle.transition_ia_days must be at least 1."
  }

  validation {
    condition     = try(var.reporting.s3_lifecycle.transition_glacier_days >= 1, true)
    error_message = "s3_lifecycle.transition_glacier_days must be at least 1."
  }

  validation {
    condition     = try(var.reporting.s3_lifecycle.expiration_days >= 1, true)
    error_message = "s3_lifecycle.expiration_days must be at least 1."
  }

  validation {
    condition     = try(var.reporting.s3_lifecycle.noncurrent_expiration_days >= 1, true)
    error_message = "s3_lifecycle.noncurrent_expiration_days must be at least 1."
  }
}

# Monitoring

variable "monitoring" {
  description = "CloudWatch monitoring and alarm configuration"
  type = object({
    dlq_alarm                 = optional(bool, true)
    error_threshold           = optional(number, 1)  # Threshold for Lambda error alarms (configured per-Lambda in lambda_config)
    low_utilization_threshold = optional(number, 70) # Alert when Savings Plans utilization falls below this percentage
  })
  default = {}

  validation {
    condition     = var.monitoring.low_utilization_threshold >= 1 && var.monitoring.low_utilization_threshold <= 100
    error_message = "low_utilization_threshold must be between 1 and 100."
  }
}

# Simple Top-Level Variables

variable "name_prefix" {
  description = "Prefix for all resource names. Allows multiple module deployments in the same AWS account."
  type        = string
  default     = "sp-autopilot"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.name_prefix))
    error_message = "name_prefix must contain only lowercase letters, numbers, and hyphens."
  }

  validation {
    condition     = length(var.name_prefix) <= 64
    error_message = "name_prefix must be 64 characters or less."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Encryption

variable "encryption" {
  description = "Encryption configuration for SNS, SQS, and S3"
  type = object({
    sns_kms_key = optional(string, "alias/aws/sns") # Default: AWS managed KMS key. Set to null to disable.
    sqs_kms_key = optional(string, "alias/aws/sqs") # Default: AWS managed KMS key. Set to null to disable.
    s3 = optional(object({
      kms_key = optional(string) # null = AES256 (SSE-S3, free), set to KMS key ARN for SSE-KMS
    }), {})
  })
  default = {}
}

variable "s3_access_logging" {
  description = "Enable S3 access logging for the reports bucket (for compliance/auditing)"
  type = object({
    enabled         = optional(bool, false)
    target_prefix   = optional(string, "access-logs/")
    expiration_days = optional(number, 90)
  })
  default = {}

  validation {
    condition     = var.s3_access_logging.expiration_days >= 1
    error_message = "expiration_days must be at least 1."
  }
}
