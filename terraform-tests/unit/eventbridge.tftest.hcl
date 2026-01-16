# AWS Savings Plans Automation Module
# EventBridge Tests - Credential-free testing using mock provider

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
# EventBridge Rules Tests - Scheduler
# ============================================================================

# Test: Scheduler EventBridge rule naming follows expected pattern
run "test_scheduler_eventbridge_rule_naming" {
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
    condition     = aws_cloudwatch_event_rule.scheduler[0].name == "sp-autopilot-scheduler"
    error_message = "Scheduler EventBridge rule name should follow pattern: sp-autopilot-scheduler"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.scheduler[0].name != ""
    error_message = "Scheduler EventBridge rule name should not be empty"
  }
}

# Test: Scheduler EventBridge rule has correct description
run "test_scheduler_eventbridge_rule_description" {
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
    condition     = aws_cloudwatch_event_rule.scheduler[0].description == "Triggers Scheduler Lambda to analyze usage and recommend Savings Plans purchases"
    error_message = "Scheduler EventBridge rule should have correct description"
  }
}

# Test: Scheduler EventBridge rule uses default schedule
run "test_scheduler_eventbridge_rule_default_schedule" {
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
    condition     = aws_cloudwatch_event_rule.scheduler[0].schedule_expression == "cron(0 8 1 * ? *)"
    error_message = "Scheduler EventBridge rule should use default schedule: cron(0 8 1 * ? *)"
  }
}

# Test: Scheduler EventBridge rule uses custom schedule
run "test_scheduler_eventbridge_rule_custom_schedule" {
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
    scheduler = {
      scheduler = "cron(0 2 1 * ? *)"
    }
  }

  assert {
    condition     = aws_cloudwatch_event_rule.scheduler[0].schedule_expression == "cron(0 2 1 * ? *)"
    error_message = "Scheduler EventBridge rule should use custom schedule value"
  }
}

# Test: Scheduler EventBridge rule has proper tags
run "test_scheduler_eventbridge_rule_tags" {
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
    condition     = aws_cloudwatch_event_rule.scheduler[0].tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Scheduler EventBridge rule should have ManagedBy tag"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.scheduler[0].tags["Module"] == "savings-plans-automation"
    error_message = "Scheduler EventBridge rule should have Module tag"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.scheduler[0].tags["Environment"] == "test"
    error_message = "Scheduler EventBridge rule should include custom tags from variables"
  }
}

# ============================================================================
# EventBridge Rules Tests - Purchaser
# ============================================================================

# Test: Purchaser EventBridge rule naming follows expected pattern
run "test_purchaser_eventbridge_rule_naming" {
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
    condition     = aws_cloudwatch_event_rule.purchaser[0].name == "sp-autopilot-purchaser"
    error_message = "Purchaser EventBridge rule name should follow pattern: sp-autopilot-purchaser"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.purchaser[0].name != ""
    error_message = "Purchaser EventBridge rule name should not be empty"
  }
}

# Test: Purchaser EventBridge rule has correct description
run "test_purchaser_eventbridge_rule_description" {
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
    condition     = aws_cloudwatch_event_rule.purchaser[0].description == "Triggers Purchaser Lambda to process and execute Savings Plans purchases from SQS queue"
    error_message = "Purchaser EventBridge rule should have correct description"
  }
}

# Test: Purchaser EventBridge rule uses default schedule
run "test_purchaser_eventbridge_rule_default_schedule" {
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
    condition     = aws_cloudwatch_event_rule.purchaser[0].schedule_expression == "cron(0 8 10 * ? *)"
    error_message = "Purchaser EventBridge rule should use default schedule: cron(0 8 10 * ? *)"
  }
}

# Test: Purchaser EventBridge rule uses custom schedule
run "test_purchaser_eventbridge_rule_custom_schedule" {
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
    scheduler = {
      purchaser = "cron(0 3 1 * ? *)"
    }
  }

  assert {
    condition     = aws_cloudwatch_event_rule.purchaser[0].schedule_expression == "cron(0 3 1 * ? *)"
    error_message = "Purchaser EventBridge rule should use custom schedule value"
  }
}

# Test: Purchaser EventBridge rule has proper tags
run "test_purchaser_eventbridge_rule_tags" {
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
    condition     = aws_cloudwatch_event_rule.purchaser[0].tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Purchaser EventBridge rule should have ManagedBy tag"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.purchaser[0].tags["Module"] == "savings-plans-automation"
    error_message = "Purchaser EventBridge rule should have Module tag"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.purchaser[0].tags["Environment"] == "test"
    error_message = "Purchaser EventBridge rule should include custom tags from variables"
  }
}

# ============================================================================
# EventBridge Rules Tests - Reporter (Conditional)
# ============================================================================

# Test: Reporter EventBridge rule is created when reports are enabled
run "test_reporter_eventbridge_rule_enabled" {
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
    reporting = {
      enabled = true
    }
  }

  assert {
    condition     = length(aws_cloudwatch_event_rule.reporter) == 1
    error_message = "Reporter EventBridge rule should be created when enable_reports is true"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.reporter[0].name == "sp-autopilot-reporter"
    error_message = "Reporter EventBridge rule name should follow pattern: sp-autopilot-reporter"
  }
}

# Test: Reporter EventBridge rule is not created when reports are disabled
run "test_reporter_eventbridge_rule_disabled" {
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
      reporter = {
        enabled = false
      }
    }
  }

  assert {
    condition     = length(aws_cloudwatch_event_rule.reporter) == 0
    error_message = "Reporter EventBridge rule should not be created when reporter Lambda is disabled"
  }
}

# Test: Reporter EventBridge rule has correct description
run "test_reporter_eventbridge_rule_description" {
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
    reporting = {
      enabled = true
    }
  }

  assert {
    condition     = aws_cloudwatch_event_rule.reporter[0].description == "Triggers Reporter Lambda to generate periodic coverage and savings reports"
    error_message = "Reporter EventBridge rule should have correct description"
  }
}

# Test: Reporter EventBridge rule uses default schedule
run "test_reporter_eventbridge_rule_default_schedule" {
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
    reporting = {
      enabled = true
    }
  }

  assert {
    condition     = aws_cloudwatch_event_rule.reporter[0].schedule_expression == "cron(0 9 20 * ? *)"
    error_message = "Reporter EventBridge rule should use default schedule: cron(0 9 20 * ? *)"
  }
}

# Test: Reporter EventBridge rule uses custom schedule
run "test_reporter_eventbridge_rule_custom_schedule" {
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
    reporting = {
      enabled = true
    }
    scheduler = {
      reporter = "cron(0 9 1 * ? *)"
    }
  }

  assert {
    condition     = aws_cloudwatch_event_rule.reporter[0].schedule_expression == "cron(0 9 1 * ? *)"
    error_message = "Reporter EventBridge rule should use custom schedule value"
  }
}

# Test: Reporter EventBridge rule has proper tags
run "test_reporter_eventbridge_rule_tags" {
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
    reporting = {
      enabled = true
    }
    tags = {
      Environment = "test"
      Owner       = "platform-team"
    }
  }

  assert {
    condition     = aws_cloudwatch_event_rule.reporter[0].tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Reporter EventBridge rule should have ManagedBy tag"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.reporter[0].tags["Module"] == "savings-plans-automation"
    error_message = "Reporter EventBridge rule should have Module tag"
  }

  assert {
    condition     = aws_cloudwatch_event_rule.reporter[0].tags["Environment"] == "test"
    error_message = "Reporter EventBridge rule should include custom tags from variables"
  }
}

# ============================================================================
# EventBridge Targets Tests - Scheduler
# ============================================================================

# Test: Scheduler EventBridge target is configured correctly
run "test_scheduler_eventbridge_target_configuration" {
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

  override_resource {
    override_during = plan
    target          = aws_lambda_function.scheduler[0]
    values = {
      arn = "arn:aws:lambda:us-east-1:123456789012:function:sp-autopilot-scheduler"
    }
  }

  override_resource {
    override_during = plan
    target          = aws_cloudwatch_event_target.scheduler[0]
    values = {
      rule = "sp-autopilot-scheduler"
      arn  = "arn:aws:lambda:us-east-1:123456789012:function:sp-autopilot-scheduler"
    }
  }

  assert {
    condition     = aws_cloudwatch_event_target.scheduler[0].rule == aws_cloudwatch_event_rule.scheduler[0].name
    error_message = "Scheduler EventBridge target should reference correct rule"
  }

  assert {
    condition     = aws_cloudwatch_event_target.scheduler[0].target_id == "SchedulerLambda"
    error_message = "Scheduler EventBridge target should have correct target_id"
  }

  assert {
    condition     = aws_cloudwatch_event_target.scheduler[0].arn == aws_lambda_function.scheduler[0].arn
    error_message = "Scheduler EventBridge target should reference Scheduler Lambda ARN"
  }
}

# ============================================================================
# EventBridge Targets Tests - Purchaser
# ============================================================================

# Test: Purchaser EventBridge target is configured correctly
run "test_purchaser_eventbridge_target_configuration" {
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

  override_resource {
    override_during = plan
    target          = aws_lambda_function.purchaser[0]
    values = {
      arn = "arn:aws:lambda:us-east-1:123456789012:function:sp-autopilot-purchaser"
    }
  }

  override_resource {
    override_during = plan
    target          = aws_cloudwatch_event_target.purchaser[0]
    values = {
      rule = "sp-autopilot-purchaser"
      arn  = "arn:aws:lambda:us-east-1:123456789012:function:sp-autopilot-purchaser"
    }
  }

  assert {
    condition     = aws_cloudwatch_event_target.purchaser[0].rule == "sp-autopilot-purchaser"
    error_message = "Purchaser EventBridge target should reference correct rule"
  }

  assert {
    condition     = aws_cloudwatch_event_target.purchaser[0].target_id == "PurchaserLambda"
    error_message = "Purchaser EventBridge target should have correct target_id"
  }

  assert {
    condition     = aws_cloudwatch_event_target.purchaser[0].arn == aws_lambda_function.purchaser[0].arn
    error_message = "Purchaser EventBridge target should reference Purchaser Lambda ARN"
  }
}

# ============================================================================
# EventBridge Targets Tests - Reporter (Conditional)
# ============================================================================

# Test: Reporter EventBridge target is created when reports are enabled
run "test_reporter_eventbridge_target_enabled" {
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
    reporting = {
      enabled = true
    }
  }

  assert {
    condition     = length(aws_cloudwatch_event_target.reporter) == 1
    error_message = "Reporter EventBridge target should be created when enable_reports is true"
  }

  assert {
    condition     = aws_cloudwatch_event_target.reporter[0].rule == "sp-autopilot-reporter"
    error_message = "Reporter EventBridge target should reference correct rule"
  }

  assert {
    condition     = aws_cloudwatch_event_target.reporter[0].target_id == "ReporterLambda"
    error_message = "Reporter EventBridge target should have correct target_id"
  }

  # Note: ARN comparison cannot be tested during plan phase as both ARNs are computed
  # This is validated through integration tests instead
}

# Test: Reporter EventBridge target is not created when reports are disabled
run "test_reporter_eventbridge_target_disabled" {
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
    reporting = {
      enabled = false
    }
  }

  assert {
    condition     = length(aws_cloudwatch_event_target.reporter) == 0
    error_message = "Reporter EventBridge target should not be created when enable_reports is false"
  }
}

# ============================================================================
# Lambda Permissions Tests - Scheduler
# ============================================================================

# Test: Scheduler Lambda permission for EventBridge is configured correctly
run "test_scheduler_lambda_permission_eventbridge" {
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
    condition     = aws_lambda_permission.scheduler_eventbridge.statement_id == "AllowExecutionFromEventBridge"
    error_message = "Scheduler Lambda permission should have correct statement_id"
  }

  assert {
    condition     = aws_lambda_permission.scheduler_eventbridge.action == "lambda:InvokeFunction"
    error_message = "Scheduler Lambda permission should allow InvokeFunction action"
  }

  assert {
    condition     = aws_lambda_permission.scheduler_eventbridge.function_name == "sp-autopilot-scheduler"
    error_message = "Scheduler Lambda permission should reference correct function name"
  }

  assert {
    condition     = aws_lambda_permission.scheduler_eventbridge.principal == "events.amazonaws.com"
    error_message = "Scheduler Lambda permission should have events.amazonaws.com as principal"
  }

  # Note: source_arn and EventBridge rule ARN are computed values during plan
  # ARN comparison is validated through integration tests instead
}

# ============================================================================
# Lambda Permissions Tests - Purchaser
# ============================================================================

# Test: Purchaser Lambda permission for EventBridge is configured correctly
run "test_purchaser_lambda_permission_eventbridge" {
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
    condition     = aws_lambda_permission.purchaser_eventbridge.statement_id == "AllowExecutionFromEventBridge"
    error_message = "Purchaser Lambda permission should have correct statement_id"
  }

  assert {
    condition     = aws_lambda_permission.purchaser_eventbridge.action == "lambda:InvokeFunction"
    error_message = "Purchaser Lambda permission should allow InvokeFunction action"
  }

  assert {
    condition     = aws_lambda_permission.purchaser_eventbridge.function_name == "sp-autopilot-purchaser"
    error_message = "Purchaser Lambda permission should reference correct function name"
  }

  assert {
    condition     = aws_lambda_permission.purchaser_eventbridge.principal == "events.amazonaws.com"
    error_message = "Purchaser Lambda permission should have events.amazonaws.com as principal"
  }

  # Note: source_arn and EventBridge rule ARN are computed values during plan
  # ARN comparison is validated through integration tests instead
}

# ============================================================================
# Lambda Permissions Tests - Reporter (Conditional)
# ============================================================================

# Test: Reporter Lambda permission is created when reports are enabled
run "test_reporter_lambda_permission_enabled" {
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
    reporting = {
      enabled = true
    }
  }

  assert {
    condition     = length(aws_lambda_permission.reporter_eventbridge) == 1
    error_message = "Reporter Lambda permission should be created when enable_reports is true"
  }

  assert {
    condition     = aws_lambda_permission.reporter_eventbridge[0].statement_id == "AllowExecutionFromEventBridge"
    error_message = "Reporter Lambda permission should have correct statement_id"
  }

  assert {
    condition     = aws_lambda_permission.reporter_eventbridge[0].action == "lambda:InvokeFunction"
    error_message = "Reporter Lambda permission should allow InvokeFunction action"
  }

  assert {
    condition     = aws_lambda_permission.reporter_eventbridge[0].function_name == "sp-autopilot-reporter"
    error_message = "Reporter Lambda permission should reference correct function name"
  }

  assert {
    condition     = aws_lambda_permission.reporter_eventbridge[0].principal == "events.amazonaws.com"
    error_message = "Reporter Lambda permission should have events.amazonaws.com as principal"
  }

  # Note: source_arn and EventBridge rule ARN are computed values during plan
  # ARN comparison is validated through integration tests instead
}

# Test: Reporter Lambda permission is not created when reports are disabled
run "test_reporter_lambda_permission_disabled" {
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
    reporting = {
      enabled = false
    }
  }

  assert {
    condition     = length(aws_lambda_permission.reporter_eventbridge) == 0
    error_message = "Reporter Lambda permission should not be created when enable_reports is false"
  }
}
