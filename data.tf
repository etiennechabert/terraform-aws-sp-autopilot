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
  sp_types_enabled = var.enable_compute_sp || var.enable_database_sp || var.enable_sagemaker_sp
}

# ============================================================================
# Validation Checks
# ============================================================================

# Ensure at least one Savings Plan type is enabled
resource "terraform_data" "validate_sp_types" {
  lifecycle {
    precondition {
      condition     = local.sp_types_enabled
      error_message = "At least one of enable_compute_sp, enable_database_sp, or enable_sagemaker_sp must be true."
    }
  }
}

# Ensure max_coverage_cap is greater than or equal to coverage_target_percent
resource "terraform_data" "validate_max_coverage_cap" {
  lifecycle {
    precondition {
      condition     = var.max_coverage_cap >= var.coverage_target_percent
      error_message = "Max coverage cap must be greater than or equal to coverage target percent."
    }
  }
}

# Ensure S3 lifecycle Glacier transition happens after IA transition
resource "terraform_data" "validate_s3_lifecycle_glacier_days" {
  lifecycle {
    precondition {
      condition     = var.s3_lifecycle_transition_glacier_days > var.s3_lifecycle_transition_ia_days
      error_message = "S3 lifecycle Glacier transition days must be greater than IA transition days."
    }
  }
}

# Ensure S3 lifecycle expiration happens after Glacier transition
resource "terraform_data" "validate_s3_lifecycle_expiration_days" {
  lifecycle {
    precondition {
      condition     = var.s3_lifecycle_expiration_days >= var.s3_lifecycle_transition_glacier_days
      error_message = "S3 lifecycle expiration days must be greater than or equal to Glacier transition days."
    }
  }
}

# ============================================================================
# Data Sources
# ============================================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
