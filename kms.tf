# KMS key for the notifications topic, unless encryption.sns_kms_key names one
#
# The CloudWatch alarms (cloudwatch.tf, sqs.tf) publish to the topic. An AWS managed
# key such as alias/aws/sns can't let them: its key policy can't be changed, so their
# notifications fail with "CloudWatch Alarms does not have authorization to access
# the SNS topic encryption key". This key's policy lets CloudWatch use it; the Lambda
# roles get their access through IAM (iam.tf).

resource "aws_kms_key" "notifications" {
  count = local.create_sns_kms_key ? 1 : 0

  description             = "Encrypts the ${local.module_name}-notifications SNS topic"
  enable_key_rotation     = true
  deletion_window_in_days = 7

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountAdministration"
        Effect    = "Allow"
        Principal = { AWS = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "CloudWatchAlarms"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource  = "*"
        Condition = {
          StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        }
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-notifications"
    }
  )
}

resource "aws_kms_alias" "notifications" {
  count = local.create_sns_kms_key ? 1 : 0

  name          = "alias/${local.module_name}-notifications"
  target_key_id = aws_kms_key.notifications[0].key_id
}
