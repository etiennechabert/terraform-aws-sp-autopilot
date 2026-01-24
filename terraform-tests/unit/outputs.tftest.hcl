# AWS Savings Plans Automation Module
# Outputs Tests - Credential-free testing using mock provider

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
# Slack Interactive Endpoint Output Tests
# ============================================================================

# Test: Slack interactive endpoint output is available
run "test_slack_interactive_endpoint_output" {
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
    target          = aws_apigatewayv2_stage.slack_interactive
    values = {
      invoke_url = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/"
    }
  }

  assert {
    condition     = output.slack_interactive_endpoint == "https://abc123xyz.execute-api.us-east-1.amazonaws.com/"
    error_message = "slack_interactive_endpoint output should return API Gateway invoke URL"
  }
}

# Test: Slack interactive endpoint output description
run "test_slack_interactive_endpoint_output_description" {
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

  # Note: Output descriptions cannot be tested in Terraform tests
  # This test verifies the output exists and has a value
  assert {
    condition     = output.slack_interactive_endpoint != null
    error_message = "slack_interactive_endpoint output should exist"
  }
}
