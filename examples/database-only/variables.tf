# Variables for database-only example
# These can be overridden for testing or customization

variable "scheduler" {
  description = "EventBridge schedule configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(string, "cron(0 8 1 * ? *)")
    purchaser = optional(string, "cron(0 8 4 * ? *)")
    reporter  = optional(string, "cron(0 9 1 * ? *)")
  })
  default = {}
}

variable "lambda_config" {
  description = "Lambda configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(object({
      dry_run = optional(bool, true)
    }), {})
  })
  default = {}
}
