# AWS Savings Plans Automation Module
# CloudWatch Tests - Credential-free testing using mock provider

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
# CloudWatch Log Groups Tests
# ============================================================================

# Test: Scheduler log group naming follows expected pattern
run "test_scheduler_log_group_naming" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  assert {
    condition     = aws_cloudwatch_log_group.scheduler[0].name == "/aws/lambda/sp-autopilot-scheduler"
    error_message = "Scheduler log group name should follow pattern: /aws/lambda/sp-autopilot-scheduler"
  }

  assert {
    condition     = aws_cloudwatch_log_group.scheduler[0].name != ""
    error_message = "Scheduler log group name should not be empty"
  }
}

# Test: Purchaser log group naming follows expected pattern
run "test_purchaser_log_group_naming" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  assert {
    condition     = aws_cloudwatch_log_group.purchaser[0].name == "/aws/lambda/sp-autopilot-purchaser"
    error_message = "Purchaser log group name should follow pattern: /aws/lambda/sp-autopilot-purchaser"
  }

  assert {
    condition     = aws_cloudwatch_log_group.purchaser[0].name != ""
    error_message = "Purchaser log group name should not be empty"
  }
}

# Test: Reporter log group naming follows expected pattern
run "test_reporter_log_group_naming" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  assert {
    condition     = aws_cloudwatch_log_group.reporter[0].name == "/aws/lambda/sp-autopilot-reporter"
    error_message = "Reporter log group name should follow pattern: /aws/lambda/sp-autopilot-reporter"
  }

  assert {
    condition     = aws_cloudwatch_log_group.reporter[0].name != ""
    error_message = "Reporter log group name should not be empty"
  }
}

# Test: Log groups have correct retention period
run "test_log_groups_retention" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  assert {
    condition     = aws_cloudwatch_log_group.scheduler[0].retention_in_days == 30
    error_message = "Scheduler log group should have 30 days retention"
  }

  assert {
    condition     = aws_cloudwatch_log_group.purchaser[0].retention_in_days == 30
    error_message = "Purchaser log group should have 30 days retention"
  }

  assert {
    condition     = aws_cloudwatch_log_group.reporter[0].retention_in_days == 30
    error_message = "Reporter log group should have 30 days retention"
  }
}

# Test: Log groups have proper tags
run "test_log_groups_tags" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    tags = {
      Environment = "test"
      Owner       = "platform-team"
    }
  }

  assert {
    condition     = aws_cloudwatch_log_group.scheduler[0].tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Scheduler log group should have ManagedBy tag"
  }

  assert {
    condition     = aws_cloudwatch_log_group.scheduler[0].tags["Module"] == "savings-plans-automation"
    error_message = "Scheduler log group should have Module tag"
  }

  assert {
    condition     = aws_cloudwatch_log_group.scheduler[0].tags["Name"] == "sp-autopilot-scheduler-logs"
    error_message = "Scheduler log group should have correct Name tag"
  }

  assert {
    condition     = aws_cloudwatch_log_group.purchaser[0].tags["Name"] == "sp-autopilot-purchaser-logs"
    error_message = "Purchaser log group should have correct Name tag"
  }

  assert {
    condition     = aws_cloudwatch_log_group.reporter[0].tags["Name"] == "sp-autopilot-reporter-logs"
    error_message = "Reporter log group should have correct Name tag"
  }

  assert {
    condition     = aws_cloudwatch_log_group.scheduler[0].tags["Environment"] == "test"
    error_message = "Log groups should include custom tags from variables"
  }
}

# ============================================================================
# CloudWatch Metric Alarms Tests - Enabled
# ============================================================================

# Test: Lambda error alarms are created when enabled
run "test_lambda_error_alarms_enabled" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.scheduler_error_alarm) == 1
    error_message = "Scheduler error alarm should be created when enable_lambda_error_alarm is true"
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.purchaser_error_alarm) == 1
    error_message = "Purchaser error alarm should be created when enable_lambda_error_alarm is true"
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.reporter_error_alarm) == 1
    error_message = "Reporter error alarm should be created when enable_lambda_error_alarm is true"
  }
}

# Test: Lambda error alarms are not created when disabled
run "test_lambda_error_alarms_disabled" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = false }
      purchaser = { error_alarm = false }
      reporter  = { error_alarm = false }
    }
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.scheduler_error_alarm) == 0
    error_message = "Scheduler error alarm should not be created when enable_lambda_error_alarm is false"
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.purchaser_error_alarm) == 0
    error_message = "Purchaser error alarm should not be created when enable_lambda_error_alarm is false"
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.reporter_error_alarm) == 0
    error_message = "Reporter error alarm should not be created when enable_lambda_error_alarm is false"
  }
}

# Test: Scheduler error alarm naming follows expected pattern
run "test_scheduler_error_alarm_naming" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].alarm_name == "sp-autopilot-scheduler-errors"
    error_message = "Scheduler error alarm name should follow pattern: sp-autopilot-scheduler-errors"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].alarm_description == "Triggers when Scheduler Lambda function errors exceed threshold, indicating failures in usage analysis"
    error_message = "Scheduler error alarm should have correct description"
  }
}

# Test: Purchaser error alarm naming follows expected pattern
run "test_purchaser_error_alarm_naming" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.purchaser_error_alarm[0].alarm_name == "sp-autopilot-purchaser-errors"
    error_message = "Purchaser error alarm name should follow pattern: sp-autopilot-purchaser-errors"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.purchaser_error_alarm[0].alarm_description == "Triggers when Purchaser Lambda function errors exceed threshold, indicating failures in Savings Plans purchases"
    error_message = "Purchaser error alarm should have correct description"
  }
}

# Test: Reporter error alarm naming follows expected pattern
run "test_reporter_error_alarm_naming" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.reporter_error_alarm[0].alarm_name == "sp-autopilot-reporter-errors"
    error_message = "Reporter error alarm name should follow pattern: sp-autopilot-reporter-errors"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.reporter_error_alarm[0].alarm_description == "Triggers when Reporter Lambda function errors exceed threshold, indicating failures in report generation"
    error_message = "Reporter error alarm should have correct description"
  }
}

# Test: Error alarms have correct metric configuration
run "test_error_alarms_metric_configuration" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].metric_name == "Errors"
    error_message = "Error alarm should monitor 'Errors' metric"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].namespace == "AWS/Lambda"
    error_message = "Error alarm should use AWS/Lambda namespace"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].statistic == "Sum"
    error_message = "Error alarm should use Sum statistic"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].period == 60
    error_message = "Error alarm should have 60 second period"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].evaluation_periods == 1
    error_message = "Error alarm should evaluate 1 period"
  }
}

# Test: Error alarms have correct comparison operator and threshold
run "test_error_alarms_threshold_configuration" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
    monitoring = {
      error_threshold = 1
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].comparison_operator == "GreaterThanOrEqualToThreshold"
    error_message = "Error alarm should use GreaterThanOrEqualToThreshold comparison"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].threshold == 1
    error_message = "Error alarm should use default threshold of 1"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].treat_missing_data == "notBreaching"
    error_message = "Error alarm should treat missing data as notBreaching"
  }
}

# Test: Error alarms use custom threshold
run "test_error_alarms_custom_threshold" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
    monitoring = {
      error_threshold = 5
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].threshold == 5
    error_message = "Error alarm should use custom threshold value"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.purchaser_error_alarm[0].threshold == 5
    error_message = "All error alarms should use the same custom threshold"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.reporter_error_alarm[0].threshold == 5
    error_message = "All error alarms should use the same custom threshold"
  }
}

# Test: Error alarms have correct dimensions for each Lambda
run "test_error_alarms_dimensions" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].dimensions["FunctionName"] == "sp-autopilot-scheduler"
    error_message = "Scheduler error alarm should monitor correct Lambda function"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.purchaser_error_alarm[0].dimensions["FunctionName"] == "sp-autopilot-purchaser"
    error_message = "Purchaser error alarm should monitor correct Lambda function"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.reporter_error_alarm[0].dimensions["FunctionName"] == "sp-autopilot-reporter"
    error_message = "Reporter error alarm should monitor correct Lambda function"
  }
}

# Test: Error alarms send to SNS topic
run "test_error_alarms_alarm_actions" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].alarm_actions) == 1
    error_message = "Error alarm should have exactly one alarm action"
  }

  # Note: Cannot verify exact SNS topic ARN with mock provider due to cross-resource reference limitations
  assert {
    condition     = length(aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].alarm_actions) > 0
    error_message = "Error alarm should have at least one alarm action configured"
  }
}

# Test: Error alarms have proper tags
run "test_error_alarms_tags" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 5
      }
    }
    sp_plans = {
      compute = {
        enabled              = true
        all_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
    lambda_config = {
      scheduler = { error_alarm = true }
      purchaser = { error_alarm = true }
      reporter  = { error_alarm = true }
    }
    tags = {
      Environment = "test"
      Owner       = "platform-team"
    }
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Error alarm should have ManagedBy tag"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].tags["Module"] == "savings-plans-automation"
    error_message = "Error alarm should have Module tag"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].tags["Name"] == "sp-autopilot-scheduler-errors"
    error_message = "Scheduler error alarm should have correct Name tag"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.purchaser_error_alarm[0].tags["Name"] == "sp-autopilot-purchaser-errors"
    error_message = "Purchaser error alarm should have correct Name tag"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.reporter_error_alarm[0].tags["Name"] == "sp-autopilot-reporter-errors"
    error_message = "Reporter error alarm should have correct Name tag"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.scheduler_error_alarm[0].tags["Environment"] == "test"
    error_message = "Error alarms should include custom tags from variables"
  }
}
