# AWS Savings Plans Automation Module
# API Gateway Tests - Credential-free testing using mock provider

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
# API Gateway HTTP API Tests
# ============================================================================

# Test: API Gateway HTTP API naming follows expected pattern
run "test_api_gateway_naming" {
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
    condition     = aws_apigatewayv2_api.slack_interactive.name == "sp-autopilot-slack-interactive"
    error_message = "API Gateway name should follow pattern: sp-autopilot-slack-interactive"
  }

  assert {
    condition     = aws_apigatewayv2_api.slack_interactive.description == "Handles Slack interactive button clicks for purchase approvals/rejections"
    error_message = "API Gateway should have correct description"
  }

  assert {
    condition     = aws_apigatewayv2_api.slack_interactive.protocol_type == "HTTP"
    error_message = "API Gateway should use HTTP protocol type"
  }
}

# Test: API Gateway HTTP API has proper tags
run "test_api_gateway_tags" {
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
    condition     = aws_apigatewayv2_api.slack_interactive.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "API Gateway should have ManagedBy tag"
  }

  assert {
    condition     = aws_apigatewayv2_api.slack_interactive.tags["Module"] == "savings-plans-automation"
    error_message = "API Gateway should have Module tag"
  }

  assert {
    condition     = aws_apigatewayv2_api.slack_interactive.tags["Environment"] == "test"
    error_message = "API Gateway should include custom tags from variables"
  }
}

# ============================================================================
# API Gateway Stage Tests
# ============================================================================

# Test: API Gateway stage configuration
run "test_api_gateway_stage_configuration" {
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
    target          = aws_apigatewayv2_api.slack_interactive
    values = {
      id = "abc123xyz"
    }
  }

  assert {
    condition     = aws_apigatewayv2_stage.slack_interactive.name == "$default"
    error_message = "API Gateway stage should use $default name for auto-deploy"
  }

  assert {
    condition     = aws_apigatewayv2_stage.slack_interactive.auto_deploy == true
    error_message = "API Gateway stage should have auto_deploy enabled"
  }

  assert {
    condition     = aws_apigatewayv2_stage.slack_interactive.api_id == "abc123xyz"
    error_message = "API Gateway stage should reference correct API ID"
  }
}

# Test: API Gateway stage has proper tags
run "test_api_gateway_stage_tags" {
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
      Environment = "production"
      Team        = "finops"
    }
  }

  assert {
    condition     = aws_apigatewayv2_stage.slack_interactive.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "API Gateway stage should have ManagedBy tag"
  }

  assert {
    condition     = aws_apigatewayv2_stage.slack_interactive.tags["Module"] == "savings-plans-automation"
    error_message = "API Gateway stage should have Module tag"
  }

  assert {
    condition     = aws_apigatewayv2_stage.slack_interactive.tags["Environment"] == "production"
    error_message = "API Gateway stage should include custom tags from variables"
  }

  assert {
    condition     = aws_apigatewayv2_stage.slack_interactive.tags["Team"] == "finops"
    error_message = "API Gateway stage should include all custom tags"
  }
}
