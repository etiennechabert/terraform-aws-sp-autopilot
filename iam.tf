# IAM Roles and Policies
# Purpose: IAM roles and policies for Lambda functions in the Savings Plans Automation module

# ============================================================================
# Scheduler Lambda IAM Role and Policies
# ============================================================================

# Scheduler Lambda IAM Role
resource "aws_iam_role" "scheduler" {
  name        = "${local.module_name}-scheduler"
  description = "IAM role for Scheduler Lambda function - analyzes usage and queues purchase recommendations"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-scheduler-role"
    }
  )
}

# Scheduler Lambda Policy - CloudWatch Logs
resource "aws_iam_role_policy" "scheduler_cloudwatch_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.scheduler.arn}:*"
    }]
  })
}

# Scheduler Lambda Policy - Cost Explorer
resource "aws_iam_role_policy" "scheduler_cost_explorer" {
  name = "cost-explorer"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansUtilization",
        "ce:GetSavingsPlansCoverage",
        "ce:GetCostAndUsage"
      ]
      Resource = "*"
    }]
  })
}

# Scheduler Lambda Policy - SQS
resource "aws_iam_role_policy" "scheduler_sqs" {
  name = "sqs"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:PurgeQueue",
        "sqs:GetQueueAttributes"
      ]
      Resource = aws_sqs_queue.purchase_intents.arn
    }]
  })
}

# Scheduler Lambda Policy - SNS
resource "aws_iam_role_policy" "scheduler_sns" {
  name = "sns"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sns:Publish"
      ]
      Resource = aws_sns_topic.notifications.arn
    }]
  })
}

# Scheduler Lambda Policy - Savings Plans
resource "aws_iam_role_policy" "scheduler_savingsplans" {
  name = "savingsplans"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:DescribeSavingsPlansOfferingRates",
        "savingsplans:DescribeSavingsPlansOfferings"
      ]
      Resource = "*"
    }]
  })
}

# Scheduler Lambda Policy - Assume Role (conditional)
resource "aws_iam_role_policy" "scheduler_assume_role" {
  count = var.management_account_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = var.management_account_role_arn
    }]
  })
}

# ============================================================================
# Purchaser Lambda IAM Role and Policies
# ============================================================================

# Purchaser Lambda IAM Role
resource "aws_iam_role" "purchaser" {
  name        = "${local.module_name}-purchaser"
  description = "IAM role for Purchaser Lambda function - executes Savings Plans purchases from queue"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-purchaser-role"
    }
  )
}

# Purchaser Lambda Policy - CloudWatch Logs
resource "aws_iam_role_policy" "purchaser_cloudwatch_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.purchaser.arn}:*"
    }]
  })
}

# Purchaser Lambda Policy - Cost Explorer
resource "aws_iam_role_policy" "purchaser_cost_explorer" {
  name = "cost-explorer"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansUtilization",
        "ce:GetSavingsPlansCoverage",
        "ce:GetCostAndUsage"
      ]
      Resource = "*"
    }]
  })
}

# Purchaser Lambda Policy - SQS
resource "aws_iam_role_policy" "purchaser_sqs" {
  name = "sqs"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ]
      Resource = aws_sqs_queue.purchase_intents.arn
    }]
  })
}

# Purchaser Lambda Policy - SNS
resource "aws_iam_role_policy" "purchaser_sns" {
  name = "sns"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sns:Publish"
      ]
      Resource = aws_sns_topic.notifications.arn
    }]
  })
}

# Purchaser Lambda Policy - Savings Plans
resource "aws_iam_role_policy" "purchaser_savingsplans" {
  name = "savingsplans"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:DescribeSavingsPlansOfferingRates",
        "savingsplans:DescribeSavingsPlansOfferings",
        "savingsplans:CreateSavingsPlan"
      ]
      Resource = "*"
    }]
  })
}

# Purchaser Lambda Policy - Assume Role (conditional)
resource "aws_iam_role_policy" "purchaser_assume_role" {
  count = var.management_account_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.purchaser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = var.management_account_role_arn
    }]
  })
}

# ============================================================================
# Reporter Lambda IAM Role and Policies
# ============================================================================

# Reporter Lambda IAM Role
resource "aws_iam_role" "reporter" {
  name        = "${local.module_name}-reporter"
  description = "IAM role for Reporter Lambda function - generates periodic coverage and savings reports"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-reporter-role"
    }
  )
}

# Reporter Lambda Policy - CloudWatch Logs
resource "aws_iam_role_policy" "reporter_cloudwatch_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.reporter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.reporter.arn}:*"
    }]
  })
}

# Reporter Lambda Policy - Cost Explorer
resource "aws_iam_role_policy" "reporter_cost_explorer" {
  name = "cost-explorer"
  role = aws_iam_role.reporter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansUtilization",
        "ce:GetSavingsPlansCoverage",
        "ce:GetCostAndUsage"
      ]
      Resource = "*"
    }]
  })
}

# Reporter Lambda Policy - S3
resource "aws_iam_role_policy" "reporter_s3" {
  name = "s3"
  role = aws_iam_role.reporter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject"
      ]
      Resource = "${aws_s3_bucket.reports.arn}/*"
    }]
  })
}

# Reporter Lambda Policy - SNS
resource "aws_iam_role_policy" "reporter_sns" {
  name = "sns"
  role = aws_iam_role.reporter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sns:Publish"
      ]
      Resource = aws_sns_topic.notifications.arn
    }]
  })
}

# Reporter Lambda Policy - Savings Plans
resource "aws_iam_role_policy" "reporter_savingsplans" {
  name = "savingsplans"
  role = aws_iam_role.reporter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:DescribeSavingsPlansOfferingRates",
        "savingsplans:DescribeSavingsPlansOfferings"
      ]
      Resource = "*"
    }]
  })
}

# Reporter Lambda Policy - Assume Role (conditional)
resource "aws_iam_role_policy" "reporter_assume_role" {
  count = var.management_account_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.reporter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = var.management_account_role_arn
    }]
  })
}
