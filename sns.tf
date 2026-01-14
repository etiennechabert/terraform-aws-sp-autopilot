# ============================================================================
# SNS Topic
# ============================================================================

resource "aws_sns_topic" "notifications" {
  name         = "${local.module_name}-notifications"
  display_name = "AWS Savings Plans Automation Notifications"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-notifications"
    }
  )
}

# ============================================================================
# SNS Email Subscriptions
# ============================================================================

resource "aws_sns_topic_subscription" "email_notifications" {
  for_each = toset(var.notification_emails)

  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = each.value
}
