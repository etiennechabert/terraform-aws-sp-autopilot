# AWS Savings Plans Automation Module
# Version: 1.0
# Purpose: Data sources and local variables

# ============================================================================
# Local Variables
# ============================================================================

locals {
  # Common tags for all resources
  common_tags = merge(
    {
      ManagedBy = "terraform-aws-sp-autopilot"
      Module    = "savings-plans-automation"
    },
    var.tags
  )

  # Module name for resource naming
  module_name = "sp-autopilot"

  # Validate at least one SP type is enabled
  sp_types_enabled = var.enable_compute_sp || var.enable_database_sp
}

# ============================================================================
# Validation Checks
# ============================================================================

# Ensure at least one Savings Plan type is enabled
resource "terraform_data" "validate_sp_types" {
  lifecycle {
    precondition {
      condition     = local.sp_types_enabled
      error_message = "At least one of enable_compute_sp or enable_database_sp must be true."
    }
  }
}

# ============================================================================
# Data Sources
# ============================================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
