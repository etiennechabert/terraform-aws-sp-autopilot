# AWS Savings Plans Automation Module - Configuration Variables

# ============================================================================
# 7.1 Savings Plan Types
# ============================================================================

variable "enable_compute_sp" {
  description = "Enable Compute Savings Plans automation"
  type        = bool
  default     = true
}

variable "enable_database_sp" {
  description = "Enable Database Savings Plans automation"
  type        = bool
  default     = false
}

# ============================================================================
# 7.2 Coverage Strategy
# ============================================================================

variable "coverage_target_percent" {
  description = "Target hourly coverage percentage"
  type        = number
  default     = 90

  validation {
    condition     = var.coverage_target_percent >= 1 && var.coverage_target_percent <= 100
    error_message = "Coverage target percent must be between 1 and 100."
  }
}

variable "max_coverage_cap" {
  description = "Hard cap - never exceed this coverage"
  type        = number
  default     = 95

  validation {
    condition     = var.max_coverage_cap <= 100
    error_message = "Max coverage cap must be less than or equal to 100."
  }
}

variable "lookback_days" {
  description = "Days of usage history for AWS recommendations"
  type        = number
  default     = 30
}

# ============================================================================
# 7.3 Risk Management
# ============================================================================

variable "max_purchase_percent" {
  description = "Max purchase as % of monthly spend"
  type        = number
  default     = 10
}

variable "min_data_days" {
  description = "Skip if insufficient usage history"
  type        = number
  default     = 14
}

variable "min_commitment_per_plan" {
  description = "Minimum commitment per SP (AWS min: $0.001/hr)"
  type        = number
  default     = 0.001

  validation {
    condition     = var.min_commitment_per_plan >= 0.001
    error_message = "Min commitment per plan must be at least 0.001 (AWS minimum)."
  }
}

# ============================================================================
# 7.4 Expiring Plans
# ============================================================================

variable "renewal_window_days" {
  description = "SPs expiring within X days excluded from coverage calculation"
  type        = number
  default     = 7
}

# ============================================================================
# 7.5 Compute SP Options
# ============================================================================

variable "compute_sp_term_mix" {
  description = "Split of commitment between terms"
  type = object({
    three_year = number
    one_year   = number
  })
  default = {
    three_year = 0.67
    one_year   = 0.33
  }

  validation {
    condition     = var.compute_sp_term_mix.three_year >= 0 && var.compute_sp_term_mix.one_year >= 0
    error_message = "Both term mix values must be non-negative."
  }

  validation {
    condition     = abs(var.compute_sp_term_mix.three_year + var.compute_sp_term_mix.one_year - 1) < 0.0001
    error_message = "The sum of compute_sp_term_mix.three_year and compute_sp_term_mix.one_year must equal 1."
  }
}

variable "compute_sp_payment_option" {
  description = "Payment option for Compute Savings Plans"
  type        = string
  default     = "ALL_UPFRONT"

  validation {
    condition     = contains(["ALL_UPFRONT", "PARTIAL_UPFRONT", "NO_UPFRONT"], var.compute_sp_payment_option)
    error_message = "compute_sp_payment_option must be one of: ALL_UPFRONT, PARTIAL_UPFRONT, NO_UPFRONT."
  }
}

variable "partial_upfront_percent" {
  description = "Percentage paid upfront for PARTIAL_UPFRONT"
  type        = number
  default     = 50
}

# ============================================================================
# 7.5.1 Database SP Options
# ============================================================================

variable "database_sp_term" {
  description = "Term length for Database Savings Plans (AWS constraint: must be ONE_YEAR)"
  type        = string
  default     = "ONE_YEAR"

  validation {
    condition     = var.database_sp_term == "ONE_YEAR"
    error_message = "database_sp_term must be ONE_YEAR. AWS Database Savings Plans only support 1-year terms."
  }
}

variable "database_sp_payment_option" {
  description = "Payment option for Database Savings Plans (AWS constraint: must be NO_UPFRONT)"
  type        = string
  default     = "NO_UPFRONT"

  validation {
    condition     = var.database_sp_payment_option == "NO_UPFRONT"
    error_message = "database_sp_payment_option must be NO_UPFRONT. AWS Database Savings Plans only support no upfront payment."
  }
}

# ============================================================================
# 7.6 Scheduling
# ============================================================================

variable "scheduler_schedule" {
  description = "When scheduler runs (EventBridge cron expression)"
  type        = string
  default     = "cron(0 8 1 * ? *)"
}

variable "purchaser_schedule" {
  description = "When purchaser runs (EventBridge cron expression)"
  type        = string
  default     = "cron(0 8 4 * ? *)"
}

# ============================================================================
# 7.7 Operations
# ============================================================================

variable "dry_run" {
  description = "If true, scheduler sends email only (no queue)"
  type        = bool
  default     = true
}

variable "send_no_action_email" {
  description = "Send email when no purchases needed"
  type        = bool
  default     = true
}

variable "enable_cost_forecasting" {
  description = "Enable cost forecasting integration (can be disabled to reduce API costs)"
  type        = bool
  default     = true
}

# ============================================================================
# 7.8 Notifications
# ============================================================================

variable "notification_emails" {
  description = "Email addresses for notifications"
  type        = list(string)
  default     = []
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = null
  sensitive   = true
}

variable "teams_webhook_url" {
  description = "Microsoft Teams webhook URL for notifications"
  type        = string
  default     = null
  sensitive   = true
}

# ============================================================================
# 7.9 Monitoring
# ============================================================================

variable "enable_lambda_error_alarm" {
  description = "CloudWatch alarm on Lambda errors"
  type        = bool
  default     = true
}

variable "enable_dlq_alarm" {
  description = "CloudWatch alarm on DLQ depth"
  type        = bool
  default     = true
}

variable "lambda_error_threshold" {
  description = "Number of Lambda errors to trigger alarm"
  type        = number
  default     = 1
}

# ============================================================================
# 7.10 AWS Organizations
# ============================================================================

variable "management_account_role_arn" {
  description = "Role ARN to assume in management account"
  type        = string
  default     = null
}

# ============================================================================
# 7.11 Tagging
# ============================================================================

variable "tags" {
  description = "Additional tags to apply to purchased SPs"
  type        = map(string)
  default     = {}
}

# ============================================================================
# 7.12 Report Configuration
# ============================================================================

variable "enable_reports" {
  description = "Enable periodic coverage and savings reports"
  type        = bool
  default     = true
}

variable "report_schedule" {
  description = "When reporter runs (EventBridge cron expression)"
  type        = string
  default     = "cron(0 9 1 * ? *)"
}

variable "report_retention_days" {
  description = "Days to retain reports in S3 before expiration"
  type        = number
  default     = 365

  validation {
    condition     = var.report_retention_days >= 1
    error_message = "report_retention_days must be at least 1."
  }
}

variable "s3_lifecycle_transition_ia_days" {
  description = "Days before transitioning reports to STANDARD_IA storage class"
  type        = number
  default     = 90

  validation {
    condition     = var.s3_lifecycle_transition_ia_days >= 1
    error_message = "s3_lifecycle_transition_ia_days must be at least 1."
  }
}

variable "s3_lifecycle_transition_glacier_days" {
  description = "Days before transitioning reports to GLACIER storage class"
  type        = number
  default     = 180

  validation {
    condition     = var.s3_lifecycle_transition_glacier_days >= 1
    error_message = "S3 lifecycle transition to Glacier must be at least 1 day."
  }
}

variable "s3_lifecycle_expiration_days" {
  description = "Days before expiring report objects"
  type        = number
  default     = 365

  validation {
    condition     = var.s3_lifecycle_expiration_days >= 1
    error_message = "S3 lifecycle expiration must be at least 1 day."
  }
}

variable "s3_lifecycle_noncurrent_expiration_days" {
  description = "Days before expiring noncurrent report versions"
  type        = number
  default     = 90

  validation {
    condition     = var.s3_lifecycle_noncurrent_expiration_days >= 1
    error_message = "S3 lifecycle noncurrent version expiration must be at least 1 day."
  }
}

variable "report_format" {
  description = "Format for generated reports"
  type        = string
  default     = "html"

  validation {
    condition     = contains(["html", "pdf", "json"], var.report_format)
    error_message = "report_format must be one of: html, pdf, json."
  }
}

variable "email_reports" {
  description = "Send reports via email to notification_emails"
  type        = bool
  default     = false
}

# ============================================================================
# 7.13 Security & Encryption
# ============================================================================
# SQS queues use AWS-managed encryption (alias/aws/sqs) which provides free at-rest
# encryption without requiring customer-managed KMS keys or additional IAM permissions.
