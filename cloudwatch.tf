# CloudWatch log groups and alarms for Lambda monitoring

resource "aws_cloudwatch_log_group" "scheduler" {
  count = local.lambda_scheduler_enabled ? 1 : 0

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
  count = local.lambda_purchaser_enabled ? 1 : 0

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
  count = local.lambda_reporter_enabled ? 1 : 0

  name              = "/aws/lambda/${local.module_name}-reporter"
  retention_in_days = 30

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-reporter-logs"
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "scheduler_error_alarm" {
  count = local.lambda_scheduler_enabled && local.lambda_scheduler_error_alarm_enabled ? 1 : 0

  alarm_name          = "${local.module_name}-scheduler-errors"
  alarm_description   = "Triggers when Scheduler Lambda function errors exceed threshold, indicating failures in usage analysis"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = local.lambda_error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.scheduler[0].function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-scheduler-errors"
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "purchaser_error_alarm" {
  count = local.lambda_purchaser_enabled && local.lambda_purchaser_error_alarm_enabled ? 1 : 0

  alarm_name          = "${local.module_name}-purchaser-errors"
  alarm_description   = "Triggers when Purchaser Lambda function errors exceed threshold, indicating failures in Savings Plans purchases"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = local.lambda_error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.purchaser[0].function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchaser-errors"
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "reporter_error_alarm" {
  count = local.lambda_reporter_enabled && local.lambda_reporter_error_alarm_enabled ? 1 : 0

  alarm_name          = "${local.module_name}-reporter-errors"
  alarm_description   = "Triggers when Reporter Lambda function errors exceed threshold, indicating failures in report generation"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = local.lambda_error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.reporter[0].function_name
  }

  alarm_actions = [aws_sns_topic.notifications.arn]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-reporter-errors"
    }
  )
}
