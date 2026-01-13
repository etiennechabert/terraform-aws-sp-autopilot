# AWS Savings Plans Automation Module - Provider Configuration
# Version: 1.0
# Purpose: Configure AWS provider for default operations and Organizations management account

# ============================================================================
# Default Provider
# ============================================================================

# Default AWS provider - inherits configuration from caller
# Used for deploying automation resources in the target account
provider "aws" {
  # Configuration inherited from caller's AWS credentials
  # Region, credentials, and other settings passed through
}

# ============================================================================
# Organizations Management Account Provider
# ============================================================================

# Optional provider alias for AWS Organizations management account operations
# Only used when management_account_role_arn is provided for cross-account access
provider "aws" {
  alias = "management"

  # Assume role in management account if ARN is provided
  dynamic "assume_role" {
    for_each = var.management_account_role_arn != null ? [1] : []

    content {
      role_arn = var.management_account_role_arn
    }
  }
}
