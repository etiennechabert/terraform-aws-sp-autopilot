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
# Components will be defined in subsequent implementation phases:
# - Lambda functions (Scheduler and Purchaser)
# - IAM roles and policies
# - EventBridge schedules
# ============================================================================
