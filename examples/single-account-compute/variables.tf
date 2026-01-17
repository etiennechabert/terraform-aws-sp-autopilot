# Variables for single-account-compute example
# These can be overridden for testing or customization

variable "module_source" {
  description = "Source path for the module (registry for production, local path for testing)"
  type        = string
  default     = "etiennechabert/sp-autopilot/aws"
}

variable "module_version" {
  description = "Module version constraint (only used when module_source is registry)"
  type        = string
  default     = "~> 1.0"
}

variable "name_prefix" {
  description = "Prefix for resource names (can be overridden for testing to avoid collisions)"
  type        = string
  default     = "sp-autopilot"
}

variable "scheduler" {
  description = "EventBridge schedule configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(string, "cron(0 8 1 * ? *)") # 1st of month
    purchaser = optional(string, "cron(0 8 4 * ? *)") # 4th of month
    reporter  = optional(string, "cron(0 9 1 * ? *)") # 1st of month
  })
  default = {}
}

variable "lambda_config" {
  description = "Lambda configuration (can be overridden for testing)"
  type = object({
    scheduler = optional(object({
      dry_run = optional(bool, true) # Default to dry-run for safety
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
