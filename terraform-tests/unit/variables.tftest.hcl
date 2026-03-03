# AWS Savings Plans Automation Module
# Variable Validation Tests - Testing all validation rules and edge cases

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
# Purchase Strategy - Target + Split Validations
# ============================================================================

# Test: dynamic (prudent) target with fixed_step split - valid
run "test_fixed_fixed_step_valid" {
  command = plan

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
}

# Test: dynamic (prudent) target with gap_split split - valid
run "test_fixed_gap_split_valid" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "prudent" }
      }

      split = {
        gap_split = {
          divider = 2
        }
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
}

# Test: aws target with one_shot split - valid
run "test_aws_target_valid" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        aws = {}
      }

      split = {
        one_shot = {}
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
}

# Test: dynamic target with fixed_step split - valid
run "test_dynamic_fixed_step_valid" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "optimal" }
      }

      split = {
        fixed_step = { step_percent = 10 }
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
}

# Test: invalid - multiple targets defined (aws + dynamic)
run "test_invalid_multiple_targets" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        aws     = {}
        dynamic = { risk_level = "optimal" }
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: invalid - dynamic target without split
run "test_invalid_fixed_without_split" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "prudent" }
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: invalid - dynamic risk_level
run "test_invalid_dynamic_risk_level" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "invalid_level" }
      }

      split = {
        fixed_step = { step_percent = 10 }
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: dynamic target with min_hourly risk level - valid
run "test_coverage_percent_valid" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "min_hourly" }
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
}

# Test: gap_split - invalid divider <= 0
run "test_gap_split_invalid_divider_zero" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "prudent" }
      }

      split = {
        gap_split = {
          divider = 0
        }
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: fixed_step step_percent - invalid above 100
run "test_fixed_step_step_percent_invalid" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "prudent" }
      }

      split = {
        fixed_step = { step_percent = 101 }
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# ============================================================================
# Risk Management - Variable Validations
# ============================================================================

# Test: min_commitment_per_plan - valid at AWS minimum (0.001)
run "test_min_commitment_per_plan_valid_at_aws_min" {
  command = plan

  variables {
    purchase_strategy = {
      min_commitment_per_plan = 0.001

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
}

# Test: min_commitment_per_plan - invalid below AWS minimum
run "test_min_commitment_per_plan_invalid_below_min" {
  command = plan

  variables {
    purchase_strategy = {
      min_commitment_per_plan = 0.0009

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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# ============================================================================
# Savings Plans Configuration - Variable Validations
# ============================================================================

# Test: At least one SP type must be enabled
run "test_at_least_one_sp_enabled" {
  command = plan

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
      compute   = { enabled = false }
      database  = { enabled = false }
      sagemaker = { enabled = false }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  expect_failures = [
    var.sp_plans,
  ]
}

# Test: Compute plan_type required when enabled
run "test_compute_plan_type_required" {
  command = plan

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
      compute   = { enabled = true }
      database  = { enabled = false }
      sagemaker = { enabled = false }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  expect_failures = [
    var.sp_plans,
  ]
}

# Test: Database plan_type must be no_upfront_one_year
run "test_database_plan_type_valid" {
  command = plan

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
      database = {
        enabled   = true
        plan_type = "no_upfront_one_year"
      }
      sagemaker = { enabled = false }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }
}

# Test: Database plan_type invalid
run "test_database_plan_type_invalid" {
  command = plan

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
      database = {
        enabled   = true
        plan_type = "all_upfront_three_year"
      }
      sagemaker = { enabled = false }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  expect_failures = [
    var.sp_plans,
  ]
}

# ============================================================================
# Reporting Configuration - Variable Validations
# ============================================================================

# Test: report_format - valid html
run "test_report_format_valid_html" {
  command = plan

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
    reporting = {
      format = "html"
    }
  }
}

# Test: report_format - invalid value
run "test_report_format_invalid" {
  command = plan

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
    reporting = {
      format = "xml"
    }
  }

  expect_failures = [
    var.reporting,
  ]
}

# Test: s3_lifecycle - invalid glacier days less than IA days
run "test_s3_lifecycle_glacier_invalid_less_than_ia" {
  command = plan

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
    reporting = {
      s3_lifecycle = {
        transition_ia_days      = 90
        transition_glacier_days = 60
      }
    }
  }

  expect_failures = [
    var.reporting,
  ]
}

# ============================================================================
# Notifications - Variable Validations
# ============================================================================

# Test: notifications - valid with emails
run "test_notifications_valid_emails" {
  command = plan

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
}

# Test: notifications - valid with slack webhook
run "test_notifications_valid_slack" {
  command = plan

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
      emails        = []
      slack_webhook = "https://hooks.slack.com/services/xxx"
    }
  }
}

# Test: notifications - invalid with no notification method
run "test_notifications_invalid_no_method" {
  command = plan

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
      emails = []
    }
  }

  expect_failures = [
    var.notifications,
  ]
}

# Test: one_shot split - valid
run "test_one_shot_split_valid" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "prudent" }
      }

      split = {
        one_shot = {}
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
}

# Test: all dynamic risk levels are valid
run "test_dynamic_risk_prudent" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "prudent" }
      }

      split = {
        fixed_step = { step_percent = 10 }
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
}

run "test_dynamic_risk_maximum" {
  command = plan

  variables {
    purchase_strategy = {
      target = {
        dynamic = { risk_level = "maximum" }
      }

      split = {
        gap_split = {
          divider = 2
        }
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
}
