# Module outputs


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


output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications"
  value       = aws_sns_topic.notifications.arn
}


output "scheduler_lambda_arn" {
  description = "ARN of the Scheduler Lambda function"
  value       = local.lambda_scheduler_enabled ? aws_lambda_function.scheduler[0].arn : null
}

output "scheduler_lambda_name" {
  description = "Name of the Scheduler Lambda function"
  value       = local.lambda_scheduler_enabled ? aws_lambda_function.scheduler[0].function_name : null
}

output "purchaser_lambda_arn" {
  description = "ARN of the Purchaser Lambda function"
  value       = local.lambda_purchaser_enabled ? aws_lambda_function.purchaser[0].arn : null
}

output "purchaser_lambda_name" {
  description = "Name of the Purchaser Lambda function"
  value       = local.lambda_purchaser_enabled ? aws_lambda_function.purchaser[0].function_name : null
}

output "reporter_lambda_arn" {
  description = "ARN of the Reporter Lambda function"
  value       = local.lambda_reporter_enabled ? aws_lambda_function.reporter[0].arn : null
}

output "reporter_lambda_name" {
  description = "Name of the Reporter Lambda function"
  value       = local.lambda_reporter_enabled ? aws_lambda_function.reporter[0].function_name : null
}


output "scheduler_rule_arn" {
  description = "ARN of the EventBridge rule for Scheduler Lambda"
  value       = local.lambda_scheduler_enabled && local.scheduler_schedule != null ? aws_cloudwatch_event_rule.scheduler[0].arn : null
}

output "scheduler_rule_name" {
  description = "Name of the EventBridge rule for Scheduler Lambda"
  value       = local.lambda_scheduler_enabled && local.scheduler_schedule != null ? aws_cloudwatch_event_rule.scheduler[0].name : null
}

output "purchaser_rule_arn" {
  description = "ARN of the EventBridge rule for Purchaser Lambda"
  value       = local.lambda_purchaser_enabled && local.purchaser_schedule != null ? aws_cloudwatch_event_rule.purchaser[0].arn : null
}

output "purchaser_rule_name" {
  description = "Name of the EventBridge rule for Purchaser Lambda"
  value       = local.lambda_purchaser_enabled && local.purchaser_schedule != null ? aws_cloudwatch_event_rule.purchaser[0].name : null
}

output "reporter_rule_arn" {
  description = "ARN of the EventBridge rule for Reporter Lambda"
  value       = local.lambda_reporter_enabled && local.report_schedule != null ? aws_cloudwatch_event_rule.reporter[0].arn : null
}

output "reporter_rule_name" {
  description = "Name of the EventBridge rule for Reporter Lambda"
  value       = local.lambda_reporter_enabled && local.report_schedule != null ? aws_cloudwatch_event_rule.reporter[0].name : null
}


output "reports_bucket_name" {
  description = "Name of the reports bucket"
  value       = aws_s3_bucket.reports.id
}

output "reports_bucket_arn" {
  description = "ARN of the reports bucket"
  value       = aws_s3_bucket.reports.arn
}


output "scheduler_role_arn" {
  description = "ARN of the Scheduler Lambda execution role"
  value       = local.lambda_scheduler_enabled ? aws_iam_role.scheduler[0].arn : null
}

output "purchaser_role_arn" {
  description = "ARN of the Purchaser Lambda execution role"
  value       = local.lambda_purchaser_enabled ? aws_iam_role.purchaser[0].arn : null
}

output "reporter_role_arn" {
  description = "ARN of the Reporter Lambda execution role"
  value       = local.lambda_reporter_enabled ? aws_iam_role.reporter[0].arn : null
}


output "scheduler_error_alarm_arn" {
  description = "ARN of the Scheduler Lambda error alarm"
  value       = local.lambda_scheduler_enabled && local.lambda_scheduler_error_alarm_enabled ? aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].arn : null
}

output "purchaser_error_alarm_arn" {
  description = "ARN of the Purchaser Lambda error alarm"
  value       = local.lambda_purchaser_enabled && local.lambda_purchaser_error_alarm_enabled ? aws_cloudwatch_metric_alarm.purchaser_error_alarm[0].arn : null
}

output "reporter_error_alarm_arn" {
  description = "ARN of the Reporter Lambda error alarm"
  value       = local.lambda_reporter_enabled && local.lambda_reporter_error_alarm_enabled ? aws_cloudwatch_metric_alarm.reporter_error_alarm[0].arn : null
}

output "dlq_alarm_arn" {
  description = "ARN of the DLQ depth alarm"
  value       = local.enable_dlq_alarm ? aws_cloudwatch_metric_alarm.dlq_alarm[0].arn : null
}


output "module_configuration" {
  description = "Module configuration summary"
  value = {
    compute_sp_enabled   = local.compute_enabled
    database_sp_enabled  = local.database_enabled
    database_sp_term     = local.database_sp_term
    database_sp_payment  = local.database_sp_payment_option
    sagemaker_sp_enabled = local.sagemaker_enabled
    sagemaker_sp_term    = local.sagemaker_term
    sagemaker_sp_payment = local.sagemaker_payment_option
    coverage_target      = local.coverage_target_percent
    max_coverage_cap     = local.max_coverage_cap
    dry_run              = local.dry_run
    scheduler_schedule   = local.scheduler_schedule
    purchaser_schedule   = local.purchaser_schedule
    notification_emails  = length(local.notification_emails)
  }
}


output "database_sp_configuration" {
  description = "Database Savings Plans configuration for monitoring"
  value = {
    enabled        = local.database_enabled
    term           = local.database_sp_term
    payment_option = local.database_sp_payment_option
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
  value       = local.database_enabled ? "true" : "false"
}


output "sagemaker_sp_configuration" {
  description = "SageMaker Savings Plans configuration for monitoring"
  value = {
    enabled        = local.sagemaker_enabled
    term           = local.sagemaker_term
    payment_option = local.sagemaker_payment_option
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
  value       = local.sagemaker_enabled ? "true" : "false"
}
