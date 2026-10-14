# SNS topic for notifications

resource "aws_sns_topic" "notifications" {
  name              = "${local.module_name}-notifications"
  display_name      = "AWS Savings Plans Automation Notifications"
  kms_master_key_id = local.sns_kms_key # The module's key (kms.tf), or encryption.sns_kms_key

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-notifications"
    }
  )
}


resource "aws_sns_topic_subscription" "email_notifications" {
  for_each = toset(local.notification_emails)

  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = each.value
}
