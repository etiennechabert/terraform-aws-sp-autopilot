# Variables for dichotomy-strategy example
# These can be overridden for testing or customization

variable "scheduler" {
  description = "EventBridge schedule configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(string, "cron(0 8 1 * ? *)")  # 1st of month
    purchaser = optional(string, "cron(0 8 4 * ? *)")  # 4th of month
    reporter  = optional(string, "cron(0 9 1 * ? *)")  # 1st of month
  })
  default = {}
}

variable "lambda_config" {
  description = "Lambda configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(object({
      dry_run = optional(bool, false)  # Production mode by default
    }), {})
    purchaser = optional(object({
      enabled = optional(bool, true)
    }), {})
    reporter = optional(object({
      enabled = optional(bool, true)
    }), {})
  })
  default = {}
}
