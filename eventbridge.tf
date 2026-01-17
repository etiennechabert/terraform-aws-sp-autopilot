# AWS Savings Plans Automation Module - EventBridge Schedules
# Purpose: Defines EventBridge schedules for automated Lambda function triggers

# ============================================================================
# EventBridge Schedules
# ============================================================================

# Scheduler Lambda - Runs monthly to analyze usage and queue purchase recommendations
resource "aws_cloudwatch_event_rule" "scheduler" {
  count = local.lambda_scheduler_enabled && local.scheduler_schedule != null ? 1 : 0

  name                = "${local.module_name}-scheduler"
  description         = "Triggers Scheduler Lambda to analyze usage and recommend Savings Plans purchases"
  schedule_expression = local.scheduler_schedule

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "scheduler" {
  count = local.lambda_scheduler_enabled && local.scheduler_schedule != null ? 1 : 0

  rule      = aws_cloudwatch_event_rule.scheduler[0].name
  target_id = "SchedulerLambda"
  arn       = aws_lambda_function.scheduler[0].arn
}

resource "aws_lambda_permission" "scheduler_eventbridge" {
  count = local.lambda_scheduler_enabled && local.scheduler_schedule != null ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduler[0].arn
}

# Purchaser Lambda - Runs monthly to execute approved Savings Plans purchases from queue
resource "aws_cloudwatch_event_rule" "purchaser" {
  count = local.lambda_purchaser_enabled && local.purchaser_schedule != null ? 1 : 0

  name                = "${local.module_name}-purchaser"
  description         = "Triggers Purchaser Lambda to process and execute Savings Plans purchases from SQS queue"
  schedule_expression = local.purchaser_schedule

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "purchaser" {
  count = local.lambda_purchaser_enabled && local.purchaser_schedule != null ? 1 : 0

  rule      = aws_cloudwatch_event_rule.purchaser[0].name
  target_id = "PurchaserLambda"
  arn       = aws_lambda_function.purchaser[0].arn
}

resource "aws_lambda_permission" "purchaser_eventbridge" {
  count = local.lambda_purchaser_enabled && local.purchaser_schedule != null ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.purchaser[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.purchaser[0].arn
}

# Reporter Lambda - Runs monthly to generate coverage and savings reports
resource "aws_cloudwatch_event_rule" "reporter" {
  count = local.lambda_reporter_enabled && local.report_schedule != null ? 1 : 0

  name                = "${local.module_name}-reporter"
  description         = "Triggers Reporter Lambda to generate periodic coverage and savings reports"
  schedule_expression = local.report_schedule

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "reporter" {
  count = local.lambda_reporter_enabled && local.report_schedule != null ? 1 : 0

  rule      = aws_cloudwatch_event_rule.reporter[0].name
  target_id = "ReporterLambda"
  arn       = aws_lambda_function.reporter[0].arn
}

resource "aws_lambda_permission" "reporter_eventbridge" {
  count = local.lambda_reporter_enabled && local.report_schedule != null ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reporter[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reporter[0].arn
}
