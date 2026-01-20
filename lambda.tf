# Lambda Functions and Deployment Packages
# Purpose: AWS Lambda functions for Savings Plans automation

# ============================================================================
# Lambda Functions
# ============================================================================

resource "aws_lambda_function" "scheduler" {
  count = local.lambda_scheduler_enabled ? 1 : 0

  function_name = "${local.module_name}-scheduler"
  description   = "Analyzes usage and queues Savings Plans purchase recommendations"

  # Deploy actual Lambda code with proper configuration
  role    = aws_iam_role.scheduler[0].arn
  handler = "handler.handler"
  runtime = "python3.11"

  # Performance configuration
  memory_size = local.lambda_scheduler_memory_size
  timeout     = local.lambda_scheduler_timeout

  # Deploy actual Lambda code from lambda/scheduler directory
  filename         = data.archive_file.scheduler.output_path
  source_code_hash = data.archive_file.scheduler.output_base64sha256


  environment {
    variables = {
      QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      DRY_RUN                     = tostring(local.dry_run)
      ENABLE_COMPUTE_SP           = tostring(local.compute_enabled)
      ENABLE_DATABASE_SP          = tostring(local.database_enabled)
      ENABLE_SAGEMAKER_SP         = tostring(local.sagemaker_enabled)
      COVERAGE_TARGET_PERCENT     = tostring(local.coverage_target_percent)
      PURCHASE_STRATEGY_TYPE      = local.purchase_strategy_type
      MAX_PURCHASE_PERCENT        = tostring(local.max_purchase_percent)
      MIN_PURCHASE_PERCENT        = tostring(local.min_purchase_percent)
      RENEWAL_WINDOW_DAYS         = tostring(local.renewal_window_days)
      LOOKBACK_DAYS               = tostring(local.lookback_days)
      GRANULARITY                 = local.granularity
      MIN_COMMITMENT_PER_PLAN     = tostring(local.min_commitment_per_plan)
      COMPUTE_SP_TERM             = local.compute_term
      COMPUTE_SP_PAYMENT_OPTION   = local.compute_payment_option
      SAGEMAKER_SP_TERM           = local.sagemaker_term
      SAGEMAKER_SP_PAYMENT_OPTION = local.sagemaker_payment_option
      MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_scheduler_assume_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "purchaser" {
  count = local.lambda_purchaser_enabled ? 1 : 0

  function_name = "${local.module_name}-purchaser"
  description   = "Executes Savings Plans purchases from queue"

  # Deploy actual Lambda code with proper configuration
  role    = aws_iam_role.purchaser[0].arn
  handler = "handler.handler"
  runtime = "python3.11"

  # Performance configuration
  memory_size = local.lambda_purchaser_memory_size
  timeout     = local.lambda_purchaser_timeout

  # Deploy actual Lambda code from lambda/purchaser directory
  filename         = data.archive_file.purchaser.output_path
  source_code_hash = data.archive_file.purchaser.output_base64sha256


  environment {
    variables = {
      QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      MAX_COVERAGE_CAP            = tostring(local.max_coverage_cap)
      RENEWAL_WINDOW_DAYS         = tostring(local.renewal_window_days)
      MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_purchaser_assume_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "reporter" {
  count = local.lambda_reporter_enabled ? 1 : 0

  function_name = "${local.module_name}-reporter"
  description   = "Generates periodic coverage and savings reports"

  # Deploy actual Lambda code with proper configuration
  role    = aws_iam_role.reporter[0].arn
  handler = "handler.handler"
  runtime = "python3.11"

  # Performance configuration
  memory_size = local.lambda_reporter_memory_size
  timeout     = local.lambda_reporter_timeout

  # Deploy actual Lambda code from lambda/reporter directory
  filename         = data.archive_file.reporter.output_path
  source_code_hash = data.archive_file.reporter.output_base64sha256


  environment {
    variables = {
      REPORTS_BUCKET              = aws_s3_bucket.reports.id
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      REPORT_FORMAT               = local.report_format
      EMAIL_REPORTS               = tostring(local.email_reports)
      SLACK_WEBHOOK_URL           = local.slack_webhook_url
      TEAMS_WEBHOOK_URL           = local.teams_webhook_url
      LOW_UTILIZATION_THRESHOLD   = tostring(local.low_utilization_threshold)
      MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_reporter_assume_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

# ============================================================================
# Lambda Deployment Packages
# ============================================================================

# Scheduler Lambda deployment package
data "archive_file" "scheduler" {
  type             = "zip"
  output_path      = "${path.module}/scheduler.zip"
  output_file_mode = "0666"

  # Include function code at root
  source {
    content  = file("${path.module}/lambda/scheduler/handler.py")
    filename = "handler.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/config.py")
    filename = "config.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/sp_coverage.py")
    filename = "sp_coverage.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/email_notifications.py")
    filename = "email_notifications.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/purchase_calculator.py")
    filename = "purchase_calculator.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/queue_manager.py")
    filename = "queue_manager.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/recommendations.py")
    filename = "recommendations.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/dichotomy_strategy.py")
    filename = "dichotomy_strategy.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/fixed_strategy.py")
    filename = "fixed_strategy.py"
  }
  source {
    content  = file("${path.module}/lambda/scheduler/follow_aws_strategy.py")
    filename = "follow_aws_strategy.py"
  }

  # Include shared module
  source {
    content  = file("${path.module}/lambda/shared/handler_utils.py")
    filename = "shared/handler_utils.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/aws_utils.py")
    filename = "shared/aws_utils.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/local_mode.py")
    filename = "shared/local_mode.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/queue_adapter.py")
    filename = "shared/queue_adapter.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/storage_adapter.py")
    filename = "shared/storage_adapter.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/notifications.py")
    filename = "shared/notifications.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/config_validation.py")
    filename = "shared/config_validation.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/spending_analyzer.py")
    filename = "shared/spending_analyzer.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/purchase_optimizer.py")
    filename = "shared/purchase_optimizer.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/__init__.py")
    filename = "shared/__init__.py"
  }
}

# Purchaser Lambda deployment package
data "archive_file" "purchaser" {
  type             = "zip"
  output_path      = "${path.module}/purchaser.zip"
  output_file_mode = "0666"

  # Include function code at root
  source {
    content  = file("${path.module}/lambda/purchaser/handler.py")
    filename = "handler.py"
  }
  source {
    content  = file("${path.module}/lambda/purchaser/validation.py")
    filename = "validation.py"
  }

  # Include shared module
  source {
    content  = file("${path.module}/lambda/shared/handler_utils.py")
    filename = "shared/handler_utils.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/aws_utils.py")
    filename = "shared/aws_utils.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/local_mode.py")
    filename = "shared/local_mode.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/queue_adapter.py")
    filename = "shared/queue_adapter.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/storage_adapter.py")
    filename = "shared/storage_adapter.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/notifications.py")
    filename = "shared/notifications.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/config_validation.py")
    filename = "shared/config_validation.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/__init__.py")
    filename = "shared/__init__.py"
  }
}

# Reporter Lambda deployment package
data "archive_file" "reporter" {
  type             = "zip"
  output_path      = "${path.module}/reporter.zip"
  output_file_mode = "0666"

  # Include function code at root
  source {
    content  = file("${path.module}/lambda/reporter/handler.py")
    filename = "handler.py"
  }

  # Include shared module
  source {
    content  = file("${path.module}/lambda/shared/handler_utils.py")
    filename = "shared/handler_utils.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/aws_utils.py")
    filename = "shared/aws_utils.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/local_mode.py")
    filename = "shared/local_mode.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/queue_adapter.py")
    filename = "shared/queue_adapter.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/storage_adapter.py")
    filename = "shared/storage_adapter.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/notifications.py")
    filename = "shared/notifications.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/config_validation.py")
    filename = "shared/config_validation.py"
  }
  source {
    content  = file("${path.module}/lambda/shared/__init__.py")
    filename = "shared/__init__.py"
  }
}

# Create placeholder ZIP files
data "archive_file" "scheduler_placeholder" {
  type        = "zip"
  output_path = "${path.module}/.terraform/scheduler_placeholder.zip"

  source {
    content  = <<-EOT
      def handler(event, context):
          print("Scheduler Lambda placeholder - not yet implemented")
          return {"statusCode": 200, "body": "Placeholder"}
    EOT
    filename = "index.py"
  }
}

data "archive_file" "purchaser_placeholder" {
  type        = "zip"
  output_path = "${path.module}/.terraform/purchaser_placeholder.zip"

  source {
    content  = <<-EOT
      def handler(event, context):
          print("Purchaser Lambda placeholder - not yet implemented")
          return {"statusCode": 200, "body": "Placeholder"}
    EOT
    filename = "index.py"
  }
}
