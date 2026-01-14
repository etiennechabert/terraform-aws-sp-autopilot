# Test Fixture: Outputs
# Purpose: Expose module outputs for integration testing

# ============================================================================
# SQS Queue Outputs
# ============================================================================

output "queue_url" {
  description = "URL of the SQS queue holding purchase intents"
  value       = module.sp_autopilot.queue_url
}

output "queue_arn" {
  description = "ARN of the SQS queue"
  value       = module.sp_autopilot.queue_arn
}

output "dlq_url" {
  description = "URL of the dead letter queue"
  value       = module.sp_autopilot.dlq_url
}

output "dlq_arn" {
  description = "ARN of the dead letter queue"
  value       = module.sp_autopilot.dlq_arn
}

# ============================================================================
# SNS Topic Outputs
# ============================================================================

output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications"
  value       = module.sp_autopilot.sns_topic_arn
}

# ============================================================================
# Lambda Function Outputs
# ============================================================================

output "scheduler_lambda_arn" {
  description = "ARN of the Scheduler Lambda function"
  value       = module.sp_autopilot.scheduler_lambda_arn
}

output "scheduler_lambda_name" {
  description = "Name of the Scheduler Lambda function"
  value       = module.sp_autopilot.scheduler_lambda_name
}

output "purchaser_lambda_arn" {
  description = "ARN of the Purchaser Lambda function"
  value       = module.sp_autopilot.purchaser_lambda_arn
}

output "purchaser_lambda_name" {
  description = "Name of the Purchaser Lambda function"
  value       = module.sp_autopilot.purchaser_lambda_name
}

# ============================================================================
# EventBridge Schedule Outputs
# ============================================================================

output "scheduler_rule_arn" {
  description = "ARN of the EventBridge rule for Scheduler Lambda"
  value       = module.sp_autopilot.scheduler_rule_arn
}

output "scheduler_rule_name" {
  description = "Name of the EventBridge rule for Scheduler Lambda"
  value       = module.sp_autopilot.scheduler_rule_name
}

output "purchaser_rule_arn" {
  description = "ARN of the EventBridge rule for Purchaser Lambda"
  value       = module.sp_autopilot.purchaser_rule_arn
}

output "purchaser_rule_name" {
  description = "Name of the EventBridge rule for Purchaser Lambda"
  value       = module.sp_autopilot.purchaser_rule_name
}

# ============================================================================
# IAM Role Outputs
# ============================================================================

output "scheduler_role_arn" {
  description = "ARN of the Scheduler Lambda execution role"
  value       = module.sp_autopilot.scheduler_role_arn
}

output "purchaser_role_arn" {
  description = "ARN of the Purchaser Lambda execution role"
  value       = module.sp_autopilot.purchaser_role_arn
}

# ============================================================================
# CloudWatch Alarm Outputs
# ============================================================================

output "scheduler_error_alarm_arn" {
  description = "ARN of the Scheduler Lambda error alarm"
  value       = module.sp_autopilot.scheduler_error_alarm_arn
}

output "purchaser_error_alarm_arn" {
  description = "ARN of the Purchaser Lambda error alarm"
  value       = module.sp_autopilot.purchaser_error_alarm_arn
}

output "dlq_alarm_arn" {
  description = "ARN of the DLQ depth alarm"
  value       = module.sp_autopilot.dlq_alarm_arn
}

# ============================================================================
# Configuration Outputs
# ============================================================================

output "module_configuration" {
  description = "Current module configuration summary"
  value       = module.sp_autopilot.module_configuration
}

# ============================================================================
# Database SP Monitoring Outputs
# ============================================================================

output "database_sp_configuration" {
  description = "Database Savings Plans specific configuration for monitoring"
  value       = module.sp_autopilot.database_sp_configuration
}

output "lambda_environment_database_sp" {
  description = "Database SP environment variable value passed to Lambda functions"
  value       = module.sp_autopilot.lambda_environment_database_sp
}
