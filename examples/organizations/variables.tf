# Variables for organizations example
# These can be overridden for testing or customization

variable "scheduler" {
  description = "EventBridge schedule configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(string, "cron(0 8 1 * ? *)")  # 1st of month
    purchaser = optional(string, "cron(0 8 10 * ? *)") # 10th of month
    reporter  = optional(string, "cron(0 9 20 * ? *)") # 20th of month
  })
  default = {}
}

variable "lambda_config" {
  description = "Lambda configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(object({
      dry_run         = optional(bool, true)
      assume_role_arn = optional(string)
    }), {})
    purchaser = optional(object({
      enabled         = optional(bool, true)
      assume_role_arn = optional(string)
    }), {})
    reporter = optional(object({
      enabled         = optional(bool, true)
      assume_role_arn = optional(string)
    }), {})
  })
  default = {}
}
