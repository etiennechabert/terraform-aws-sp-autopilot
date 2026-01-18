# AWS Savings Plans Automation Module
# SQS Queue Policy Tests - Credential-free testing using mock provider

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
# SQS Queue Policy Tests
# ============================================================================

# Test: SQS queue policy is created when scheduler is enabled
run "test_sqs_queue_policy_created" {
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
    condition     = length(aws_sqs_queue_policy.purchase_intents) == 1
    error_message = "SQS queue policy should be created when scheduler is enabled"
  }

  assert {
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Principal.AWS == aws_iam_role.scheduler[0].arn
    error_message = "SQS queue policy should restrict access to scheduler role"
  }

  assert {
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Action == "sqs:SendMessage"
    error_message = "SQS queue policy should allow sqs:SendMessage action"
  }
}

# Test: SQS queue policy is created with any SP plan type
run "test_sqs_queue_policy_with_database_sp" {
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
        enabled = false
      }
      database = {
        enabled             = true
        no_upfront_one_year = 1
      }
      sagemaker = {
        enabled = false
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  assert {
    condition     = length(aws_sqs_queue_policy.purchase_intents) == 1
    error_message = "SQS queue policy should be created when any SP plan is enabled"
  }
}
