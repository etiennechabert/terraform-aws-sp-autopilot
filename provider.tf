# AWS Savings Plans Automation Module - Provider Configuration
# Version: 2.0
# Purpose: Document provider configuration requirements for module callers
#
# IMPORTANT: This module does NOT declare providers internally.
# Provider configurations must be passed by the caller.
#
# ============================================================================
# Required Providers
# ============================================================================
#
# This module requires two AWS provider configurations:
#
# 1. Default Provider (aws):
#    - Used for deploying automation resources in the target account
#    - Inherits configuration from caller's AWS credentials
#
# 2. Management Account Provider (aws.management):
#    - Used for AWS Organizations management account operations
#    - Only needed when management_account_role_arn is provided
#
# ============================================================================
# Usage Example
# ============================================================================
#
# provider "aws" {
#   region = "us-east-1"
# }
#
# provider "aws" {
#   alias  = "management"
#   region = "us-east-1"
#   assume_role {
#     role_arn = "arn:aws:iam::123456789012:role/OrganizationAccountAccessRole"
#   }
# }
#
# module "savings_plans" {
#   source = "git::https://github.com/etiennechabert/terraform-aws-sp-autopilot.git"
#
#   providers = {
#     aws            = aws
#     aws.management = aws.management
#   }
#
#   # ... rest of configuration
# }
#
# ============================================================================
# Migration Note
# ============================================================================
#
# This module previously declared providers internally, which made it
# incompatible with count, for_each, and depends_on. The module now expects
# provider configurations to be passed by the caller, following Terraform
# best practices for reusable modules.
#
