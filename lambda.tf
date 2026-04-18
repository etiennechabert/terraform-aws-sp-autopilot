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
    variables = merge(
      local.common_lambda_env,
      local.strategy_lambda_env,
      {
        QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
        RENEWAL_WINDOW_DAYS         = tostring(local.renewal_window_days)
        PURCHASE_COOLDOWN_DAYS      = tostring(local.purchase_cooldown_days)
        MIN_COMMITMENT_PER_PLAN     = tostring(local.min_commitment_per_plan)
        MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_scheduler_assume_role_arn
      },
    )
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
    variables = merge(
      local.common_lambda_env,
      {
        QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
        RENEWAL_WINDOW_DAYS         = tostring(local.renewal_window_days)
        SLACK_WEBHOOK_URL           = local.slack_webhook_url
        TEAMS_WEBHOOK_URL           = local.teams_webhook_url
        MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_purchaser_assume_role_arn
      },
    )
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
    variables = merge(
      local.common_lambda_env,
      local.strategy_lambda_env,
      {
        REPORTS_BUCKET              = aws_s3_bucket.reports.id
        REPORT_FORMAT               = local.report_format
        EMAIL_REPORTS               = tostring(local.email_reports)
        INCLUDE_DEBUG_DATA          = tostring(local.include_debug_data)
        SLACK_WEBHOOK_URL           = local.slack_webhook_url
        TEAMS_WEBHOOK_URL           = local.teams_webhook_url
        LOW_UTILIZATION_THRESHOLD   = tostring(local.low_utilization_threshold)
        MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_reporter_assume_role_arn
      },
    )
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

  # Shared module
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }

  # Shared strategy sub-packages
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared/target_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/target_strategies/${source.value}")
      filename = "shared/target_strategies/${source.value}"
    }
  }

  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared/split_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/split_strategies/${source.value}")
      filename = "shared/split_strategies/${source.value}"
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

  # Shared strategy sub-packages
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared/target_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/target_strategies/${source.value}")
      filename = "shared/target_strategies/${source.value}"
    }
  }

  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared/split_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/split_strategies/${source.value}")
      filename = "shared/split_strategies/${source.value}"
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

  # Shared module
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }

  # Shared strategy sub-packages
  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared/target_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/target_strategies/${source.value}")
      filename = "shared/target_strategies/${source.value}"
    }
  }

  dynamic "source" {
    for_each = fileset("${path.module}/lambda/shared/split_strategies", "*.py")
    content {
      content  = file("${path.module}/lambda/shared/split_strategies/${source.value}")
      filename = "shared/split_strategies/${source.value}"
    }
  }
}

