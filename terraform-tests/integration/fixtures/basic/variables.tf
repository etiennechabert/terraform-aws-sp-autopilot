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
        commitment = number
      }))
    })

    split = optional(object({
      one_shot   = optional(object({}))
      fixed_step = optional(object({ step_percent = number }))
      gap_split = optional(object({
        divider              = number
        min_purchase_percent = optional(number)
        max_purchase_percent = optional(number)
      }))
    }))
  })
  default = {
    renewal_window_days     = 14
    min_commitment_per_plan = 0.001

    target = {
      dynamic = { risk_level = "prudent" }
    }

    split = {
      fixed_step = { step_percent = 10 }
    }
  }
}

# ============================================================================
# Savings Plans Configuration
# ============================================================================

variable "sp_plans" {
  description = "Savings Plans configuration"
  type = object({
    compute = object({
      enabled   = bool
      plan_type = optional(string)
    })

    database = object({
      enabled   = bool
      plan_type = optional(string)
    })

    sagemaker = object({
      enabled   = bool
      plan_type = optional(string)
    })
  })
  default = {
    compute = {
      enabled   = true
      plan_type = "all_upfront_three_year"
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

variable "cron_schedules" {
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
    emails        = list(string)
    slack_webhook = optional(string)
    teams_webhook = optional(string)
  })
  default = {
    emails = ["test@example.com"]
  }
}

# ============================================================================
# Reporting
# ============================================================================

variable "reporting" {
  description = "Reporting configuration"
  type = object({
    format        = optional(string, "html")
    email_reports = optional(bool, false)

    s3_lifecycle = optional(object({
      transition_ia_days         = optional(number, 90)
      transition_glacier_days    = optional(number, 180)
      expiration_days            = optional(number, 365)
      noncurrent_expiration_days = optional(number, 90)
    }), {})
  })
  default = {
    format        = "html"
    email_reports = false
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
