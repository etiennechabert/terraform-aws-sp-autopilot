# ============================================================================
# SQS Resources
# ============================================================================
# Purpose: Manages SQS queues for Savings Plans purchase intents processing

# ============================================================================
# SQS Dead Letter Queue
# ============================================================================

resource "aws_sqs_queue" "purchase_intents_dlq" {
  name                              = "${local.module_name}-purchase-intents-dlq"
  message_retention_seconds         = 1209600 # 14 days (AWS maximum)
  kms_master_key_id                 = "alias/aws/sqs"
  kms_data_key_reuse_period_seconds = 300 # 5 minutes (default)

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
  name                              = "${local.module_name}-purchase-intents"
  visibility_timeout_seconds        = 300 # 5 minutes (matching Lambda timeout)
  kms_master_key_id                 = "alias/aws/sqs"
  kms_data_key_reuse_period_seconds = 300 # 5 minutes (default)

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
  count = local.enable_dlq_alarm ? 1 : 0

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
