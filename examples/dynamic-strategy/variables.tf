# Variables for dynamic-strategy example
# These can be overridden for testing or customization

variable "name_prefix" {
  description = "Prefix for resource names (can be overridden for testing to avoid collisions)"
  type        = string
  default     = "sp-autopilot"
}

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
      dry_run = optional(bool, false) # Production mode by default for this example
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
