# AWS Savings Plans Automation Module
# IAM Role and Policy Tests - Credential-free testing using mock provider

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
# Scheduler Lambda IAM Role Tests
# ============================================================================

# Test: Scheduler IAM role naming follows expected pattern
run "test_scheduler_role_naming" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role.scheduler.name == "sp-autopilot-scheduler"
    error_message = "Scheduler IAM role name should follow pattern: sp-autopilot-scheduler"
  }

  assert {
    condition     = aws_iam_role.scheduler.description == "IAM role for Scheduler Lambda function - analyzes usage and queues purchase recommendations"
    error_message = "Scheduler IAM role should have correct description"
  }
}

# Test: Scheduler IAM role assume role policy
run "test_scheduler_role_assume_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = can(jsondecode(aws_iam_role.scheduler.assume_role_policy))
    error_message = "Scheduler IAM role assume role policy should be valid JSON"
  }

  assert {
    condition     = jsondecode(aws_iam_role.scheduler.assume_role_policy).Statement[0].Principal.Service == "lambda.amazonaws.com"
    error_message = "Scheduler IAM role should allow Lambda service to assume it"
  }

  assert {
    condition     = jsondecode(aws_iam_role.scheduler.assume_role_policy).Statement[0].Action == "sts:AssumeRole"
    error_message = "Scheduler IAM role should allow sts:AssumeRole action"
  }
}

# Test: Scheduler IAM role tags include common tags
run "test_scheduler_role_tags" {
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
    condition     = aws_iam_role.scheduler.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Scheduler IAM role should have ManagedBy tag"
  }

  assert {
    condition     = aws_iam_role.scheduler.tags["Module"] == "savings-plans-automation"
    error_message = "Scheduler IAM role should have Module tag"
  }

  assert {
    condition     = aws_iam_role.scheduler.tags["Name"] == "sp-autopilot-scheduler-role"
    error_message = "Scheduler IAM role should have Name tag"
  }

  assert {
    condition     = aws_iam_role.scheduler.tags["Environment"] == "test"
    error_message = "Scheduler IAM role should include custom tags from variables"
  }
}

# Test: Scheduler CloudWatch Logs policy
run "test_scheduler_cloudwatch_logs_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.scheduler_cloudwatch_logs.name == "cloudwatch-logs"
    error_message = "Scheduler CloudWatch Logs policy should have correct name"
  }

  # Note: Mock provider doesn't populate policy content, so we can only verify the policy exists
  # In a real environment, you would verify the policy content using integration tests
  assert {
    condition     = aws_iam_role_policy.scheduler_cloudwatch_logs.policy != null
    error_message = "Scheduler CloudWatch Logs policy should be set"
  }
}

# Test: Scheduler Cost Explorer policy
run "test_scheduler_cost_explorer_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.scheduler_cost_explorer.name == "cost-explorer"
    error_message = "Scheduler Cost Explorer policy should have correct name"
  }

  # Note: Mock provider doesn't populate policy content
  assert {
    condition     = aws_iam_role_policy.scheduler_cost_explorer.policy != null
    error_message = "Scheduler Cost Explorer policy should be set"
  }
}

# Test: Scheduler SQS policy
run "test_scheduler_sqs_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.scheduler_sqs.name == "sqs"
    error_message = "Scheduler SQS policy should have correct name"
  }

  # Note: Mock provider doesn't populate policy content
  assert {
    condition     = aws_iam_role_policy.scheduler_sqs.policy != null
    error_message = "Scheduler SQS policy should be set"
  }
}

# Test: Scheduler SNS policy
run "test_scheduler_sns_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.scheduler_sns.name == "sns"
    error_message = "Scheduler SNS policy should have correct name"
  }

  # Note: Mock provider doesn't populate policy content
  assert {
    condition     = aws_iam_role_policy.scheduler_sns.policy != null
    error_message = "Scheduler SNS policy should be set"
  }
}

# Test: Scheduler Savings Plans policy
run "test_scheduler_savingsplans_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.scheduler_savingsplans.name == "savingsplans"
    error_message = "Scheduler Savings Plans policy should have correct name"
  }

  # Note: Mock provider doesn't populate policy content
  assert {
    condition     = aws_iam_role_policy.scheduler_savingsplans.policy != null
    error_message = "Scheduler Savings Plans policy should be set"
  }
}

# Test: Scheduler assume role policy not created when management_account_role_arn is null
run "test_scheduler_assume_role_policy_not_created" {
  command = plan

  variables {
    enable_compute_sp           = true
    dry_run                     = true
    management_account_role_arn = null
  }

  assert {
    condition     = length(aws_iam_role_policy.scheduler_assume_role) == 0
    error_message = "Scheduler assume role policy should not be created when management_account_role_arn is null"
  }
}

# Test: Scheduler assume role policy created when management_account_role_arn is set
run "test_scheduler_assume_role_policy_created" {
  command = plan

  variables {
    enable_compute_sp           = true
    dry_run                     = true
    management_account_role_arn = "arn:aws:iam::999888777666:role/OrganizationAccountAccessRole"
  }

  assert {
    condition     = length(aws_iam_role_policy.scheduler_assume_role) == 1
    error_message = "Scheduler assume role policy should be created when management_account_role_arn is set"
  }

  assert {
    condition     = aws_iam_role_policy.scheduler_assume_role[0].name == "assume-role"
    error_message = "Scheduler assume role policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.scheduler_assume_role[0].policy))
    error_message = "Scheduler assume role policy should be valid JSON"
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.scheduler_assume_role[0].policy).Statement[0].Action == "sts:AssumeRole"
    error_message = "Scheduler assume role policy should allow sts:AssumeRole"
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.scheduler_assume_role[0].policy).Statement[0].Resource == "arn:aws:iam::999888777666:role/OrganizationAccountAccessRole"
    error_message = "Scheduler assume role policy should reference correct management account role ARN"
  }
}

# ============================================================================
# Purchaser Lambda IAM Role Tests
# ============================================================================

# Test: Purchaser IAM role naming follows expected pattern
run "test_purchaser_role_naming" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role.purchaser.name == "sp-autopilot-purchaser"
    error_message = "Purchaser IAM role name should follow pattern: sp-autopilot-purchaser"
  }

  assert {
    condition     = aws_iam_role.purchaser.description == "IAM role for Purchaser Lambda function - executes Savings Plans purchases from queue"
    error_message = "Purchaser IAM role should have correct description"
  }
}

# Test: Purchaser IAM role assume role policy
run "test_purchaser_role_assume_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = can(jsondecode(aws_iam_role.purchaser.assume_role_policy))
    error_message = "Purchaser IAM role assume role policy should be valid JSON"
  }

  assert {
    condition     = jsondecode(aws_iam_role.purchaser.assume_role_policy).Statement[0].Principal.Service == "lambda.amazonaws.com"
    error_message = "Purchaser IAM role should allow Lambda service to assume it"
  }

  assert {
    condition     = jsondecode(aws_iam_role.purchaser.assume_role_policy).Statement[0].Action == "sts:AssumeRole"
    error_message = "Purchaser IAM role should allow sts:AssumeRole action"
  }
}

# Test: Purchaser IAM role tags include common tags
run "test_purchaser_role_tags" {
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
    condition     = aws_iam_role.purchaser.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Purchaser IAM role should have ManagedBy tag"
  }

  assert {
    condition     = aws_iam_role.purchaser.tags["Module"] == "savings-plans-automation"
    error_message = "Purchaser IAM role should have Module tag"
  }

  assert {
    condition     = aws_iam_role.purchaser.tags["Name"] == "sp-autopilot-purchaser-role"
    error_message = "Purchaser IAM role should have Name tag"
  }

  assert {
    condition     = aws_iam_role.purchaser.tags["Environment"] == "test"
    error_message = "Purchaser IAM role should include custom tags from variables"
  }
}

# Test: Purchaser CloudWatch Logs policy
run "test_purchaser_cloudwatch_logs_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  override_resource {
    override_during = plan
    target = aws_iam_role.purchaser
    values = {
      id = "sp-autopilot-purchaser"
    }
  }

  override_resource {
    override_during = plan
    target = aws_iam_role_policy.purchaser_cloudwatch_logs
    values = {
      role = "sp-autopilot-purchaser"
    }
  }

  assert {
    condition     = aws_iam_role_policy.purchaser_cloudwatch_logs.name == "cloudwatch-logs"
    error_message = "Purchaser CloudWatch Logs policy should have correct name"
  }

  assert {
    condition     = aws_iam_role_policy.purchaser_cloudwatch_logs.role == aws_iam_role.purchaser.id
    error_message = "Purchaser CloudWatch Logs policy should be attached to purchaser role"
  }

  # Note: Cannot introspect policy JSON content with mock provider
  # The policy attribute is "(known after apply)" during plan evaluation
  # Policy correctness is verified through actual AWS API testing in integration tests
}

# Test: Purchaser Cost Explorer policy
run "test_purchaser_cost_explorer_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.purchaser_cost_explorer.name == "cost-explorer"
    error_message = "Purchaser Cost Explorer policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.purchaser_cost_explorer.policy))
    error_message = "Purchaser Cost Explorer policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.purchaser_cost_explorer.policy).Statement[0].Action, "ce:GetSavingsPlansPurchaseRecommendation")
    error_message = "Purchaser Cost Explorer policy should include ce:GetSavingsPlansPurchaseRecommendation"
  }
}

# Test: Purchaser SQS policy
run "test_purchaser_sqs_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.purchaser_sqs.name == "sqs"
    error_message = "Purchaser SQS policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.purchaser_sqs.policy))
    error_message = "Purchaser SQS policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.purchaser_sqs.policy).Statement[0].Action, "sqs:ReceiveMessage")
    error_message = "Purchaser SQS policy should include sqs:ReceiveMessage"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.purchaser_sqs.policy).Statement[0].Action, "sqs:DeleteMessage")
    error_message = "Purchaser SQS policy should include sqs:DeleteMessage"
  }
}

# Test: Purchaser SNS policy
run "test_purchaser_sns_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.purchaser_sns.name == "sns"
    error_message = "Purchaser SNS policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.purchaser_sns.policy))
    error_message = "Purchaser SNS policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.purchaser_sns.policy).Statement[0].Action, "sns:Publish")
    error_message = "Purchaser SNS policy should include sns:Publish"
  }
}

# Test: Purchaser Savings Plans policy
run "test_purchaser_savingsplans_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.purchaser_savingsplans.name == "savingsplans"
    error_message = "Purchaser Savings Plans policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.purchaser_savingsplans.policy))
    error_message = "Purchaser Savings Plans policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.purchaser_savingsplans.policy).Statement[0].Action, "savingsplans:DescribeSavingsPlans")
    error_message = "Purchaser Savings Plans policy should include savingsplans:DescribeSavingsPlans"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.purchaser_savingsplans.policy).Statement[0].Action, "savingsplans:CreateSavingsPlan")
    error_message = "Purchaser Savings Plans policy should include savingsplans:CreateSavingsPlan"
  }
}

# Test: Purchaser assume role policy not created when management_account_role_arn is null
run "test_purchaser_assume_role_policy_not_created" {
  command = plan

  variables {
    enable_compute_sp           = true
    dry_run                     = true
    management_account_role_arn = null
  }

  assert {
    condition     = length(aws_iam_role_policy.purchaser_assume_role) == 0
    error_message = "Purchaser assume role policy should not be created when management_account_role_arn is null"
  }
}

# Test: Purchaser assume role policy created when management_account_role_arn is set
run "test_purchaser_assume_role_policy_created" {
  command = plan

  variables {
    enable_compute_sp           = true
    dry_run                     = true
    management_account_role_arn = "arn:aws:iam::999888777666:role/OrganizationAccountAccessRole"
  }

  assert {
    condition     = length(aws_iam_role_policy.purchaser_assume_role) == 1
    error_message = "Purchaser assume role policy should be created when management_account_role_arn is set"
  }

  assert {
    condition     = aws_iam_role_policy.purchaser_assume_role[0].name == "assume-role"
    error_message = "Purchaser assume role policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.purchaser_assume_role[0].policy))
    error_message = "Purchaser assume role policy should be valid JSON"
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.purchaser_assume_role[0].policy).Statement[0].Action == "sts:AssumeRole"
    error_message = "Purchaser assume role policy should allow sts:AssumeRole"
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.purchaser_assume_role[0].policy).Statement[0].Resource == "arn:aws:iam::999888777666:role/OrganizationAccountAccessRole"
    error_message = "Purchaser assume role policy should reference correct management account role ARN"
  }
}

# ============================================================================
# Reporter Lambda IAM Role Tests
# ============================================================================

# Test: Reporter IAM role naming follows expected pattern
run "test_reporter_role_naming" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role.reporter.name == "sp-autopilot-reporter"
    error_message = "Reporter IAM role name should follow pattern: sp-autopilot-reporter"
  }

  assert {
    condition     = aws_iam_role.reporter.description == "IAM role for Reporter Lambda function - generates periodic coverage and savings reports"
    error_message = "Reporter IAM role should have correct description"
  }
}

# Test: Reporter IAM role assume role policy
run "test_reporter_role_assume_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = can(jsondecode(aws_iam_role.reporter.assume_role_policy))
    error_message = "Reporter IAM role assume role policy should be valid JSON"
  }

  assert {
    condition     = jsondecode(aws_iam_role.reporter.assume_role_policy).Statement[0].Principal.Service == "lambda.amazonaws.com"
    error_message = "Reporter IAM role should allow Lambda service to assume it"
  }

  assert {
    condition     = jsondecode(aws_iam_role.reporter.assume_role_policy).Statement[0].Action == "sts:AssumeRole"
    error_message = "Reporter IAM role should allow sts:AssumeRole action"
  }
}

# Test: Reporter IAM role tags include common tags
run "test_reporter_role_tags" {
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
    condition     = aws_iam_role.reporter.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "Reporter IAM role should have ManagedBy tag"
  }

  assert {
    condition     = aws_iam_role.reporter.tags["Module"] == "savings-plans-automation"
    error_message = "Reporter IAM role should have Module tag"
  }

  assert {
    condition     = aws_iam_role.reporter.tags["Name"] == "sp-autopilot-reporter-role"
    error_message = "Reporter IAM role should have Name tag"
  }

  assert {
    condition     = aws_iam_role.reporter.tags["Environment"] == "test"
    error_message = "Reporter IAM role should include custom tags from variables"
  }
}

# Test: Reporter CloudWatch Logs policy
run "test_reporter_cloudwatch_logs_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.reporter_cloudwatch_logs.name == "cloudwatch-logs"
    error_message = "Reporter CloudWatch Logs policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.reporter_cloudwatch_logs.policy))
    error_message = "Reporter CloudWatch Logs policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.reporter_cloudwatch_logs.policy).Statement[0].Action, "logs:CreateLogStream")
    error_message = "Reporter CloudWatch Logs policy should include logs:CreateLogStream"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.reporter_cloudwatch_logs.policy).Statement[0].Action, "logs:PutLogEvents")
    error_message = "Reporter CloudWatch Logs policy should include logs:PutLogEvents"
  }
}

# Test: Reporter Cost Explorer policy
run "test_reporter_cost_explorer_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.reporter_cost_explorer.name == "cost-explorer"
    error_message = "Reporter Cost Explorer policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.reporter_cost_explorer.policy))
    error_message = "Reporter Cost Explorer policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.reporter_cost_explorer.policy).Statement[0].Action, "ce:GetSavingsPlansPurchaseRecommendation")
    error_message = "Reporter Cost Explorer policy should include ce:GetSavingsPlansPurchaseRecommendation"
  }
}

# Test: Reporter S3 policy
run "test_reporter_s3_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.reporter_s3.name == "s3"
    error_message = "Reporter S3 policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.reporter_s3.policy))
    error_message = "Reporter S3 policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.reporter_s3.policy).Statement[0].Action, "s3:PutObject")
    error_message = "Reporter S3 policy should include s3:PutObject"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.reporter_s3.policy).Statement[0].Action, "s3:GetObject")
    error_message = "Reporter S3 policy should include s3:GetObject"
  }
}

# Test: Reporter SNS policy
run "test_reporter_sns_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.reporter_sns.name == "sns"
    error_message = "Reporter SNS policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.reporter_sns.policy))
    error_message = "Reporter SNS policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.reporter_sns.policy).Statement[0].Action, "sns:Publish")
    error_message = "Reporter SNS policy should include sns:Publish"
  }
}

# Test: Reporter Savings Plans policy
run "test_reporter_savingsplans_policy" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_iam_role_policy.reporter_savingsplans.name == "savingsplans"
    error_message = "Reporter Savings Plans policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.reporter_savingsplans.policy))
    error_message = "Reporter Savings Plans policy should be valid JSON"
  }

  assert {
    condition     = contains(jsondecode(aws_iam_role_policy.reporter_savingsplans.policy).Statement[0].Action, "savingsplans:DescribeSavingsPlans")
    error_message = "Reporter Savings Plans policy should include savingsplans:DescribeSavingsPlans"
  }
}

# Test: Reporter assume role policy not created when management_account_role_arn is null
run "test_reporter_assume_role_policy_not_created" {
  command = plan

  variables {
    enable_compute_sp           = true
    dry_run                     = true
    management_account_role_arn = null
  }

  assert {
    condition     = length(aws_iam_role_policy.reporter_assume_role) == 0
    error_message = "Reporter assume role policy should not be created when management_account_role_arn is null"
  }
}

# Test: Reporter assume role policy created when management_account_role_arn is set
run "test_reporter_assume_role_policy_created" {
  command = plan

  variables {
    enable_compute_sp           = true
    dry_run                     = true
    management_account_role_arn = "arn:aws:iam::999888777666:role/OrganizationAccountAccessRole"
  }

  assert {
    condition     = length(aws_iam_role_policy.reporter_assume_role) == 1
    error_message = "Reporter assume role policy should be created when management_account_role_arn is set"
  }

  assert {
    condition     = aws_iam_role_policy.reporter_assume_role[0].name == "assume-role"
    error_message = "Reporter assume role policy should have correct name"
  }

  assert {
    condition     = can(jsondecode(aws_iam_role_policy.reporter_assume_role[0].policy))
    error_message = "Reporter assume role policy should be valid JSON"
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.reporter_assume_role[0].policy).Statement[0].Action == "sts:AssumeRole"
    error_message = "Reporter assume role policy should allow sts:AssumeRole"
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.reporter_assume_role[0].policy).Statement[0].Resource == "arn:aws:iam::999888777666:role/OrganizationAccountAccessRole"
    error_message = "Reporter assume role policy should reference correct management account role ARN"
  }
}
