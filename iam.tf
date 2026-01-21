# IAM roles and policies for Lambda functions


resource "aws_iam_role" "scheduler" {
  count = local.lambda_scheduler_enabled ? 1 : 0

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

resource "aws_iam_role_policy" "scheduler_cloudwatch_logs" {
  count = local.lambda_scheduler_enabled ? 1 : 0

  name = "cloudwatch-logs"
  role = aws_iam_role.scheduler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.scheduler[0].arn}:*"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_cost_explorer" {
  count = local.lambda_scheduler_enabled ? 1 : 0

  name = "cost-explorer"
  role = aws_iam_role.scheduler[0].id

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

resource "aws_iam_role_policy" "scheduler_sqs" {
  count = local.lambda_scheduler_enabled ? 1 : 0

  name = "sqs"
  role = aws_iam_role.scheduler[0].id

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

resource "aws_iam_role_policy" "scheduler_sns" {
  count = local.lambda_scheduler_enabled ? 1 : 0

  name = "sns"
  role = aws_iam_role.scheduler[0].id

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

resource "aws_iam_role_policy" "scheduler_savingsplans" {
  count = local.lambda_scheduler_enabled ? 1 : 0

  name = "savingsplans"
  role = aws_iam_role.scheduler[0].id

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

resource "aws_iam_role_policy" "scheduler_assume_role" {
  count = local.lambda_scheduler_enabled && local.lambda_scheduler_assume_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.scheduler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = local.lambda_scheduler_assume_role_arn
    }]
  })
}


resource "aws_iam_role" "purchaser" {
  count = local.lambda_purchaser_enabled ? 1 : 0

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

resource "aws_iam_role_policy" "purchaser_cloudwatch_logs" {
  count = local.lambda_purchaser_enabled ? 1 : 0

  name = "cloudwatch-logs"
  role = aws_iam_role.purchaser[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.purchaser[0].arn}:*"
    }]
  })
}

resource "aws_iam_role_policy" "purchaser_cost_explorer" {
  count = local.lambda_purchaser_enabled ? 1 : 0

  name = "cost-explorer"
  role = aws_iam_role.purchaser[0].id

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

resource "aws_iam_role_policy" "purchaser_sqs" {
  count = local.lambda_purchaser_enabled ? 1 : 0

  name = "sqs"
  role = aws_iam_role.purchaser[0].id

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

resource "aws_iam_role_policy" "purchaser_sns" {
  count = local.lambda_purchaser_enabled ? 1 : 0

  name = "sns"
  role = aws_iam_role.purchaser[0].id

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

resource "aws_iam_role_policy" "purchaser_savingsplans" {
  count = local.lambda_purchaser_enabled ? 1 : 0

  name = "savingsplans"
  role = aws_iam_role.purchaser[0].id

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

resource "aws_iam_role_policy" "purchaser_assume_role" {
  count = local.lambda_purchaser_enabled && local.lambda_purchaser_assume_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.purchaser[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = local.lambda_purchaser_assume_role_arn
    }]
  })
}


resource "aws_iam_role" "reporter" {
  count = local.lambda_reporter_enabled ? 1 : 0

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

resource "aws_iam_role_policy" "reporter_cloudwatch_logs" {
  count = local.lambda_reporter_enabled ? 1 : 0

  name = "cloudwatch-logs"
  role = aws_iam_role.reporter[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "${aws_cloudwatch_log_group.reporter[0].arn}:*"
    }]
  })
}

resource "aws_iam_role_policy" "reporter_cost_explorer" {
  count = local.lambda_reporter_enabled ? 1 : 0

  name = "cost-explorer"
  role = aws_iam_role.reporter[0].id

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

resource "aws_iam_role_policy" "reporter_s3" {
  count = local.lambda_reporter_enabled ? 1 : 0

  name = "s3"
  role = aws_iam_role.reporter[0].id

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

resource "aws_iam_role_policy" "reporter_sns" {
  count = local.lambda_reporter_enabled ? 1 : 0

  name = "sns"
  role = aws_iam_role.reporter[0].id

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

resource "aws_iam_role_policy" "reporter_savingsplans" {
  count = local.lambda_reporter_enabled ? 1 : 0

  name = "savingsplans"
  role = aws_iam_role.reporter[0].id

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

resource "aws_iam_role_policy" "reporter_assume_role" {
  count = local.lambda_reporter_enabled && local.lambda_reporter_assume_role_arn != null ? 1 : 0

  name = "assume-role"
  role = aws_iam_role.reporter[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sts:AssumeRole"
      Resource = local.lambda_reporter_assume_role_arn
    }]
  })
}
