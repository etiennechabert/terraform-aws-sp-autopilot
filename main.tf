# AWS Savings Plans Automation Module
# Version: 1.0
# Purpose: Automates AWS Savings Plans purchases based on usage analysis

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

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

# ============================================================================
# Lambda Functions (Placeholder - Full implementation in future phase)
# ============================================================================

# TODO: Full Lambda implementation including:
# - Actual Python code deployment
# - IAM roles and policies
# - Environment variables
# - CloudWatch log groups
# - Error handling and retries

resource "aws_lambda_function" "scheduler" {
  function_name = "${local.module_name}-scheduler"
  description   = "Analyzes usage and queues Savings Plans purchase recommendations (PLACEHOLDER)"

  # Placeholder configuration - minimal valid Lambda
  role          = aws_iam_role.scheduler_placeholder.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  # Inline placeholder code (replace with actual deployment in future phase)
  filename         = data.archive_file.scheduler_placeholder.output_path
  source_code_hash = data.archive_file.scheduler_placeholder.output_base64sha256

  tags = local.common_tags
}

resource "aws_lambda_function" "purchaser" {
  function_name = "${local.module_name}-purchaser"
  description   = "Executes Savings Plans purchases from queue (PLACEHOLDER)"

  # Placeholder configuration - minimal valid Lambda
  role          = aws_iam_role.purchaser_placeholder.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  # Inline placeholder code (replace with actual deployment in future phase)
  filename         = data.archive_file.purchaser_placeholder.output_path
  source_code_hash = data.archive_file.purchaser_placeholder.output_base64sha256

  tags = local.common_tags
}

# Minimal IAM roles for placeholder Lambdas
resource "aws_iam_role" "scheduler_placeholder" {
  name = "${local.module_name}-scheduler-placeholder"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role" "purchaser_placeholder" {
  name = "${local.module_name}-purchaser-placeholder"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

# Create placeholder ZIP files
data "archive_file" "scheduler_placeholder" {
  type        = "zip"
  output_path = "${path.module}/.terraform/scheduler_placeholder.zip"

  source {
    content  = <<-EOT
      def handler(event, context):
          print("Scheduler Lambda placeholder - not yet implemented")
          return {"statusCode": 200, "body": "Placeholder"}
    EOT
    filename = "index.py"
  }
}

data "archive_file" "purchaser_placeholder" {
  type        = "zip"
  output_path = "${path.module}/.terraform/purchaser_placeholder.zip"

  source {
    content  = <<-EOT
      def handler(event, context):
          print("Purchaser Lambda placeholder - not yet implemented")
          return {"statusCode": 200, "body": "Placeholder"}
    EOT
    filename = "index.py"
  }
}

# ============================================================================
# EventBridge Schedules
# ============================================================================

# Scheduler Lambda - Runs monthly to analyze usage and queue purchase recommendations
resource "aws_cloudwatch_event_rule" "scheduler" {
  name                = "${local.module_name}-scheduler"
  description         = "Triggers Scheduler Lambda to analyze usage and recommend Savings Plans purchases"
  schedule_expression = var.scheduler_schedule

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "scheduler" {
  rule      = aws_cloudwatch_event_rule.scheduler.name
  target_id = "SchedulerLambda"
  arn       = aws_lambda_function.scheduler.arn # To be implemented in Lambda creation phase
}

resource "aws_lambda_permission" "scheduler_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler.function_name # To be implemented in Lambda creation phase
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduler.arn
}

# Purchaser Lambda - Runs monthly to execute approved Savings Plans purchases from queue
resource "aws_cloudwatch_event_rule" "purchaser" {
  name                = "${local.module_name}-purchaser"
  description         = "Triggers Purchaser Lambda to process and execute Savings Plans purchases from SQS queue"
  schedule_expression = var.purchaser_schedule

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "purchaser" {
  rule      = aws_cloudwatch_event_rule.purchaser.name
  target_id = "PurchaserLambda"
  arn       = aws_lambda_function.purchaser.arn # To be implemented in Lambda creation phase
}

resource "aws_lambda_permission" "purchaser_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.purchaser.function_name # To be implemented in Lambda creation phase
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.purchaser.arn
}

# ============================================================================
# Components will be defined in subsequent implementation phases:
# - SQS Queue for purchase intents
# - SNS Topic for notifications
# - Lambda functions (Scheduler and Purchaser)
# - IAM roles and policies
# - CloudWatch alarms
# ============================================================================
