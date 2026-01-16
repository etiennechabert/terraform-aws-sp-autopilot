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

  depends_on = [null_resource.scheduler_add_shared]

  environment {
    variables = {
      QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      DRY_RUN                     = tostring(local.dry_run)
      ENABLE_COMPUTE_SP           = tostring(local.compute_enabled)
      ENABLE_DATABASE_SP          = tostring(local.database_enabled)
      ENABLE_SAGEMAKER_SP         = tostring(local.sagemaker_enabled)
      COVERAGE_TARGET_PERCENT     = tostring(local.coverage_target_percent)
      MAX_PURCHASE_PERCENT        = tostring(local.max_purchase_percent)
      RENEWAL_WINDOW_DAYS         = tostring(local.renewal_window_days)
      LOOKBACK_DAYS               = tostring(local.lookback_days)
      MIN_DATA_DAYS               = tostring(local.min_data_days)
      MIN_COMMITMENT_PER_PLAN     = tostring(local.min_commitment_per_plan)
      COMPUTE_SP_TERM_MIX         = jsonencode(local.compute_term_mix)
      COMPUTE_SP_PAYMENT_OPTION   = local.compute_payment_option
      SAGEMAKER_SP_TERM_MIX       = jsonencode(local.sagemaker_term_mix)
      SAGEMAKER_SP_PAYMENT_OPTION = local.sagemaker_payment_option
      PARTIAL_UPFRONT_PERCENT     = tostring(local.compute_partial_upfront_percent)
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

  depends_on = [null_resource.purchaser_add_shared]

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

  depends_on = [null_resource.reporter_add_shared]

  environment {
    variables = {
      REPORTS_BUCKET              = aws_s3_bucket.reports.id
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      REPORT_FORMAT               = local.report_format
      EMAIL_REPORTS               = tostring(local.email_reports)
      SLACK_WEBHOOK_URL           = local.slack_webhook_url
      TEAMS_WEBHOOK_URL           = local.teams_webhook_url
      MANAGEMENT_ACCOUNT_ROLE_ARN = local.lambda_reporter_assume_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

# ============================================================================
# Lambda Deployment Packages
# ============================================================================

# Build Lambda deployment packages with correct directory structure
# Run build-lambda-zips.sh before terraform apply to generate the ZIP files
# Each ZIP contains: function code at root + shared/ subdirectory

# Scheduler Lambda deployment package
data "archive_file" "scheduler" {
  type             = "zip"
  source_dir       = "${path.module}/lambda/scheduler"
  output_path      = "${path.module}/scheduler.zip"
  output_file_mode = "0666"

  # Include only Python files, exclude tests and docs
  excludes = [
    ".pytest_cache",
    "__pycache__",
    ".coverage",
    "htmlcov",
    "tests",
    "TESTING.md",
    "README.md",
    "pytest.ini",
    "requirements.txt",
    "test_dry_run.sh",
    "integration_test_dry_run.md"
  ]
}

# Copy shared module into scheduler package
resource "null_resource" "scheduler_add_shared" {
  triggers = {
    zip_changed    = data.archive_file.scheduler.output_base64sha256
    shared_changed = filemd5("${path.module}/lambda/shared/handler_utils.py")
  }

  provisioner "local-exec" {
    command     = "cd lambda && zip -u ../scheduler.zip shared/*.py"
    working_dir = path.module
    interpreter = ["bash", "-c"]
  }

  depends_on = [data.archive_file.scheduler]
}

# Purchaser Lambda deployment package
data "archive_file" "purchaser" {
  type             = "zip"
  source_dir       = "${path.module}/lambda/purchaser"
  output_path      = "${path.module}/purchaser.zip"
  output_file_mode = "0666"

  excludes = [
    ".pytest_cache",
    "__pycache__",
    ".coverage",
    "htmlcov",
    "tests",
    "TESTING.md",
    "README.md",
    "pytest.ini",
    "requirements.txt"
  ]
}

# Copy shared module into purchaser package
resource "null_resource" "purchaser_add_shared" {
  triggers = {
    zip_changed    = data.archive_file.purchaser.output_base64sha256
    shared_changed = filemd5("${path.module}/lambda/shared/handler_utils.py")
  }

  provisioner "local-exec" {
    command     = "cd lambda && zip -u ../purchaser.zip shared/*.py"
    working_dir = path.module
    interpreter = ["bash", "-c"]
  }

  depends_on = [data.archive_file.purchaser]
}

# Reporter Lambda deployment package
data "archive_file" "reporter" {
  type             = "zip"
  source_dir       = "${path.module}/lambda/reporter"
  output_path      = "${path.module}/reporter.zip"
  output_file_mode = "0666"

  excludes = [
    ".pytest_cache",
    "__pycache__",
    ".coverage",
    "htmlcov",
    "tests",
    "TESTING.md",
    "README.md",
    "pytest.ini",
    "requirements.txt"
  ]
}

# Copy shared module into reporter package
resource "null_resource" "reporter_add_shared" {
  triggers = {
    zip_changed    = data.archive_file.reporter.output_base64sha256
    shared_changed = filemd5("${path.module}/lambda/shared/handler_utils.py")
  }

  provisioner "local-exec" {
    command     = "cd lambda && zip -u ../reporter.zip shared/*.py"
    working_dir = path.module
    interpreter = ["bash", "-c"]
  }

  depends_on = [data.archive_file.reporter]
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
