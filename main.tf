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
# SNS Topic
# ============================================================================

resource "aws_sns_topic" "notifications" {
  name         = "${local.module_name}-notifications"
  display_name = "AWS Savings Plans Automation Notifications"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-notifications"
    }
  )
}

# ============================================================================
# SNS Email Subscriptions
# ============================================================================

resource "aws_sns_topic_subscription" "email_notifications" {
  for_each = toset(var.notification_emails)

  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = each.value
}

# ============================================================================
# SQS Dead Letter Queue
# ============================================================================

resource "aws_sqs_queue" "purchase_intents_dlq" {
  name                      = "${local.module_name}-purchase-intents-dlq"
  message_retention_seconds = 1209600 # 14 days (AWS maximum)

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchase-intents-dlq"
    }
  )
}

# ============================================================================
# SQS Main Queue
# ============================================================================

resource "aws_sqs_queue" "purchase_intents" {
  name                       = "${local.module_name}-purchase-intents"
  visibility_timeout_seconds = 300 # 5 minutes (matching Lambda timeout)

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.purchase_intents_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchase-intents"
    }
  )
}

# ============================================================================
# CloudWatch Alarm for DLQ Depth
# ============================================================================

resource "aws_cloudwatch_metric_alarm" "dlq_alarm" {
  count = var.enable_dlq_alarm ? 1 : 0

  alarm_name          = "${local.module_name}-purchase-intents-dlq-depth"
  alarm_description   = "Triggers when messages land in the purchase intents DLQ, indicating repeated processing failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.purchase_intents_dlq.name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchase-intents-dlq-depth"
    }
  )
}

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
# CloudWatch Alarms for Lambda Functions
# ============================================================================

# Scheduler Lambda - Error Alarm
resource "aws_cloudwatch_metric_alarm" "scheduler_error_alarm" {
  count = var.enable_lambda_error_alarm ? 1 : 0

  alarm_name          = "${local.module_name}-scheduler-errors"
  alarm_description   = "Triggers when Scheduler Lambda function errors exceed threshold, indicating failures in usage analysis"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.scheduler.function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-scheduler-errors"
    }
  )
}

# Scheduler Lambda - Throttle Alarm
resource "aws_cloudwatch_metric_alarm" "scheduler_throttle_alarm" {
  count = var.enable_lambda_throttle_alarm ? 1 : 0

  alarm_name          = "${local.module_name}-scheduler-throttles"
  alarm_description   = "Triggers when Scheduler Lambda function is throttled, indicating concurrency limits are being hit"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = var.lambda_throttle_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.scheduler.function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-scheduler-throttles"
    }
  )
}

# Scheduler Lambda - Duration Alarm
resource "aws_cloudwatch_metric_alarm" "scheduler_duration_alarm" {
  count = var.enable_lambda_duration_alarm ? 1 : 0

  alarm_name          = "${local.module_name}-scheduler-duration"
  alarm_description   = "Triggers when Scheduler Lambda function duration exceeds threshold, indicating performance degradation"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Maximum"
  threshold           = var.lambda_duration_threshold_ms
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.scheduler.function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-scheduler-duration"
    }
  )
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
# - Full Lambda implementation (currently using placeholders)
# - Comprehensive IAM roles and policies
# - Additional CloudWatch alarms for Lambda errors
# ============================================================================
