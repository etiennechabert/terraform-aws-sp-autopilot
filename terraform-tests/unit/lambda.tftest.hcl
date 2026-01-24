# AWS Savings Plans Automation Module
# Lambda Function Tests - Credential-free testing using mock provider

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
# Interactive Handler Lambda Function Tests
# ============================================================================

# Test: Interactive Handler Lambda function naming follows expected pattern
run "test_interactive_handler_lambda_naming" {
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
    condition     = aws_lambda_function.interactive_handler[0].function_name == "sp-autopilot-interactive-handler"
    error_message = "Interactive Handler Lambda function name should follow pattern: sp-autopilot-interactive-handler"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].description == "Handles Slack interactive button actions for purchase approvals"
    error_message = "Interactive Handler Lambda should have correct description"
  }
}

# Test: Interactive Handler Lambda runtime configuration
run "test_interactive_handler_lambda_runtime" {
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
    condition     = aws_lambda_function.interactive_handler[0].runtime == "python3.14"
    error_message = "Interactive Handler Lambda should use python3.14 runtime"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].handler == "handler.handler"
    error_message = "Interactive Handler Lambda should use handler.handler as entry point"
  }
}

# Test: Interactive Handler Lambda performance configuration defaults
run "test_interactive_handler_lambda_performance_defaults" {
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
    condition     = aws_lambda_function.interactive_handler[0].memory_size == 128
    error_message = "Interactive Handler Lambda should default to 128 MB memory"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].timeout == 30
    error_message = "Interactive Handler Lambda should default to 30 second timeout for Slack response requirement"
  }
}

# Test: Interactive Handler Lambda performance configuration custom
run "test_interactive_handler_lambda_performance_custom" {
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
      interactive_handler = {
        memory_mb = 256
        timeout   = 20
      }
    }
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].memory_size == 256
    error_message = "Interactive Handler Lambda should use custom memory size"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].timeout == 20
    error_message = "Interactive Handler Lambda should use custom timeout"
  }
}

# Test: Interactive Handler Lambda environment variables
run "test_interactive_handler_lambda_environment" {
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
      emails                = ["test@example.com"]
      slack_signing_secret  = "test-secret-value"
    }
  }

  override_resource {
    override_during = plan
    target          = aws_sqs_queue.purchase_intents
    values = {
      url = "https://sqs.us-east-1.amazonaws.com/123456789012/sp-autopilot-purchase-intents"
    }
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].environment[0].variables["QUEUE_URL"] == "https://sqs.us-east-1.amazonaws.com/123456789012/sp-autopilot-purchase-intents"
    error_message = "Interactive Handler Lambda should have QUEUE_URL environment variable"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].environment[0].variables["SLACK_SIGNING_SECRET"] == "test-secret-value"
    error_message = "Interactive Handler Lambda should have SLACK_SIGNING_SECRET environment variable"
  }
}

# Test: Interactive Handler Lambda IAM role reference
run "test_interactive_handler_lambda_iam_role" {
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
    target          = aws_iam_role.interactive_handler[0]
    values = {
      arn = "arn:aws:iam::123456789012:role/sp-autopilot-interactive-handler"
    }
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].role == "arn:aws:iam::123456789012:role/sp-autopilot-interactive-handler"
    error_message = "Interactive Handler Lambda should reference correct IAM role ARN"
  }
}

# Test: Interactive Handler Lambda tags
run "test_interactive_handler_lambda_tags" {
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
      Environment = "staging"
      Team        = "finops"
    }
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Interactive Handler Lambda should have ManagedBy tag"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].tags["Module"] == "savings-plans-automation"
    error_message = "Interactive Handler Lambda should have Module tag"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].tags["Environment"] == "staging"
    error_message = "Interactive Handler Lambda should include custom tags from variables"
  }

  assert {
    condition     = aws_lambda_function.interactive_handler[0].tags["Team"] == "finops"
    error_message = "Interactive Handler Lambda should include all custom tags"
  }
}

# Test: Interactive Handler Lambda can be disabled
run "test_interactive_handler_lambda_disabled" {
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
      interactive_handler = {
        enabled = false
      }
    }
  }

  assert {
    condition     = length(aws_lambda_function.interactive_handler) == 0
    error_message = "Interactive Handler Lambda should not be created when disabled"
  }
}

# Test: Interactive Handler Lambda is created by default
run "test_interactive_handler_lambda_enabled_by_default" {
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
    condition     = length(aws_lambda_function.interactive_handler) == 1
    error_message = "Interactive Handler Lambda should be created by default"
  }
}
