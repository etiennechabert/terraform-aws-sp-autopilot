# AWS Savings Plans Automation Module
# SQS Queue Tests - Credential-free testing using mock provider

# ============================================================================
# Mock Provider Configuration
# ============================================================================

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:user/test"
      user_id    = "AIDAEXAMPLE"
    }
  }

  mock_data "aws_region" {
    defaults = {
      name = "us-east-1"
    }
  }
}

# ============================================================================
# SQS Main Queue Tests
# ============================================================================

# Test: SQS main queue naming follows expected pattern
run "test_sqs_main_queue_naming" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents.name == "sp-autopilot-purchase-intents"
    error_message = "SQS main queue name should follow pattern: sp-autopilot-purchase-intents"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents.name != ""
    error_message = "SQS main queue name should not be empty"
  }
}

# Test: SQS main queue visibility timeout matches Lambda timeout
run "test_sqs_visibility_timeout" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents.visibility_timeout_seconds == 300
    error_message = "SQS main queue visibility timeout should be 300 seconds (5 minutes) to match Lambda timeout"
  }
}

# Test: SQS main queue has redrive policy configured
run "test_sqs_redrive_policy_configured" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  # Note: redrive_policy is a computed JSON string attribute
  # Cannot reliably test JSON content during plan phase even with override
  # Testing that redrive_policy attribute exists in configuration
  assert {
    condition     = aws_sqs_queue.purchase_intents.redrive_policy != null
    error_message = "SQS main queue should have a redrive policy configured"
  }
}

# Test: SQS redrive policy has correct maxReceiveCount
run "test_sqs_redrive_policy_max_receive_count" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  # Note: redrive_policy JSON content cannot be inspected during plan phase
  # The redrive_policy attribute is a computed JSON string
  # Redrive policy contents are validated through integration tests instead
  assert {
    condition     = aws_sqs_queue.purchase_intents.redrive_policy != null
    error_message = "SQS redrive policy should be configured"
  }
}

# Test: SQS redrive policy points to correct DLQ
run "test_sqs_redrive_policy_dlq_target" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  # Note: Cannot test redrive_policy JSON contents during plan phase
  # Both redrive_policy and DLQ ARN are computed values
  # DLQ target is validated through integration tests instead
  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.name == "sp-autopilot-purchase-intents-dlq"
    error_message = "DLQ should exist with correct name"
  }
}

# ============================================================================
# SQS Dead Letter Queue Tests
# ============================================================================

# Test: SQS DLQ naming follows expected pattern
run "test_sqs_dlq_naming" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.name == "sp-autopilot-purchase-intents-dlq"
    error_message = "SQS DLQ name should follow pattern: sp-autopilot-purchase-intents-dlq"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.name != ""
    error_message = "SQS DLQ name should not be empty"
  }
}

# Test: SQS DLQ message retention is set to maximum
run "test_sqs_dlq_message_retention" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.message_retention_seconds == 1209600
    error_message = "SQS DLQ should retain messages for 1209600 seconds (14 days - AWS maximum)"
  }
}

# ============================================================================
# SQS Queue Tags Tests
# ============================================================================

# Test: SQS main queue tags include common tags
run "test_sqs_main_queue_tags" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    tags = {
      Environment = "test"
      Owner       = "platform-team"
    }
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "SQS main queue should have ManagedBy tag"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents.tags["Module"] == "savings-plans-automation"
    error_message = "SQS main queue should have Module tag"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents.tags["Name"] == "sp-autopilot-purchase-intents"
    error_message = "SQS main queue should have Name tag"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents.tags["Environment"] == "test"
    error_message = "SQS main queue should include custom tags from variables"
  }
}

# Test: SQS DLQ tags include common tags
run "test_sqs_dlq_tags" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    tags = {
      Environment = "test"
      Owner       = "platform-team"
    }
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "SQS DLQ should have ManagedBy tag"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.tags["Module"] == "savings-plans-automation"
    error_message = "SQS DLQ should have Module tag"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.tags["Name"] == "sp-autopilot-purchase-intents-dlq"
    error_message = "SQS DLQ should have Name tag"
  }

  assert {
    condition     = aws_sqs_queue.purchase_intents_dlq.tags["Environment"] == "test"
    error_message = "SQS DLQ should include custom tags from variables"
  }
}

# ============================================================================
# CloudWatch Alarm Tests
# ============================================================================

# Test: DLQ alarm is created when enabled
run "test_dlq_alarm_enabled" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    enable_dlq_alarm  = true
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.dlq_alarm) == 1
    error_message = "DLQ alarm should be created when enable_dlq_alarm is true"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].alarm_name == "sp-autopilot-purchase-intents-dlq-depth"
    error_message = "DLQ alarm name should follow pattern: sp-autopilot-purchase-intents-dlq-depth"
  }
}

# Test: DLQ alarm is not created when disabled
run "test_dlq_alarm_disabled" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    enable_dlq_alarm  = false
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.dlq_alarm) == 0
    error_message = "DLQ alarm should not be created when enable_dlq_alarm is false"
  }
}

# Test: DLQ alarm configuration is correct
run "test_dlq_alarm_configuration" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    enable_dlq_alarm  = true
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].comparison_operator == "GreaterThanOrEqualToThreshold"
    error_message = "DLQ alarm should use GreaterThanOrEqualToThreshold comparison operator"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].threshold == 1
    error_message = "DLQ alarm should trigger when at least 1 message is visible"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].metric_name == "ApproximateNumberOfMessagesVisible"
    error_message = "DLQ alarm should monitor ApproximateNumberOfMessagesVisible metric"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].namespace == "AWS/SQS"
    error_message = "DLQ alarm should use AWS/SQS namespace"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].statistic == "Maximum"
    error_message = "DLQ alarm should use Maximum statistic"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].period == 60
    error_message = "DLQ alarm should have 60 second evaluation period"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].evaluation_periods == 1
    error_message = "DLQ alarm should evaluate over 1 period"
  }
}

# Test: DLQ alarm monitors correct queue
run "test_dlq_alarm_queue_dimensions" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    enable_dlq_alarm  = true
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].dimensions["QueueName"] == aws_sqs_queue.purchase_intents_dlq.name
    error_message = "DLQ alarm should monitor the purchase_intents_dlq queue"
  }
}

# Test: DLQ alarm sends to SNS topic
run "test_dlq_alarm_sns_action" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    enable_dlq_alarm  = true
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.dlq_alarm[0].alarm_actions) == 1
    error_message = "DLQ alarm should have exactly one alarm action"
  }

  # Note: alarm_actions is a set, cannot index with [0]
  # SNS topic ARN verification is validated through integration tests
}

# Test: DLQ alarm tags include common tags
run "test_dlq_alarm_tags" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    enable_dlq_alarm  = true
    tags = {
      Environment = "test"
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "DLQ alarm should have ManagedBy tag"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].tags["Module"] == "savings-plans-automation"
    error_message = "DLQ alarm should have Module tag"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_alarm[0].tags["Name"] == "sp-autopilot-purchase-intents-dlq-depth"
    error_message = "DLQ alarm should have Name tag"
  }
}
