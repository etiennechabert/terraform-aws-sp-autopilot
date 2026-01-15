# Lambda Functions and Deployment Packages
# Purpose: AWS Lambda functions for Savings Plans automation

# ============================================================================
# Lambda Functions
# ============================================================================

resource "aws_lambda_function" "scheduler" {
  function_name = "${local.module_name}-scheduler"
  description   = "Analyzes usage and queues Savings Plans purchase recommendations"

  # Deploy actual Lambda code with proper configuration
  role    = aws_iam_role.scheduler.arn
  handler = "handler.handler"
  runtime = "python3.11"

  # Performance configuration
  memory_size = var.lambda_scheduler_memory_size
  timeout     = var.lambda_scheduler_timeout

  # Deploy actual Lambda code from lambda/scheduler directory
  filename         = data.archive_file.scheduler.output_path
  source_code_hash = data.archive_file.scheduler.output_base64sha256

  depends_on = [null_resource.scheduler_add_shared]

  environment {
    variables = {
      QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      DRY_RUN                     = tostring(var.dry_run)
      ENABLE_COMPUTE_SP           = tostring(var.enable_compute_sp)
      ENABLE_DATABASE_SP          = tostring(var.enable_database_sp)
      ENABLE_SAGEMAKER_SP         = tostring(var.enable_sagemaker_sp)
      COVERAGE_TARGET_PERCENT     = tostring(var.coverage_target_percent)
      MAX_PURCHASE_PERCENT        = tostring(var.max_purchase_percent)
      RENEWAL_WINDOW_DAYS         = tostring(var.renewal_window_days)
      LOOKBACK_DAYS               = tostring(var.lookback_days)
      MIN_DATA_DAYS               = tostring(var.min_data_days)
      MIN_COMMITMENT_PER_PLAN     = tostring(var.min_commitment_per_plan)
      COMPUTE_SP_TERM_MIX         = jsonencode(var.compute_sp_term_mix)
      COMPUTE_SP_PAYMENT_OPTION   = var.compute_sp_payment_option
      SAGEMAKER_SP_TERM_MIX       = jsonencode(var.sagemaker_sp_term_mix)
      SAGEMAKER_SP_PAYMENT_OPTION = var.sagemaker_sp_payment_option
      PARTIAL_UPFRONT_PERCENT     = tostring(var.partial_upfront_percent)
      MANAGEMENT_ACCOUNT_ROLE_ARN = var.management_account_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "purchaser" {
  function_name = "${local.module_name}-purchaser"
  description   = "Executes Savings Plans purchases from queue"

  # Deploy actual Lambda code with proper configuration
  role    = aws_iam_role.purchaser.arn
  handler = "handler.handler"
  runtime = "python3.11"

  # Performance configuration
  memory_size = var.lambda_purchaser_memory_size
  timeout     = var.lambda_purchaser_timeout

  # Deploy actual Lambda code from lambda/purchaser directory
  filename         = data.archive_file.purchaser.output_path
  source_code_hash = data.archive_file.purchaser.output_base64sha256

  depends_on = [null_resource.purchaser_add_shared]

  environment {
    variables = {
      QUEUE_URL                   = aws_sqs_queue.purchase_intents.url
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      MAX_COVERAGE_CAP            = tostring(var.max_coverage_cap)
      RENEWAL_WINDOW_DAYS         = tostring(var.renewal_window_days)
      MANAGEMENT_ACCOUNT_ROLE_ARN = var.management_account_role_arn
      TAGS                        = jsonencode(local.common_tags)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "reporter" {
  function_name = "${local.module_name}-reporter"
  description   = "Generates periodic coverage and savings reports"

  # Deploy actual Lambda code with proper configuration
  role    = aws_iam_role.reporter.arn
  handler = "handler.handler"
  runtime = "python3.11"

  # Performance configuration
  memory_size = var.lambda_reporter_memory_size
  timeout     = var.lambda_reporter_timeout

  # Deploy actual Lambda code from lambda/reporter directory
  filename         = data.archive_file.reporter.output_path
  source_code_hash = data.archive_file.reporter.output_base64sha256

  depends_on = [null_resource.reporter_add_shared]

  environment {
    variables = {
      REPORTS_BUCKET              = aws_s3_bucket.reports.id
      SNS_TOPIC_ARN               = aws_sns_topic.notifications.arn
      REPORT_FORMAT               = var.report_format
      EMAIL_REPORTS               = tostring(var.email_reports)
      SLACK_WEBHOOK_URL           = var.slack_webhook_url
      TEAMS_WEBHOOK_URL           = var.teams_webhook_url
      MANAGEMENT_ACCOUNT_ROLE_ARN = var.management_account_role_arn
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
