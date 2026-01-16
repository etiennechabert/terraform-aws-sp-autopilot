# AWS Savings Plans Automation Module - Configuration Variables
# Version: 2.0 - Refactored to nested structure

# ============================================================================
# Lambda Control & Configuration
# ============================================================================

variable "lambda_config" {
  description = "Lambda function configuration including enable/disable controls, performance settings, and cross-account role ARNs"
  type = object({
    scheduler = optional(object({
      enabled         = optional(bool, true)
      memory_mb       = optional(number, 256)
      timeout         = optional(number, 300)
      assume_role_arn = optional(string)  # Role to assume for Cost Explorer and Savings Plans APIs (AWS Orgs)
    }), {})

    purchaser = optional(object({
      enabled         = optional(bool, true)
      memory_mb       = optional(number, 256)
      timeout         = optional(number, 300)
      assume_role_arn = optional(string)  # Role to assume for Savings Plans purchase APIs (AWS Orgs)
    }), {})

    reporter = optional(object({
      enabled         = optional(bool, true)
      memory_mb       = optional(number, 256)
      timeout         = optional(number, 300)
      assume_role_arn = optional(string)  # Role to assume for Cost Explorer and Savings Plans APIs (AWS Orgs)
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
      no_upfront_one_year = optional(number, 1)  # AWS only supports 1-year NO_UPFRONT
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
        abs(
          try(var.sp_plans.compute.all_upfront_three_year, 0) +
          try(var.sp_plans.compute.all_upfront_one_year, 0) +
          try(var.sp_plans.compute.partial_upfront_three_year, 0) +
          try(var.sp_plans.compute.partial_upfront_one_year, 0) +
          try(var.sp_plans.compute.no_upfront_three_year, 0) +
          try(var.sp_plans.compute.no_upfront_one_year, 0) - 1
        ) < 0.0001
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
        abs(
          try(var.sp_plans.sagemaker.all_upfront_three_year, 0) +
          try(var.sp_plans.sagemaker.all_upfront_one_year, 0) +
          try(var.sp_plans.sagemaker.partial_upfront_three_year, 0) +
          try(var.sp_plans.sagemaker.partial_upfront_one_year, 0) +
          try(var.sp_plans.sagemaker.no_upfront_three_year, 0) +
          try(var.sp_plans.sagemaker.no_upfront_one_year, 0) - 1
        ) < 0.0001
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
    scheduler = optional(string)  # Set to null to disable, defaults to "cron(0 8 1 * ? *)"
    purchaser = optional(string)  # Set to null to disable, defaults to "cron(0 8 4 * ? *)"
    reporter  = optional(string)  # Set to null to disable, defaults to "cron(0 9 1 * ? *)"
  })
  default = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month at 8am UTC
    purchaser = "cron(0 8 4 * ? *)"  # 4th of month at 8am UTC
    reporter  = "cron(0 9 1 * ? *)"  # 1st of month at 9am UTC
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
    lambda_error_alarm = optional(bool, true)
    dlq_alarm          = optional(bool, true)
    error_threshold    = optional(number, 1)
  })
  default = {}
}

# ============================================================================
# Operations
# ============================================================================

variable "operations" {
  description = "Operational settings including dry-run mode and AWS Organizations integration"
  type = object({
    dry_run                     = optional(bool, true)
    enable_cost_forecasting     = optional(bool, true)
    management_account_role_arn = optional(string)
  })
  default = {}
}

# ============================================================================
# Simple Top-Level Variables
# ============================================================================

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "enable_sns_kms_encryption" {
  description = "Enable KMS encryption for SNS topic (uses AWS managed key alias/aws/sns)"
  type        = bool
  default     = false
}
