# AWS Savings Plans Automation Module - Configuration Variables

# ============================================================================
# Lambda Control & Configuration
# ============================================================================

variable "lambda_config" {
  description = "Lambda function configuration including enable/disable controls, performance settings, cross-account role ARNs, and error alarms"
  type = object({
    scheduler = optional(object({
      enabled         = optional(bool, true)
      dry_run         = optional(bool, false) # If true, sends email only (no SQS queueing)
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

# ============================================================================
# Purchase Strategy Configuration
# ============================================================================

variable "purchase_strategy" {
  description = "Purchase strategy configuration including coverage targets and risk management"
  type = object({
    # Coverage targets
    coverage_target_percent = number
    max_coverage_cap        = number

    # Historical data settings
    lookback_days = optional(number, 30)
    min_data_days = optional(number, 14)

    # Renewal and commitment settings
    renewal_window_days     = optional(number, 7)
    min_commitment_per_plan = optional(number, 0.001)

    # Strategy type - exactly one must be defined
    simple = optional(object({
      max_purchase_percent = number
    }))

    dichotomy = optional(object({
      max_purchase_percent = number
      min_purchase_percent = number
    }))
  })

  validation {
    condition     = var.purchase_strategy.coverage_target_percent >= 1 && var.purchase_strategy.coverage_target_percent <= 100
    error_message = "coverage_target_percent must be between 1 and 100."
  }

  validation {
    condition     = var.purchase_strategy.max_coverage_cap <= 100
    error_message = "max_coverage_cap must be less than or equal to 100."
  }

  validation {
    condition     = var.purchase_strategy.coverage_target_percent <= var.purchase_strategy.max_coverage_cap
    error_message = "coverage_target_percent must be <= max_coverage_cap."
  }

  validation {
    condition     = try(var.purchase_strategy.min_commitment_per_plan >= 0.001, true)
    error_message = "min_commitment_per_plan must be at least 0.001 (AWS minimum)."
  }

  validation {
    condition = (
      (var.purchase_strategy.simple != null && var.purchase_strategy.dichotomy == null) ||
      (var.purchase_strategy.simple == null && var.purchase_strategy.dichotomy != null)
    )
    error_message = "Exactly one purchase strategy (simple or dichotomy) must be defined."
  }

  validation {
    condition = (
      var.purchase_strategy.simple != null ?
      var.purchase_strategy.simple.max_purchase_percent > 0 && var.purchase_strategy.simple.max_purchase_percent <= 100 :
      true
    )
    error_message = "simple.max_purchase_percent must be between 0 and 100."
  }

  validation {
    condition = (
      var.purchase_strategy.dichotomy != null ?
      (var.purchase_strategy.dichotomy.min_purchase_percent > 0 &&
        var.purchase_strategy.dichotomy.max_purchase_percent <= 100 &&
      var.purchase_strategy.dichotomy.min_purchase_percent < var.purchase_strategy.dichotomy.max_purchase_percent) :
      true
    )
    error_message = "For dichotomy strategy: 0 < min_purchase_percent < max_purchase_percent <= 100."
  }
}

# ============================================================================
# Savings Plans Configuration
# ============================================================================

variable "sp_plans" {
  description = "Savings Plans configuration for Compute, Database, and SageMaker"
  type = object({
    compute = optional(object({
      enabled                    = bool
      all_upfront_three_year     = optional(number, 0)
      all_upfront_one_year       = optional(number, 0)
      partial_upfront_three_year = optional(number, 0)
      partial_upfront_one_year   = optional(number, 0)
      no_upfront_three_year      = optional(number, 0)
      no_upfront_one_year        = optional(number, 0)
      partial_upfront_percent    = optional(number, 50)
    }))

    database = optional(object({
      enabled             = bool
      no_upfront_one_year = optional(number, 1) # AWS only supports 1-year NO_UPFRONT
    }))

    sagemaker = optional(object({
      enabled                    = bool
      all_upfront_three_year     = optional(number, 0)
      all_upfront_one_year       = optional(number, 0)
      partial_upfront_three_year = optional(number, 0)
      partial_upfront_one_year   = optional(number, 0)
      no_upfront_three_year      = optional(number, 0)
      no_upfront_one_year        = optional(number, 0)
      partial_upfront_percent    = optional(number, 50)
    }))
  })

  # At least one SP type must be enabled
  validation {
    condition = (
      try(var.sp_plans.compute.enabled, false) ||
      try(var.sp_plans.database.enabled, false) ||
      try(var.sp_plans.sagemaker.enabled, false)
    )
    error_message = "At least one SP type (compute, database, or sagemaker) must be enabled."
  }

  # Compute percentages must sum to 1.0 (if enabled)
  validation {
    condition = (
      try(var.sp_plans.compute.enabled, false) ?
      (try(var.sp_plans.compute.all_upfront_three_year, 0) +
        try(var.sp_plans.compute.all_upfront_one_year, 0) +
        try(var.sp_plans.compute.partial_upfront_three_year, 0) +
        try(var.sp_plans.compute.partial_upfront_one_year, 0) +
        try(var.sp_plans.compute.no_upfront_three_year, 0) +
      try(var.sp_plans.compute.no_upfront_one_year, 0)) == 1
      : true
    )
    error_message = "Compute SP payment/term percentages must sum to 1.0 when enabled."
  }

  # Database must be exactly 1.0 (AWS constraint - only one option available)
  validation {
    condition = (
      try(var.sp_plans.database.enabled, false) ?
      try(var.sp_plans.database.no_upfront_one_year, 0) == 1
      : true
    )
    error_message = "Database SP must have no_upfront_one_year = 1 (AWS only supports 1-year NO_UPFRONT)."
  }

  # SageMaker percentages must sum to 1.0 (if enabled)
  validation {
    condition = (
      try(var.sp_plans.sagemaker.enabled, false) ?
      (try(var.sp_plans.sagemaker.all_upfront_three_year, 0) +
        try(var.sp_plans.sagemaker.all_upfront_one_year, 0) +
        try(var.sp_plans.sagemaker.partial_upfront_three_year, 0) +
        try(var.sp_plans.sagemaker.partial_upfront_one_year, 0) +
        try(var.sp_plans.sagemaker.no_upfront_three_year, 0) +
      try(var.sp_plans.sagemaker.no_upfront_one_year, 0)) == 1
      : true
    )
    error_message = "SageMaker SP payment/term percentages must sum to 1.0 when enabled."
  }

  # All percentages must be non-negative
  validation {
    condition = alltrue([
      try(var.sp_plans.compute.all_upfront_three_year >= 0, true),
      try(var.sp_plans.compute.all_upfront_one_year >= 0, true),
      try(var.sp_plans.compute.partial_upfront_three_year >= 0, true),
      try(var.sp_plans.compute.partial_upfront_one_year >= 0, true),
      try(var.sp_plans.compute.no_upfront_three_year >= 0, true),
      try(var.sp_plans.compute.no_upfront_one_year >= 0, true),
      try(var.sp_plans.sagemaker.all_upfront_three_year >= 0, true),
      try(var.sp_plans.sagemaker.all_upfront_one_year >= 0, true),
      try(var.sp_plans.sagemaker.partial_upfront_three_year >= 0, true),
      try(var.sp_plans.sagemaker.partial_upfront_one_year >= 0, true),
      try(var.sp_plans.sagemaker.no_upfront_three_year >= 0, true),
      try(var.sp_plans.sagemaker.no_upfront_one_year >= 0, true),
    ])
    error_message = "All SP payment/term percentages must be non-negative."
  }

  # partial_upfront_percent must be between 0 and 100
  validation {
    condition = alltrue([
      try(var.sp_plans.compute.partial_upfront_percent >= 0 && var.sp_plans.compute.partial_upfront_percent <= 100, true),
      try(var.sp_plans.sagemaker.partial_upfront_percent >= 0 && var.sp_plans.sagemaker.partial_upfront_percent <= 100, true),
    ])
    error_message = "partial_upfront_percent must be between 0 and 100."
  }
}

# ============================================================================
# Scheduling
# ============================================================================

variable "scheduler" {
  description = "EventBridge cron schedules for each Lambda function. Set to null to disable a schedule."
  type = object({
    scheduler = optional(string) # Set to null to disable, defaults to "cron(0 8 1 * ? *)"
    purchaser = optional(string) # Set to null to disable, defaults to "cron(0 8 10 * ? *)"
    reporter  = optional(string) # Set to null to disable, defaults to "cron(0 9 20 * ? *)"
  })
  default = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month at 8am UTC
    purchaser = "cron(0 8 10 * ? *)" # 10th of month at 8am UTC
    reporter  = "cron(0 9 20 * ? *)" # 20th of month at 9am UTC
  }
}

# ============================================================================
# Notifications
# ============================================================================

variable "notifications" {
  description = "Notification configuration for email, Slack, and Teams"
  type = object({
    emails         = list(string)
    slack_webhook  = optional(string)
    teams_webhook  = optional(string)
    send_no_action = optional(bool, true)
  })

  validation {
    condition     = length(var.notifications.emails) > 0 || var.notifications.slack_webhook != null || var.notifications.teams_webhook != null
    error_message = "At least one notification method (emails, slack_webhook, or teams_webhook) must be configured."
  }
}

# ============================================================================
# Reporting
# ============================================================================

variable "reporting" {
  description = "Report generation and storage configuration"
  type = object({
    enabled        = optional(bool, true)
    format         = optional(string, "html")
    email_reports  = optional(bool, false)
    retention_days = optional(number, 365)

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
    condition     = try(var.reporting.retention_days >= 1, true)
    error_message = "retention_days must be at least 1."
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

# ============================================================================
# Monitoring
# ============================================================================

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

# ============================================================================
# Simple Top-Level Variables
# ============================================================================

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

# ============================================================================
# Encryption
# ============================================================================

variable "encryption" {
  description = "Encryption configuration for SNS, SQS, and S3"
  type = object({
    sns_kms_key = optional(string, "alias/aws/sns") # Default: AWS managed KMS key. Set to null to disable.
    sqs_kms_key = optional(string, "alias/aws/sqs") # Default: AWS managed KMS key. Set to null to disable.
    s3 = optional(object({
      enabled = optional(bool, true) # Enable/disable S3 encryption
      kms_key = optional(string)     # null = AES256 (SSE-S3, free), set to KMS key ARN for SSE-KMS
    }), {})
  })
  default = {
    sns_kms_key = "alias/aws/sns"
    sqs_kms_key = "alias/aws/sqs"
    s3 = {
      enabled = true
      kms_key = null # AES256 by default
    }
  }
}
