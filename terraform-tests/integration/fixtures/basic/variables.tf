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
# Purchase Strategy
# ============================================================================

variable "purchase_strategy" {
  description = "Purchase strategy configuration"
  type = object({
    coverage_target_percent = number
    max_coverage_cap        = number
    lookback_days           = optional(number, 30)
    min_data_days           = optional(number, 14)
    renewal_window_days     = optional(number, 7)
    min_commitment_per_plan = optional(number, 0.001)

    simple = optional(object({
      max_purchase_percent = number
    }))
  })
  default = {
    coverage_target_percent = 80
    max_coverage_cap        = 90
    lookback_days           = 30
    min_data_days           = 14
    renewal_window_days     = 7
    min_commitment_per_plan = 0.001

    simple = {
      max_purchase_percent = 10
    }
  }
}

# ============================================================================
# Savings Plans Configuration
# ============================================================================

variable "sp_plans" {
  description = "Savings Plans configuration"
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
      no_upfront_one_year = optional(number, 1)
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
  default = {
    compute = {
      enabled                 = true
      all_upfront_three_year  = 0.67
      all_upfront_one_year    = 0.33
      partial_upfront_percent = 50
    }
    database = {
      enabled = false
    }
    sagemaker = {
      enabled = false
    }
  }
}

# ============================================================================
# Scheduling
# ============================================================================

variable "scheduler" {
  description = "EventBridge schedule configuration"
  type = object({
    scheduler = optional(string, "cron(0 8 1 * ? *)")
    purchaser = optional(string, "cron(0 8 10 * ? *)")
    reporter  = optional(string, "cron(0 9 20 * ? *)")
  })
  default = {
    scheduler = "cron(0 8 1 * ? *)"
    purchaser = "cron(0 8 10 * ? *)"
    reporter  = "cron(0 9 20 * ? *)"
  }
}

# ============================================================================
# Notifications
# ============================================================================

variable "notifications" {
  description = "Notification configuration"
  type = object({
    emails         = list(string)
    slack_webhook  = optional(string)
    teams_webhook  = optional(string)
    send_no_action = optional(bool, true)
  })
  default = {
    emails         = ["test@example.com"]
    send_no_action = true
  }
}

# ============================================================================
# Reporting
# ============================================================================

variable "reporting" {
  description = "Reporting configuration"
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
  default = {
    enabled        = true
    format         = "html"
    email_reports  = false
    retention_days = 365
  }
}

# ============================================================================
# Monitoring
# ============================================================================

variable "monitoring" {
  description = "Monitoring configuration"
  type = object({
    dlq_alarm       = optional(bool, true)
    error_threshold = optional(number, 1)
  })
  default = {
    dlq_alarm       = true
    error_threshold = 1
  }
}

# ============================================================================
# Lambda Configuration
# ============================================================================

variable "lambda_config" {
  description = "Lambda function configuration"
  type = object({
    scheduler = optional(object({
      memory_mb       = optional(number, 128)
      timeout         = optional(number, 300)
      dry_run         = optional(bool, false)
      error_alarm     = optional(bool, true)
      assume_role_arn = optional(string)
    }), {})

    purchaser = optional(object({
      memory_mb       = optional(number, 128)
      timeout         = optional(number, 300)
      error_alarm     = optional(bool, true)
      assume_role_arn = optional(string)
    }), {})

    reporter = optional(object({
      memory_mb       = optional(number, 128)
      timeout         = optional(number, 300)
      error_alarm     = optional(bool, true)
      assume_role_arn = optional(string)
    }), {})
  })
  default = {
    scheduler = {
      dry_run     = true
      error_alarm = true
    }
    purchaser = {
      error_alarm = true
    }
    reporter = {
      error_alarm = true
    }
  }
}

# ============================================================================
# Resource Naming
# ============================================================================

variable "name_prefix" {
  description = "Prefix for all resource names (enables unique names per test run to avoid collisions)"
  type        = string
  default     = "sp-autopilot-test"
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
