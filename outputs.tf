# AWS Savings Plans Automation Module - Outputs

# ============================================================================
# SQS Queue Outputs
# ============================================================================

output "queue_url" {
  description = "URL of the purchase intents queue"
  value       = aws_sqs_queue.purchase_intents.url
}

output "queue_arn" {
  description = "ARN of the purchase intents queue"
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
  value       = aws_lambda_function.scheduler.arn
}

output "scheduler_lambda_name" {
  description = "Name of the Scheduler Lambda function"
  value       = aws_lambda_function.scheduler.function_name
}

output "purchaser_lambda_arn" {
  description = "ARN of the Purchaser Lambda function"
  value       = aws_lambda_function.purchaser.arn
}

output "purchaser_lambda_name" {
  description = "Name of the Purchaser Lambda function"
  value       = aws_lambda_function.purchaser.function_name
}

output "reporter_lambda_arn" {
  description = "ARN of the Reporter Lambda function"
  value       = aws_lambda_function.reporter.arn
}

output "reporter_lambda_name" {
  description = "Name of the Reporter Lambda function"
  value       = aws_lambda_function.reporter.function_name
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

output "reporter_rule_arn" {
  description = "ARN of the EventBridge rule for Reporter Lambda"
  value       = var.enable_reports ? aws_cloudwatch_event_rule.reporter[0].arn : null
}

output "reporter_rule_name" {
  description = "Name of the EventBridge rule for Reporter Lambda"
  value       = var.enable_reports ? aws_cloudwatch_event_rule.reporter[0].name : null
}

# ============================================================================
# S3 Bucket Outputs
# ============================================================================

output "reports_bucket_name" {
  description = "Name of the reports bucket"
  value       = aws_s3_bucket.reports.id
}

output "reports_bucket_arn" {
  description = "ARN of the reports bucket"
  value       = aws_s3_bucket.reports.arn
}

# ============================================================================
# IAM Role Outputs
# ============================================================================

output "scheduler_role_arn" {
  description = "ARN of the Scheduler Lambda execution role"
  value       = aws_iam_role.scheduler.arn
}

output "purchaser_role_arn" {
  description = "ARN of the Purchaser Lambda execution role"
  value       = aws_iam_role.purchaser.arn
}

output "reporter_role_arn" {
  description = "ARN of the Reporter Lambda execution role"
  value       = aws_iam_role.reporter.arn
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

output "reporter_error_alarm_arn" {
  description = "ARN of the Reporter Lambda error alarm"
  value       = var.enable_lambda_error_alarm ? aws_cloudwatch_metric_alarm.reporter_error_alarm[0].arn : null
}

output "dlq_alarm_arn" {
  description = "ARN of the DLQ depth alarm"
  value       = var.enable_dlq_alarm ? aws_cloudwatch_metric_alarm.dlq_alarm[0].arn : null
}

# ============================================================================
# Configuration Outputs
# ============================================================================

output "module_configuration" {
  description = "Module configuration summary"
  value = {
    compute_sp_enabled    = var.enable_compute_sp
    database_sp_enabled   = var.enable_database_sp
    database_sp_term      = var.database_sp_term
    database_sp_payment   = var.database_sp_payment_option
    sagemaker_sp_enabled  = var.enable_sagemaker_sp
    sagemaker_sp_term_mix = var.sagemaker_sp_term_mix
    sagemaker_sp_payment  = var.sagemaker_sp_payment_option
    coverage_target       = var.coverage_target_percent
    max_coverage_cap      = var.max_coverage_cap
    dry_run               = var.dry_run
    scheduler_schedule    = var.scheduler_schedule
    purchaser_schedule    = var.purchaser_schedule
    notification_emails   = length(var.notification_emails)
  }
}

# ============================================================================
# Database SP Monitoring Outputs
# ============================================================================

output "database_sp_configuration" {
  description = "Database Savings Plans configuration for monitoring"
  value = {
    enabled        = var.enable_database_sp
    term           = var.database_sp_term
    payment_option = var.database_sp_payment_option
    supported_services = [
      "RDS",
      "Aurora",
      "DynamoDB",
      "ElastiCache (Valkey)",
      "DocumentDB",
      "Neptune",
      "Keyspaces",
      "Timestream",
      "DMS"
    ]
    aws_constraints = {
      term_fixed           = "ONE_YEAR only"
      payment_option_fixed = "NO_UPFRONT only"
      configurable         = false
    }
  }
}

output "lambda_environment_database_sp" {
  description = "Database SP enablement flag for Lambda functions"
  value       = var.enable_database_sp ? "true" : "false"
}

# ============================================================================
# SageMaker SP Monitoring Outputs
# ============================================================================

output "sagemaker_sp_configuration" {
  description = "SageMaker Savings Plans configuration for monitoring"
  value = {
    enabled        = var.enable_sagemaker_sp
    term_mix       = var.sagemaker_sp_term_mix
    payment_option = var.sagemaker_sp_payment_option
    supported_services = [
      "SageMaker"
    ]
    aws_constraints = {
      terms_available = "ONE_YEAR and THREE_YEAR"
      payment_options = "ALL_UPFRONT, PARTIAL_UPFRONT, NO_UPFRONT"
      configurable    = true
    }
  }
}

output "lambda_environment_sagemaker_sp" {
  description = "SageMaker SP enablement flag for Lambda functions"
  value       = var.enable_sagemaker_sp ? "true" : "false"
}
