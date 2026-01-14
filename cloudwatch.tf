# ============================================================================
# CloudWatch Resources
# ============================================================================
# Purpose: Manages CloudWatch alarms and log groups for Lambda function monitoring

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

# Reporter Lambda - Error Alarm
resource "aws_cloudwatch_metric_alarm" "reporter_error_alarm" {
  count = var.enable_lambda_error_alarm ? 1 : 0

  alarm_name          = "${local.module_name}-reporter-errors"
  alarm_description   = "Triggers when Reporter Lambda function errors exceed threshold, indicating failures in report generation"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.reporter.function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-reporter-errors"
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

resource "aws_cloudwatch_log_group" "reporter" {
  name              = "/aws/lambda/${local.module_name}-reporter"
  retention_in_days = 30

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-reporter-logs"
    }
  )
}
