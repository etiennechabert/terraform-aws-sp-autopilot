# AWS Savings Plans Automation Module - Provider Configuration
# Version: 2.0
# Purpose: Document provider configuration requirements for module callers
#
# ============================================================================
# Provider Configuration
# ============================================================================
#
# This module does NOT declare providers internally. It inherits the AWS
# provider configuration from the caller, following Terraform best practices
# for reusable modules.
#
# The module uses a single AWS provider for deploying resources. For AWS
# Organizations scenarios, the management_account_role_arn variable can be
# provided, and the Lambda functions will assume that role at runtime (not
# at Terraform apply time).
#
# ============================================================================
# Usage Example - Single Account
# ============================================================================
#
# provider "aws" {
#   region = "us-east-1"
# }
#
# module "savings_plans" {
#   source = "git::https://github.com/etiennechabert/terraform-aws-sp-autopilot.git"
#
#   enable_compute_sp  = true
#   enable_database_sp = false
#
#   # ... rest of configuration
# }
#
# ============================================================================
# Usage Example - AWS Organizations
# ============================================================================
#
# provider "aws" {
#   region = "us-east-1"
# }
#
# module "savings_plans" {
#   source = "git::https://github.com/etiennechabert/terraform-aws-sp-autopilot.git"
#
#   enable_compute_sp  = true
#   enable_database_sp = false
#
#   # Lambda functions will assume this role at runtime to access
#   # Cost Explorer and Savings Plans APIs in the management account
#   management_account_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansAutomationRole"
#
#   # ... rest of configuration
# }
#
# ============================================================================
# Migration Note
# ============================================================================
#
# This module previously declared providers internally, which made it
# incompatible with count, for_each, and depends_on. Internal provider
# declarations have been removed to follow Terraform best practices.
#
