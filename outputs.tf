# AWS Savings Plans Automation Module - Outputs

# ============================================================================
# SQS Queue Outputs
# ============================================================================

output "queue_url" {
  description = "URL of the SQS queue holding purchase intents"
  value       = aws_sqs_queue.purchase_intents.url
}

output "queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.purchase_intents.arn
}

output "dlq_url" {
  description = "URL of the dead letter queue"
  value       = aws_sqs_queue.purchase_intents_dlq.url
}

output "dlq_arn" {
  description = "ARN of the dead letter queue"
  value       = aws_sqs_queue.purchase_intents_dlq.arn
}

# ============================================================================
# SNS Topic Outputs
# ============================================================================

output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications"
  value       = aws_sns_topic.notifications.arn
}

# ============================================================================
# Lambda Function Outputs
# ============================================================================

output "scheduler_lambda_arn" {
  description = "ARN of the Scheduler Lambda function"
  value       = "" # To be implemented: aws_lambda_function.scheduler.arn
}

output "scheduler_lambda_name" {
  description = "Name of the Scheduler Lambda function"
  value       = "" # To be implemented: aws_lambda_function.scheduler.function_name
}

output "purchaser_lambda_arn" {
  description = "ARN of the Purchaser Lambda function"
  value       = "" # To be implemented: aws_lambda_function.purchaser.arn
}

output "purchaser_lambda_name" {
  description = "Name of the Purchaser Lambda function"
  value       = "" # To be implemented: aws_lambda_function.purchaser.function_name
}

# ============================================================================
# EventBridge Schedule Outputs
# ============================================================================

output "scheduler_rule_arn" {
  description = "ARN of the EventBridge rule for Scheduler Lambda"
  value       = aws_cloudwatch_event_rule.scheduler.arn
}

output "scheduler_rule_name" {
  description = "Name of the EventBridge rule for Scheduler Lambda"
  value       = aws_cloudwatch_event_rule.scheduler.name
}

output "purchaser_rule_arn" {
  description = "ARN of the EventBridge rule for Purchaser Lambda"
  value       = aws_cloudwatch_event_rule.purchaser.arn
}

output "purchaser_rule_name" {
  description = "Name of the EventBridge rule for Purchaser Lambda"
  value       = aws_cloudwatch_event_rule.purchaser.name
}

# ============================================================================
# IAM Role Outputs
# ============================================================================

output "scheduler_role_arn" {
  description = "ARN of the Scheduler Lambda execution role"
  value       = "" # To be implemented: aws_iam_role.scheduler.arn
}

output "purchaser_role_arn" {
  description = "ARN of the Purchaser Lambda execution role"
  value       = "" # To be implemented: aws_iam_role.purchaser.arn
}

# ============================================================================
# CloudWatch Alarm Outputs
# ============================================================================

output "scheduler_error_alarm_arn" {
  description = "ARN of the Scheduler Lambda error alarm"
  value       = var.enable_lambda_error_alarm ? aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].arn : null
}

output "purchaser_error_alarm_arn" {
  description = "ARN of the Purchaser Lambda error alarm"
  value       = var.enable_lambda_error_alarm ? aws_cloudwatch_metric_alarm.purchaser_error_alarm[0].arn : null
}

output "dlq_alarm_arn" {
  description = "ARN of the DLQ depth alarm"
  value       = var.enable_dlq_alarm ? aws_cloudwatch_metric_alarm.dlq_alarm[0].arn : null
}

output "scheduler_throttle_alarm_arn" {
  description = "ARN of the Scheduler Lambda throttle alarm"
  value       = var.enable_lambda_throttle_alarm ? aws_cloudwatch_metric_alarm.scheduler_throttle_alarm[0].arn : null
}

output "scheduler_duration_alarm_arn" {
  description = "ARN of the Scheduler Lambda duration alarm"
  value       = var.enable_lambda_duration_alarm ? aws_cloudwatch_metric_alarm.scheduler_duration_alarm[0].arn : null
}

output "purchaser_throttle_alarm_arn" {
  description = "ARN of the Purchaser Lambda throttle alarm"
  value       = var.enable_lambda_throttle_alarm ? aws_cloudwatch_metric_alarm.purchaser_throttle_alarm[0].arn : null
}

output "purchaser_duration_alarm_arn" {
  description = "ARN of the Purchaser Lambda duration alarm"
  value       = var.enable_lambda_duration_alarm ? aws_cloudwatch_metric_alarm.purchaser_duration_alarm[0].arn : null
}

# ============================================================================
# Configuration Outputs
# ============================================================================

output "module_configuration" {
  description = "Current module configuration summary"
  value = {
    compute_sp_enabled    = var.enable_compute_sp
    database_sp_enabled   = var.enable_database_sp
    coverage_target       = var.coverage_target_percent
    max_coverage_cap      = var.max_coverage_cap
    dry_run               = var.dry_run
    scheduler_schedule    = var.scheduler_schedule
    purchaser_schedule    = var.purchaser_schedule
    notification_emails   = length(var.notification_emails)
  }
}
