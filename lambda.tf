# Lambda functions and deployment packages


resource "aws_lambda_function" "scheduler" {
  count = local.lambda_scheduler_enabled ? 1 : 0

  function_name = "${local.module_name}-scheduler"
  description   = "Analyzes usage and queues Savings Plans purchase recommendations"

  # Deploy actual Lambda code with proper configuration
  role    = aws_iam_role.scheduler[0].arn
  handler = "handler.handler"
  runtime = "python3.14"

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
      TARGET_STRATEGY_TYPE        = local.target_strategy_type
      SPLIT_STRATEGY_TYPE         = local.split_strategy_type
      DYNAMIC_RISK_LEVEL          = local.dynamic_risk_level
      LINEAR_STEP_PERCENT         = tostring(local.linear_step_percent)
      MAX_PURCHASE_PERCENT        = tostring(local.max_purchase_percent)
      MIN_PURCHASE_PERCENT        = tostring(local.min_purchase_percent)
      RENEWAL_WINDOW_DAYS         = tostring(local.renewal_window_days)
      LOOKBACK_DAYS               = tostring(local.lookback_days)
      GRANULARITY                 = local.granularity
      MIN_COMMITMENT_PER_PLAN     = tostring(local.min_commitment_per_plan)
      COMPUTE_SP_TERM             = local.compute_term
      COMPUTE_SP_PAYMENT_OPTION   = local.compute_payment_option
      DATABASE_SP_PAYMENT_OPTION  = local.database_sp_payment_option
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
  runtime = "python3.14"

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
      LOOKBACK_DAYS               = tostring(local.lookback_days)
      GRANULARITY                 = local.granularity
      SLACK_WEBHOOK_URL           = local.slack_webhook_url
      TEAMS_WEBHOOK_URL           = local.teams_webhook_url
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
  runtime = "python3.14"

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
      INCLUDE_DEBUG_DATA          = tostring(local.include_debug_data)
      SLACK_WEBHOOK_URL           = local.slack_webhook_url
      TEAMS_WEBHOOK_URL           = local.teams_webhook_url
      LOW_UTILIZATION_THRESHOLD   = tostring(local.low_utilization_threshold)
      LOOKBACK_DAYS               = tostring(local.lookback_days)
      GRANULARITY                 = local.granularity
      ENABLE_COMPUTE_SP           = tostring(local.compute_enabled)
      ENABLE_DATABASE_SP          = tostring(local.database_enabled)
      ENABLE_SAGEMAKER_SP         = tostring(local.sagemaker_enabled)
      COVERAGE_TARGET_PERCENT     = tostring(local.coverage_target_percent)
      TARGET_STRATEGY_TYPE        = local.target_strategy_type
      SPLIT_STRATEGY_TYPE         = local.split_strategy_type
      DYNAMIC_RISK_LEVEL          = local.dynamic_risk_level
      LINEAR_STEP_PERCENT         = tostring(local.linear_step_percent)
      MAX_PURCHASE_PERCENT        = tostring(local.max_purchase_percent)
      MIN_PURCHASE_PERCENT        = tostring(local.min_purchase_percent)
      COMPUTE_SP_TERM             = local.compute_term
      COMPUTE_SP_PAYMENT_OPTION   = local.compute_payment_option
      DATABASE_SP_PAYMENT_OPTION  = local.database_sp_payment_option
      SAGEMAKER_SP_TERM           = local.sagemaker_term
      SAGEMAKER_SP_PAYMENT_OPTION = local.sagemaker_payment_option
      MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_reporter_assume_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}


data "archive_file" "scheduler" {
  type             = "zip"
  output_path      = "${path.module}/scheduler.zip"
  output_file_mode = "0666"

  # Scheduler function code
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/scheduler", "*.py")
    content {
      content  = file("${path.module}/lambda/scheduler/${source.value}")
      filename = source.value
    }
  }

  # Strategy sub-packages
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/scheduler/target_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/scheduler/target_strategies/${source.value}")
      filename = "target_strategies/${source.value}"
    }
  }

  dynamic "source" {
    for_each = fileset("${path.module}/lambda/scheduler/split_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/scheduler/split_strategies/${source.value}")
      filename = "split_strategies/${source.value}"
    }
  }

  # Shared module
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }
}

data "archive_file" "purchaser" {
  type             = "zip"
  output_path      = "${path.module}/purchaser.zip"
  output_file_mode = "0666"

  # Purchaser function code
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/purchaser", "*.py")
    content {
      content  = file("${path.module}/lambda/purchaser/${source.value}")
      filename = source.value
    }
  }

  # Shared module
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }
}

data "archive_file" "reporter" {
  type             = "zip"
  output_path      = "${path.module}/reporter.zip"
  output_file_mode = "0666"

  # Reporter function code
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/reporter", "*.py")
    content {
      content  = file("${path.module}/lambda/reporter/${source.value}")
      filename = source.value
    }
  }

  # Scheduler modules needed by scheduler_preview.py
  dynamic "source" {
    for_each = toset([
      "sp_types.py",
      "follow_aws_strategy.py",
      "recommendations.py",
      "purchase_calculator.py",
    ])
    content {
      content  = file("${path.module}/lambda/scheduler/${source.value}")
      filename = source.value
    }
  }

  # Strategy sub-packages
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/scheduler/target_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/scheduler/target_strategies/${source.value}")
      filename = "target_strategies/${source.value}"
    }
  }

  dynamic "source" {
    for_each = fileset("${path.module}/lambda/scheduler/split_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/scheduler/split_strategies/${source.value}")
      filename = "split_strategies/${source.value}"
    }
  }

  # Shared module
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }
}

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
