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
# Purchase Strategy - Variable Validations
# ============================================================================

# Test: coverage_target_percent - valid minimum value (1)
run "test_coverage_target_percent_valid_min" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 1
      max_coverage_cap        = 2
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
}

# Test: coverage_target_percent - valid maximum value (100)
run "test_coverage_target_percent_valid_max" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 100
      max_coverage_cap        = 100
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
}

# Test: coverage_target_percent - invalid value below minimum
run "test_coverage_target_percent_invalid_below_min" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 0
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: coverage_target_percent - invalid value above maximum
run "test_coverage_target_percent_invalid_above_max" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 101
      max_coverage_cap        = 101
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: coverage_target_percent - invalid negative value
run "test_coverage_target_percent_invalid_negative" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = -10
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: max_coverage_cap - valid at boundary (100)
run "test_max_coverage_cap_valid_at_100" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 90
      max_coverage_cap        = 100
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
}

# Test: max_coverage_cap - invalid above 100
run "test_max_coverage_cap_invalid_above_100" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 90
      max_coverage_cap        = 101
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: max_coverage_cap - invalid when less than coverage_target_percent
run "test_max_coverage_cap_invalid_less_than_target" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 90
      max_coverage_cap        = 85
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
      coverage_target_percent = 80
      max_coverage_cap        = 90
      min_commitment_per_plan = 0.001
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
}

# Test: min_commitment_per_plan - valid above AWS minimum
run "test_min_commitment_per_plan_valid_above_min" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      min_commitment_per_plan = 1.5
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
}

# Test: min_commitment_per_plan - invalid below AWS minimum
run "test_min_commitment_per_plan_invalid_below_min" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      min_commitment_per_plan = 0.0009
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: min_commitment_per_plan - invalid at zero
run "test_min_commitment_per_plan_invalid_zero" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      min_commitment_per_plan = 0
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: min_commitment_per_plan - invalid negative
run "test_min_commitment_per_plan_invalid_negative" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      min_commitment_per_plan = -0.001
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# ============================================================================
# Savings Plans Configuration - Variable Validations
# ============================================================================

# Test: Compute SP percentages must sum to 1.0
run "test_compute_sp_percentages_valid_sum" {
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
        enabled                = true
        all_upfront_three_year = 0.5
        no_upfront_one_year    = 0.5
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }
}

# Test: Compute SP percentages invalid sum (less than 1.0)
run "test_compute_sp_percentages_invalid_sum_less" {
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
        enabled                = true
        all_upfront_three_year = 0.4
        no_upfront_one_year    = 0.4
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  expect_failures = [
    var.sp_plans,
  ]
}

# Test: Compute SP percentages invalid sum (greater than 1.0)
run "test_compute_sp_percentages_invalid_sum_greater" {
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
        enabled                = true
        all_upfront_three_year = 0.6
        no_upfront_one_year    = 0.6
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  expect_failures = [
    var.sp_plans,
  ]
}

# Test: Compute SP negative percentage
run "test_compute_sp_negative_percentage" {
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
        enabled                = true
        all_upfront_three_year = -0.5
        no_upfront_one_year    = 1.5
      }
    }
    notifications = {
      emails = ["test@example.com"]
    }
  }

  expect_failures = [
    var.sp_plans,
  ]
}

# Test: At least one SP type must be enabled
run "test_at_least_one_sp_enabled" {
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
}

# ============================================================================
# Reporting Configuration - Variable Validations
# ============================================================================

# Test: report_format - valid html
run "test_report_format_valid_html" {
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
      format = "html"
    }
  }
}

# Test: report_format - valid pdf
run "test_report_format_valid_pdf" {
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
      format = "pdf"
    }
  }
}

# Test: report_format - valid json
run "test_report_format_valid_json" {
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
      format = "json"
    }
  }
}

# Test: report_format - invalid value
run "test_report_format_invalid" {
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
      format = "xml"
    }
  }

  expect_failures = [
    var.reporting,
  ]
}

# Test: retention_days - valid minimum value (1)
run "test_retention_days_valid_min" {
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
      retention_days = 1
    }
  }
}

# Test: retention_days - invalid zero
run "test_retention_days_invalid_zero" {
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
      retention_days = 0
    }
  }

  expect_failures = [
    var.reporting,
  ]
}

# Test: s3_lifecycle - valid configuration
run "test_s3_lifecycle_valid" {
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
      s3_lifecycle = {
        transition_ia_days         = 90
        transition_glacier_days    = 180
        expiration_days            = 365
        noncurrent_expiration_days = 90
      }
    }
  }
}

# Test: s3_lifecycle - invalid glacier days less than IA days
run "test_s3_lifecycle_glacier_invalid_less_than_ia" {
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

# Test: s3_lifecycle - invalid expiration days less than glacier days
run "test_s3_lifecycle_expiration_invalid_less_than_glacier" {
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
      s3_lifecycle = {
        transition_ia_days      = 90
        transition_glacier_days = 180
        expiration_days         = 150
      }
    }
  }

  expect_failures = [
    var.reporting,
  ]
}

# ============================================================================
# Purchase Strategy Type - Variable Validations
# ============================================================================

# Test: simple strategy - valid
run "test_simple_strategy_valid" {
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
}

# Test: dichotomy strategy - valid
run "test_dichotomy_strategy_valid" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      dichotomy = {
        max_purchase_percent = 10
        min_purchase_percent = 2
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
}

# Test: simple strategy - invalid max_purchase_percent above 100
run "test_simple_strategy_invalid_max_above_100" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      simple = {
        max_purchase_percent = 101
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

  expect_failures = [
    var.purchase_strategy,
  ]
}

# Test: dichotomy strategy - invalid min >= max
run "test_dichotomy_strategy_invalid_min_gte_max" {
  command = plan

  variables {
    purchase_strategy = {
      coverage_target_percent = 80
      max_coverage_cap        = 90
      dichotomy = {
        max_purchase_percent = 5
        min_purchase_percent = 10
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

  expect_failures = [
    var.purchase_strategy,
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
}

# Test: notifications - valid with slack webhook
run "test_notifications_valid_slack" {
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
      emails = []
    }
  }

  expect_failures = [
    var.notifications,
  ]
}
