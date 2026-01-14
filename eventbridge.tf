# AWS Savings Plans Automation Module - EventBridge Schedules
# Version: 1.0
# Purpose: Defines EventBridge schedules for automated Lambda function triggers

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

# Reporter Lambda - Runs monthly to generate coverage and savings reports
resource "aws_cloudwatch_event_rule" "reporter" {
  count = var.enable_reports ? 1 : 0

  name                = "${local.module_name}-reporter"
  description         = "Triggers Reporter Lambda to generate periodic coverage and savings reports"
  schedule_expression = var.report_schedule

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "reporter" {
  count = var.enable_reports ? 1 : 0

  rule      = aws_cloudwatch_event_rule.reporter[0].name
  target_id = "ReporterLambda"
  arn       = aws_lambda_function.reporter.arn
}

resource "aws_lambda_permission" "reporter_eventbridge" {
  count = var.enable_reports ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reporter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reporter[0].arn
}
