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
# SQS Queue Policy Creation Tests
# ============================================================================

# Test: SQS queue policy is created when scheduler is enabled
run "test_sqs_queue_policy_created_when_scheduler_enabled" {
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
    error_message = "SQS queue policy should be created when scheduler is enabled (compute SP is enabled)"
  }
}

# Test: SQS queue policy is created even with only database SP enabled
run "test_sqs_queue_policy_created_with_only_database_enabled" {
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
    error_message = "SQS queue policy should be created when any SP plan is enabled (scheduler active)"
  }
}

# ============================================================================
# SQS Queue Policy Configuration Tests
# ============================================================================

# Test: SQS queue policy targets correct queue
run "test_sqs_queue_policy_targets_correct_queue" {
  command = apply

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
    condition     = aws_sqs_queue_policy.purchase_intents[0].queue_url == aws_sqs_queue.purchase_intents.id
    error_message = "SQS queue policy should target the purchase_intents queue"
  }
}

# Test: SQS queue policy has valid JSON structure
run "test_sqs_queue_policy_valid_json" {
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
    condition     = can(jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy))
    error_message = "SQS queue policy should be valid JSON"
  }
}

# Test: SQS queue policy has correct version
run "test_sqs_queue_policy_version" {
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
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Version == "2012-10-17"
    error_message = "SQS queue policy should use IAM policy version 2012-10-17"
  }
}

# ============================================================================
# SQS Queue Policy Statement Tests
# ============================================================================

# Test: SQS queue policy has exactly one statement
run "test_sqs_queue_policy_statement_count" {
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
    condition     = length(jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement) == 1
    error_message = "SQS queue policy should have exactly one statement"
  }
}

# Test: SQS queue policy statement has Allow effect
run "test_sqs_queue_policy_statement_effect" {
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
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Effect == "Allow"
    error_message = "SQS queue policy statement should have Allow effect"
  }
}

# Test: SQS queue policy allows only sqs:SendMessage action
run "test_sqs_queue_policy_action" {
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
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Action == "sqs:SendMessage"
    error_message = "SQS queue policy should allow only sqs:SendMessage action"
  }
}

# Test: SQS queue policy principal is scheduler role
run "test_sqs_queue_policy_principal" {
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
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Principal.AWS == aws_iam_role.scheduler[0].arn
    error_message = "SQS queue policy principal should be the scheduler IAM role ARN"
  }
}

# Test: SQS queue policy resource is purchase_intents queue ARN
run "test_sqs_queue_policy_resource" {
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
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Resource == aws_sqs_queue.purchase_intents.arn
    error_message = "SQS queue policy resource should be the purchase_intents queue ARN"
  }
}

# ============================================================================
# SQS Queue Policy Condition Tests
# ============================================================================

# Test: SQS queue policy has condition block
run "test_sqs_queue_policy_has_condition" {
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
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Condition != null
    error_message = "SQS queue policy statement should have a Condition block"
  }
}

# Test: SQS queue policy includes account ownership condition
run "test_sqs_queue_policy_account_ownership_condition" {
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
    condition     = can(jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Condition.StringEquals)
    error_message = "SQS queue policy should have a StringEquals condition"
  }

  assert {
    condition     = can(jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Condition.StringEquals["aws:SourceAccount"])
    error_message = "SQS queue policy should include aws:SourceAccount in condition"
  }
}

# Test: SQS queue policy account condition matches current account
run "test_sqs_queue_policy_account_condition_value" {
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
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "123456789012"
    error_message = "SQS queue policy account condition should match the current AWS account ID"
  }
}

# ============================================================================
# SQS Queue Policy with Different SP Plan Configurations
# ============================================================================

# Test: SQS queue policy created with Database SP enabled
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
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  assert {
    condition     = length(aws_sqs_queue_policy.purchase_intents) == 1
    error_message = "SQS queue policy should be created when Database SP is enabled"
  }

  assert {
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Action == "sqs:SendMessage"
    error_message = "SQS queue policy should allow sqs:SendMessage when Database SP is enabled"
  }
}

# Test: SQS queue policy created with SageMaker SP enabled
run "test_sqs_queue_policy_with_sagemaker_sp" {
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
        enabled = false
      }
      sagemaker = {
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
    error_message = "SQS queue policy should be created when SageMaker SP is enabled"
  }

  assert {
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Principal.AWS == aws_iam_role.scheduler[0].arn
    error_message = "SQS queue policy should restrict access to scheduler role when SageMaker SP is enabled"
  }
}

# Test: SQS queue policy with multiple SP plans enabled
run "test_sqs_queue_policy_with_multiple_sp_plans" {
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
      database = {
        enabled             = true
        no_upfront_one_year = 1
      }
      sagemaker = {
        enabled                 = true
        partial_upfront_one_year = 1
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  assert {
    condition     = length(aws_sqs_queue_policy.purchase_intents) == 1
    error_message = "SQS queue policy should be created when multiple SP plans are enabled"
  }

  assert {
    condition     = jsondecode(aws_sqs_queue_policy.purchase_intents[0].policy).Statement[0].Effect == "Allow"
    error_message = "SQS queue policy should have Allow effect with multiple SP plans enabled"
  }
}
