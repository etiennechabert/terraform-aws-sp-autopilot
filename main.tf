# AWS Savings Plans Automation Module
# Version: 1.0
# Purpose: Automates AWS Savings Plans purchases based on usage analysis

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
  description   = "Analyzes usage and queues Savings Plans purchase recommendations"

  # Deploy actual Lambda code with proper configuration
  role          = aws_iam_role.scheduler.arn
  handler       = "handler.handler"
  runtime       = "python3.11"

  # Deploy actual Lambda code from lambda/scheduler directory
  filename         = data.archive_file.scheduler.output_path
  source_code_hash = data.archive_file.scheduler.output_base64sha256

  environment {
    variables = {
      QUEUE_URL                     = aws_sqs_queue.purchase_intents.url
      SNS_TOPIC_ARN                 = aws_sns_topic.notifications.arn
      DRY_RUN                       = tostring(var.dry_run)
      ENABLE_COMPUTE_SP             = tostring(var.enable_compute_sp)
      ENABLE_DATABASE_SP            = tostring(var.enable_database_sp)
      COVERAGE_TARGET_PERCENT       = tostring(var.coverage_target_percent)
      MAX_PURCHASE_PERCENT          = tostring(var.max_purchase_percent)
      RENEWAL_WINDOW_DAYS           = tostring(var.renewal_window_days)
      LOOKBACK_DAYS                 = tostring(var.lookback_days)
      MIN_DATA_DAYS                 = tostring(var.min_data_days)
      MIN_COMMITMENT_PER_PLAN       = tostring(var.min_commitment_per_plan)
      COMPUTE_SP_TERM_MIX           = jsonencode(var.compute_sp_term_mix)
      COMPUTE_SP_PAYMENT_OPTION     = var.compute_sp_payment_option
      PARTIAL_UPFRONT_PERCENT       = tostring(var.partial_upfront_percent)
      MANAGEMENT_ACCOUNT_ROLE_ARN   = var.management_account_role_arn
      TAGS                          = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "purchaser" {
  function_name = "${local.module_name}-purchaser"
  description   = "Executes Savings Plans purchases from queue"

  # Deploy actual Lambda code with proper configuration
  role          = aws_iam_role.purchaser.arn
  handler       = "handler.handler"
  runtime       = "python3.11"

  # Deploy actual Lambda code from lambda/purchaser directory
  filename         = data.archive_file.purchaser.output_path
  source_code_hash = data.archive_file.purchaser.output_base64sha256

  environment {
    variables = {
      QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      MAX_COVERAGE_CAP            = tostring(var.max_coverage_cap)
      RENEWAL_WINDOW_DAYS         = tostring(var.renewal_window_days)
      MANAGEMENT_ACCOUNT_ROLE_ARN = var.management_account_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

# ============================================================================
# IAM Roles and Policies for Lambda Functions
# ============================================================================

# Scheduler Lambda IAM Role
resource "aws_iam_role" "scheduler" {
  name        = "${local.module_name}-scheduler"
  description = "IAM role for Scheduler Lambda function - analyzes usage and queues purchase recommendations"

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

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-scheduler-role"
    }
  )
}

# Scheduler Lambda Policy - CloudWatch Logs
resource "aws_iam_role_policy" "scheduler_cloudwatch_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.scheduler.arn}:*"
    }]
  })
}

# Scheduler Lambda Policy - Cost Explorer
resource "aws_iam_role_policy" "scheduler_cost_explorer" {
  name = "cost-explorer"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansUtilization",
        "ce:GetSavingsPlansCoverage",
        "ce:GetCostAndUsage"
      ]
      Resource = "*"
    }]
  })
}

# Scheduler Lambda Policy - SQS
resource "aws_iam_role_policy" "scheduler_sqs" {
  name = "sqs"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:PurgeQueue",
        "sqs:GetQueueAttributes"
      ]
      Resource = aws_sqs_queue.purchase_intents.arn
    }]
  })
}

# Scheduler Lambda Policy - SNS
resource "aws_iam_role_policy" "scheduler_sns" {
  name = "sns"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sns:Publish"
      ]
      Resource = aws_sns_topic.notifications.arn
    }]
  })
}

# Scheduler Lambda Policy - Savings Plans
resource "aws_iam_role_policy" "scheduler_savingsplans" {
  name = "savingsplans"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:DescribeSavingsPlansOfferingRates",
        "savingsplans:DescribeSavingsPlansOfferings"
      ]
      Resource = "*"
    }]
  })
}

# Scheduler Lambda Policy - Assume Role (conditional)
resource "aws_iam_role_policy" "scheduler_assume_role" {
  count = var.management_account_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = var.management_account_role_arn
    }]
  })
}

# Purchaser Lambda IAM Role
resource "aws_iam_role" "purchaser" {
  name        = "${local.module_name}-purchaser"
  description = "IAM role for Purchaser Lambda function - executes Savings Plans purchases from queue"

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

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchaser-role"
    }
  )
}

# Purchaser Lambda Policy - CloudWatch Logs
resource "aws_iam_role_policy" "purchaser_cloudwatch_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.purchaser.arn}:*"
    }]
  })
}

# Purchaser Lambda Policy - Cost Explorer
resource "aws_iam_role_policy" "purchaser_cost_explorer" {
  name = "cost-explorer"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansUtilization",
        "ce:GetSavingsPlansCoverage",
        "ce:GetCostAndUsage"
      ]
      Resource = "*"
    }]
  })
}

# Purchaser Lambda Policy - SQS
resource "aws_iam_role_policy" "purchaser_sqs" {
  name = "sqs"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ]
      Resource = aws_sqs_queue.purchase_intents.arn
    }]
  })
}

# Purchaser Lambda Policy - SNS
resource "aws_iam_role_policy" "purchaser_sns" {
  name = "sns"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sns:Publish"
      ]
      Resource = aws_sns_topic.notifications.arn
    }]
  })
}

# Purchaser Lambda Policy - Savings Plans
resource "aws_iam_role_policy" "purchaser_savingsplans" {
  name = "savingsplans"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:DescribeSavingsPlansOfferingRates",
        "savingsplans:DescribeSavingsPlansOfferings",
        "savingsplans:CreateSavingsPlan"
      ]
      Resource = "*"
    }]
  })
}

# Purchaser Lambda Policy - Assume Role (conditional)
resource "aws_iam_role_policy" "purchaser_assume_role" {
  count = var.management_account_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = var.management_account_role_arn
    }]
  })
}

# ============================================================================
# Lambda Deployment Packages
# ============================================================================

# Scheduler Lambda deployment package
data "archive_file" "scheduler" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/scheduler"
  output_path = "${path.module}/.terraform/scheduler.zip"
}

# Purchaser Lambda deployment package
data "archive_file" "purchaser" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/purchaser"
  output_path = "${path.module}/.terraform/purchaser.zip"
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

# Purchaser Lambda - Error Alarm
resource "aws_cloudwatch_metric_alarm" "purchaser_error_alarm" {
  count = var.enable_lambda_error_alarm ? 1 : 0

  alarm_name          = "${local.module_name}-purchaser-errors"
  alarm_description   = "Triggers when Purchaser Lambda function errors exceed threshold, indicating failures in Savings Plans purchases"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.purchaser.function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchaser-errors"
    }
  )
}

# ============================================================================
# CloudWatch Log Groups
# ============================================================================

resource "aws_cloudwatch_log_group" "scheduler" {
  name              = "/aws/lambda/${local.module_name}-scheduler"
  retention_in_days = 30

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-scheduler-logs"
    }
  )
}

resource "aws_cloudwatch_log_group" "purchaser" {
  name              = "/aws/lambda/${local.module_name}-purchaser"
  retention_in_days = 30

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchaser-logs"
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
