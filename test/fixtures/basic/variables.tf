# Test Fixture: Variables
# Purpose: Input variables for basic integration test

# ============================================================================
# Provider Configuration
# ============================================================================

variable "aws_region" {
  description = "AWS region for test resources"
  type        = string
  default     = "us-east-1"
}

# ============================================================================
# Savings Plan Types
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
# Coverage Strategy
# ============================================================================

variable "coverage_target_percent" {
  description = "Target hourly coverage percentage"
  type        = number
  default     = 80
}

variable "max_coverage_cap" {
  description = "Hard cap - never exceed this coverage"
  type        = number
  default     = 90
}

variable "lookback_days" {
  description = "Days of usage history for AWS recommendations"
  type        = number
  default     = 30
}

# ============================================================================
# Risk Management
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
}

# ============================================================================
# Expiring Plans
# ============================================================================

variable "renewal_window_days" {
  description = "SPs expiring within X days excluded from coverage calculation"
  type        = number
  default     = 7
}

# ============================================================================
# Compute SP Options
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
}

variable "compute_sp_payment_option" {
  description = "Payment option for Compute Savings Plans"
  type        = string
  default     = "ALL_UPFRONT"
}

variable "partial_upfront_percent" {
  description = "Percentage paid upfront for PARTIAL_UPFRONT"
  type        = number
  default     = 50
}

# ============================================================================
# Database SP Options
# ============================================================================

variable "database_sp_term" {
  description = "Term length for Database Savings Plans (AWS constraint: must be ONE_YEAR)"
  type        = string
  default     = "ONE_YEAR"
}

variable "database_sp_payment_option" {
  description = "Payment option for Database Savings Plans (AWS constraint: must be NO_UPFRONT)"
  type        = string
  default     = "NO_UPFRONT"
}

# ============================================================================
# Scheduling
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
# Operations
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

# ============================================================================
# Notifications
# ============================================================================

variable "notification_emails" {
  description = "List of email addresses for notifications"
  type        = list(string)
  default     = ["test@example.com"]
}

# ============================================================================
# Monitoring
# ============================================================================

variable "enable_lambda_error_alarm" {
  description = "Enable CloudWatch alarms for Lambda errors"
  type        = bool
  default     = true
}

variable "enable_dlq_alarm" {
  description = "Enable CloudWatch alarm for DLQ depth"
  type        = bool
  default     = true
}

# ============================================================================
# Cross-Account
# ============================================================================

variable "management_account_role_arn" {
  description = "ARN of role to assume in management account"
  type        = string
  default     = ""
}

# ============================================================================
# Tagging
# ============================================================================

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default = {
    Environment = "test"
    TestFixture = "basic"
  }
}
