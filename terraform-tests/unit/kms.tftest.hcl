# AWS Savings Plans Automation Module
# KMS Key Tests - Credential-free testing using mock provider
#
# The notifications topic gets a key the module creates, so CloudWatch alarms can
# publish to it (an AWS managed key such as alias/aws/sns can't allow them).

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

  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
    }
  }
}

variables {
  purchase_strategy = {
    target = {
      dynamic = { risk_level = "prudent" }
    }
    split = {
      fixed_step = { step_percent = 5 }
    }
  }
  sp_plans = {
    compute = {
      enabled   = true
      plan_type = "all_upfront_one_year"
    }
    database  = { enabled = false }
    sagemaker = { enabled = false }
  }
  notifications = {
    emails = ["test@example.com"]
  }
}

# ============================================================================
# Default: the module's key
# ============================================================================

run "test_default_creates_a_rotated_key_and_alias" {
  command = plan

  assert {
    condition     = length(aws_kms_key.notifications) == 1
    error_message = "A KMS key should be created for the notifications topic by default"
  }

  assert {
    condition     = aws_kms_key.notifications[0].enable_key_rotation == true
    error_message = "The notifications key should rotate"
  }

  assert {
    condition     = aws_kms_alias.notifications[0].name == "alias/sp-autopilot-notifications"
    error_message = "The notifications key alias should follow pattern: alias/sp-autopilot-notifications"
  }
}

run "test_default_key_lets_cloudwatch_alarms_publish" {
  command = plan

  assert {
    condition = contains(jsondecode(aws_kms_key.notifications[0].policy).Statement, {
      Sid       = "CloudWatchAlarms"
      Effect    = "Allow"
      Principal = { Service = "cloudwatch.amazonaws.com" }
      Action    = ["kms:Decrypt", "kms:GenerateDataKey*"]
      Resource  = "*"
      Condition = { StringEquals = { "aws:SourceAccount" = "123456789012" } }
    })
    error_message = "The key policy should let CloudWatch alarms in this account use the key"
  }

  assert {
    condition = contains(jsondecode(aws_kms_key.notifications[0].policy).Statement, {
      Sid       = "AccountAdministration"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::123456789012:root" }
      Action    = "kms:*"
      Resource  = "*"
    })
    error_message = "The key policy should keep the account able to manage the key through IAM"
  }
}

run "test_default_topic_uses_the_module_key" {
  command = plan

  override_resource {
    override_during = plan
    target          = aws_kms_key.notifications[0]
    values = {
      arn = "arn:aws:kms:us-east-1:123456789012:key/11111111-2222-3333-4444-555555555555"
    }
  }

  assert {
    condition     = aws_sns_topic.notifications.kms_master_key_id == "arn:aws:kms:us-east-1:123456789012:key/11111111-2222-3333-4444-555555555555"
    error_message = "The notifications topic should be encrypted with the module's key"
  }
}

run "test_default_lambda_roles_can_publish_with_the_key" {
  command = plan

  override_resource {
    override_during = plan
    target          = aws_kms_key.notifications[0]
    values = {
      arn = "arn:aws:kms:us-east-1:123456789012:key/11111111-2222-3333-4444-555555555555"
    }
  }

  override_resource {
    override_during = plan
    target          = aws_sns_topic.notifications
    values = {
      arn = "arn:aws:sns:us-east-1:123456789012:sp-autopilot-notifications"
    }
  }

  assert {
    condition = alltrue([
      for policy in [aws_iam_role_policy.scheduler_sns[0], aws_iam_role_policy.purchaser_sns[0], aws_iam_role_policy.reporter_sns[0]] :
      contains(jsondecode(policy.policy).Statement, {
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey*", "kms:Decrypt"]
        Resource = "arn:aws:kms:us-east-1:123456789012:key/11111111-2222-3333-4444-555555555555"
      })
    ])
    error_message = "Each Lambda role should be allowed to encrypt with the notifications key"
  }
}

# ============================================================================
# A key of your own
# ============================================================================

run "test_own_key_creates_no_key" {
  command = plan

  variables {
    encryption = {
      sns_kms_key = "arn:aws:kms:us-east-1:123456789012:key/99999999-8888-7777-6666-555555555555"
    }
  }

  override_resource {
    override_during = plan
    target          = aws_sns_topic.notifications
    values = {
      arn = "arn:aws:sns:us-east-1:123456789012:sp-autopilot-notifications"
    }
  }

  assert {
    condition     = length(aws_kms_key.notifications) == 0 && length(aws_kms_alias.notifications) == 0
    error_message = "No key should be created when encryption.sns_kms_key names one"
  }

  assert {
    condition     = aws_sns_topic.notifications.kms_master_key_id == "arn:aws:kms:us-east-1:123456789012:key/99999999-8888-7777-6666-555555555555"
    error_message = "The notifications topic should use the given key"
  }

  assert {
    condition     = length(jsondecode(aws_iam_role_policy.scheduler_sns[0].policy).Statement) == 1
    error_message = "With your own key, its policy grants the Lambda roles access; the module adds no KMS statement"
  }
}
